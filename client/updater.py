import os
import re
import sys

from version import VERSION

LATEST = "https://api.github.com/repos/deivao06/zoozap/releases/latest"
ASSET = "zoozap-windows.exe" if sys.platform == "win32" else "zoozap-linux"


def enabled() -> bool:
    return getattr(sys, "frozen", False) and VERSION != "dev"


def numbers(tag: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", tag))


def newer(release: dict) -> tuple[str, str] | None:
    tag = release.get("tag_name", "")
    if numbers(tag) <= numbers(VERSION):
        return None
    for asset in release.get("assets", []):
        if asset.get("name") == ASSET:
            return tag, asset["browser_download_url"]
    return None


def cleanup(exe: str = sys.executable) -> None:
    try:
        os.remove(exe + ".old")
    except OSError:
        pass


def install(data: bytes, exe: str = sys.executable) -> None:
    new = exe + ".new"
    try:
        with open(new, "wb") as f:
            f.write(data)
        if sys.platform == "win32":
            os.replace(exe, exe + ".old")
            try:
                os.replace(new, exe)
            except OSError:
                os.replace(exe + ".old", exe)
                raise
        else:
            os.chmod(new, 0o755)
            os.replace(new, exe)
    except OSError:
        try:
            os.remove(new)
        except OSError:
            pass
        raise
