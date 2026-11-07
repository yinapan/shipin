# CUDA PyTorch 安装

运行本项目的 CUDA 语音功能时使用独立的 `.venv-cosyvoice` 环境，不修改系统 Python 中的其他语音项目依赖。

```powershell
# 首次使用时创建环境（已有环境无需重复创建）
python -m venv .venv-cosyvoice
powershell -ExecutionPolicy Bypass -File scripts/install_cuda_torch.ps1
```

脚本通过 `requirements-cuda.txt` 安装 PyTorch 2.3.1+cu121、TorchAudio 2.3.1+cu121 和 NumPy 1.26.4，再安装基础媒体依赖；每一步失败都会停止。最后执行实际 GPU 张量计算并报告显卡信息。普通媒体处理仍只需 `pip install -r requirements.txt`。

这些版本与 [CosyVoice 官方依赖](https://github.com/QwenAudio/CosyVoice/blob/main/requirements.txt) 保持一致。CUDA wheel 自带 CUDA 运行时，普通推理无需另装完整 CUDA Toolkit；显卡仍需兼容驱动。CUDA 不可用时脚本明确失败，不静默退回 CPU。

依赖或环境更改后，可单独复验：

```powershell
.\.venv-cosyvoice\Scripts\python.exe -c "import torch, torchaudio; assert torch.cuda.is_available(); x=torch.ones(4,device='cuda'); assert x.sum().item()==4; print(torch.__version__, torchaudio.__version__, torch.version.cuda, torch.cuda.get_device_name(0))"
```

CosyVoice 源码、模型下载和旁白生成入口见项目的 CosyVoice 接入说明。虚拟环境、模型和权重不应提交或放入分享包。
