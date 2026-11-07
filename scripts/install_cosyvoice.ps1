param(
    [string]$Python = "$PSScriptRoot\..\.venv-cosyvoice\Scripts\python.exe"
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $Python)) { throw "Python executable not found: $Python" }

& $Python -m pip install -r "$PSScriptRoot\..\requirements-cosyvoice-inference.txt"
if ($LASTEXITCODE -ne 0) { throw "CosyVoice inference dependencies failed ($LASTEXITCODE)" }

# openai-whisper 20231117 imports pkg_resources while building. Python 3.12
# needs a setuptools version that still provides it, and the legacy sdist must
# be built in the current environment instead of an isolated PEP-517 env.
& $Python -m pip install "setuptools<81"
if ($LASTEXITCODE -ne 0) { throw "setuptools compatibility install failed ($LASTEXITCODE)" }
& $Python -m pip install --no-build-isolation "openai-whisper==20231117"
if ($LASTEXITCODE -ne 0) { throw "openai-whisper installation failed ($LASTEXITCODE)" }

& $Python -c "import sys; sys.path.insert(0, r'$PSScriptRoot\..\tools\CosyVoice'); sys.path.insert(0, r'$PSScriptRoot\..\tools\CosyVoice\third_party\Matcha-TTS'); import whisper, cosyvoice.cli.cosyvoice; print('CosyVoice imports OK')"
if ($LASTEXITCODE -ne 0) { throw "CosyVoice import validation failed ($LASTEXITCODE)" }
