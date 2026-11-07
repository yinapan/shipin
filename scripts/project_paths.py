"""读取本地项目配置，并解析各工作目录。"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "project_config.json"

def load_config():
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return {"root_layout": {"videos": "mp4/", "audio": "wav/", "work": "work/", "output": "output/"}}

CONFIG = load_config()
LAYOUT = CONFIG.get("root_layout", {})

def project_path(key, default):
    value = LAYOUT.get(key, default)
    path = Path(value)
    return path if path.is_absolute() else ROOT / path
