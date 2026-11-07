# CosyVoice 旁白接入

`scripts/generate_voice_cosyvoice.py` 调用仓库 `tools/CosyVoice` 中的官方
`AutoModel`，以项目指定的参考音频和逐字文稿进行 CosyVoice2 zero-shot 音色克隆。
模型权重与虚拟环境不放入分享包。

在 `project_config.json` 的 `voice.cosyvoice` 中填写模型目录和参考音频逐字文稿：

```json
{
  "model_dir": "tools/models/CosyVoice2-0.5B",
  "source_dir": "tools/CosyVoice",
  "prompt_text": "参考音频中实际说出的完整文字",
  "output_file": "work/voice/cosyvoice.wav"
}
```

生成旁白：

```powershell
python scripts/generate_voice_cosyvoice.py --text-file work/narration.txt --device cuda
```

可用 `--text`、`--model-dir`、`--reference-audio` 和 `--output` 覆盖配置。官方 API
直接接收参考音频路径，脚本输出 48 kHz 单声道 PCM WAV；已有输出文件不会被覆盖。
当前入口要求 `--device cuda`，因为项目目标是 CUDA 版 PyTorch。首次运行前执行安装脚本；
它会安装推理依赖，并处理 Python 3.12 下 `openai-whisper` 的构建兼容性。然后下载匹配版本的模型权重：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_cosyvoice.ps1
```

```powershell
.\.venv-cosyvoice\Scripts\python.exe -c "from modelscope import snapshot_download; snapshot_download('iic/CosyVoice2-0.5B', local_dir='tools/models/CosyVoice2-0.5B')"
```
