import platform
from pathlib import Path


def is_macos() -> bool:
    return platform.system() == "Darwin"


def is_raspberry_pi() -> bool:
    if platform.system() != "Linux":
        return False
    try:
        model_path = Path("/sys/firmware/devicetree/base/model")
        if model_path.exists():
            text = model_path.read_text(errors="ignore")
            if "Raspberry Pi" in text:
                return True
    except Exception:
        pass
    try:
        cpuinfo = Path("/proc/cpuinfo")
        if cpuinfo.exists():
            text = cpuinfo.read_text(errors="ignore")
            if "Raspberry Pi" in text or "BCM270" in text or "BCM271" in text:
                return True
    except Exception:
        pass
    return False
