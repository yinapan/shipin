param(
    [string]$Python = "$PSScriptRoot\..\.venv-cosyvoice\Scripts\python.exe"
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python executable not found: $Python"
}
& $Python -m pip install --upgrade pip
& $Python -m pip install --index-url https://download.pytorch.org/whl/cu121 torch==2.3.1 torchaudio==2.3.1
& $Python -m pip install -r "$PSScriptRoot\..\requirements.txt"
& $Python -c "import torch, torchaudio; assert torch.cuda.is_available(), 'CUDA is unavailable'; print(f'torch={torch.__version__} torchaudio={torchaudio.__version__} cuda={torch.version.cuda} device={torch.cuda.get_device_name(0)}')"
