"""Contract tests independent of downloaded model weights and CUDA hardware."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np
import soundfile as sf

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/generate_voice_cosyvoice.py"
spec = importlib.util.spec_from_file_location("voice_entry", SCRIPT)
voice = importlib.util.module_from_spec(spec)
spec.loader.exec_module(voice)


class VoiceContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.reference = self.root / "reference.wav"
        self.reference.touch()
        self.output = self.root / "out.wav"
        self.kwargs = dict(model_dir=self.root, reference_audio=self.reference,
                           prompt_text="reference words", text="new words",
                           output=self.output, device="cuda", output_rate=24000)

    def model(self, chunks):
        return SimpleNamespace(sample_rate=24000, inference_zero_shot=Mock(return_value=iter(chunks)))

    def run_generate(self, model, **changes):
        with patch.object(voice, "_load_cosyvoice", return_value=model), patch.dict(sys.modules, {"torchaudio": SimpleNamespace()}):
            return voice.generate(**(self.kwargs | changes))

    def test_mono_shapes_and_invalid_outputs(self):
        np.testing.assert_array_equal(voice._array([[0, 2, -2]]), [0, 1, -1])
        np.testing.assert_array_equal(voice._array([0, 1]), [0, 1])
        for invalid in ([], [[1], [2]], np.zeros((1, 1, 3)), [float("nan")], [float("inf")]):
            with self.subTest(value=str(invalid)), self.assertRaises(ValueError):
                voice._array(invalid)

    def test_upstream_factory_contract_and_no_failure_fallback(self):
        factory = Mock(return_value="model")
        torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: True))
        original_path = sys.path[:]
        self.addCleanup(lambda: sys.path.__setitem__(slice(None), original_path))
        with patch.dict(sys.modules, {"torch": torch}), patch.object(voice.importlib, "import_module", return_value=SimpleNamespace(AutoModel=factory)):
            self.assertEqual(voice._load_cosyvoice(self.root, "cuda", self.root), "model")
            factory.assert_called_once_with(model_dir=str(self.root), load_trt=False, fp16=False)
            factory.reset_mock(side_effect=True)
            factory.side_effect = RuntimeError("model corrupted")
            with self.assertRaisesRegex(RuntimeError, "model corrupted"):
                voice._load_cosyvoice(self.root, "cuda", self.root)
            self.assertEqual(factory.call_count, 1)

    def test_cuda_missing_does_not_silently_use_cpu(self):
        with patch.dict(sys.modules, {"torch": SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))}):
            with self.assertRaises(RuntimeError):
                voice._load_cosyvoice(self.root, "cuda")
            with self.assertRaises(ValueError):
                voice._load_cosyvoice(self.root, "cpu")

    def test_two_generations_do_not_reuse_model_output(self):
        first = self.model([{"tts_speech": np.full((1, 24), .2)}])
        second = self.model([{"tts_speech": np.full(48, -.3)}])
        self.run_generate(first)
        next_output = self.root / "second.wav"
        self.run_generate(second, output=next_output, text="different sentence")
        a, rate_a = sf.read(self.output)
        b, rate_b = sf.read(next_output)
        self.assertEqual((len(a), len(b), rate_a, rate_b), (24, 48, 24000, 24000))
        self.assertGreater(float(a.mean()), 0)
        self.assertLess(float(b.mean()), 0)
        second.inference_zero_shot.assert_called_once_with("different sentence", "reference words", str(self.reference), stream=False, speed=1.0)

    def test_existing_output_is_preserved_without_loading_model(self):
        self.output.write_bytes(b"original")
        with patch.object(voice, "_load_cosyvoice") as load, self.assertRaises(FileExistsError):
            voice.generate(**self.kwargs)
        load.assert_not_called()
        self.assertEqual(self.output.read_bytes(), b"original")

    def test_failed_or_empty_inference_leaves_retryable_output(self):
        for chunks in ([], [np.array([float("nan")])]):
            with self.subTest(chunks=str(chunks)), self.assertRaises((RuntimeError, ValueError)):
                self.run_generate(self.model(chunks))
            self.assertFalse(self.output.exists())
        self.run_generate(self.model([np.zeros(12)]))
        self.assertTrue(self.output.is_file())

    def test_failed_write_removes_only_its_new_file_and_retry_succeeds(self):
        with patch.object(voice.sf, "write", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                self.run_generate(self.model([np.zeros(12)]))
        self.assertFalse(self.output.exists())
        self.run_generate(self.model([np.zeros(12)]))
        self.assertTrue(self.output.exists())

    def test_concurrent_output_creation_does_not_delete_other_file(self):
        def competing_load(*args):
            self.output.write_bytes(b"other process")
            return self.model([np.zeros(12)])
        with patch.object(voice, "_load_cosyvoice", side_effect=competing_load):
            with self.assertRaises(FileExistsError):
                voice.generate(**self.kwargs)
        self.assertEqual(self.output.read_bytes(), b"other process")

    def test_invalid_speed_and_rate_fail_before_loading_model(self):
        for change in ({"speed": 0}, {"speed": float("nan")}, {"output_rate": 0}, {"output_rate": -1}):
            with self.subTest(change=change), patch.object(voice, "_load_cosyvoice") as load:
                with self.assertRaises(ValueError):
                    voice.generate(**(self.kwargs | change))
                load.assert_not_called()

    def test_config_paths_are_independent_of_process_directory(self):
        config = self.root / "project.json"
        config.write_text(json.dumps({"voice": {"reference_file": "ref.wav", "cosyvoice": {"source_dir": "source", "model_dir": "models", "output_file": "audio/out.wav", "prompt_text": "prompt"}}}), encoding="utf-8")
        (self.root / "text.txt").write_text("narration", encoding="utf-8")
        with patch.object(sys, "argv", [str(SCRIPT), "--config", str(config), "--text-file", "text.txt"]), patch.object(voice, "generate", return_value=self.output) as generate:
            self.assertEqual(voice.main(), 0)
        kw = generate.call_args.kwargs
        self.assertEqual(kw["reference_audio"], self.root / "ref.wav")
        self.assertEqual(kw["model_dir"], self.root / "models")
        self.assertEqual(kw["source_dir"], self.root / "source")
        self.assertEqual(kw["output"], self.root / "audio/out.wav")
        self.assertEqual(kw["text"], "narration")


if __name__ == "__main__":
    unittest.main()
