param(
    [string]$Python = "$PSScriptRoot\..\.venv-cosyvoice\Scripts\python.exe"
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python executable not found: $Python"
}
& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed ($LASTEXITCODE)" }
& $Python -m pip install -r "$PSScriptRoot\..\requirements-cuda.txt"
if ($LASTEXITCODE -ne 0) { throw "CUDA PyTorch installation failed ($LASTEXITCODE)" }
& $Python -m pip install -r "$PSScriptRoot\..\requirements.txt"
if ($LASTEXITCODE -ne 0) { throw "Media dependency installation failed ($LASTEXITCODE)" }
& $Python -c "import torch, torchaudio; assert torch.cuda.is_available(), 'CUDA is unavailable'; x=torch.ones(4,device='cuda'); assert x.sum().item()==4; print(f'torch={torch.__version__} torchaudio={torchaudio.__version__} cuda={torch.version.cuda} device={torch.cuda.get_device_name(0)}')"
if ($LASTEXITCODE -ne 0) { throw "CUDA GPU validation failed ($LASTEXITCODE)" }
