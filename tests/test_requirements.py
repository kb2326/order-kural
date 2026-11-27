"""Every third-party package the app imports must be in requirements.txt, or Docker (and the live link) will crash
when that code first runs. 27 Nov: pipecat was installed locally but missing here; the keyless start hid it."""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_OF = {"fastapi": "fastapi", "starlette": "fastapi", "pydantic": "pydantic", "httpx": "httpx",
              "uvicorn": "uvicorn", "pipecat": "pipecat-ai", "multipart": "python-multipart"}
OPTIONAL = {"imageio_ffmpeg"}  # local-only fallback for ffmpeg; the Docker image installs ffmpeg itself


def third_party_imports() -> set[str]:
    found = set()
    for path in (ROOT / "app").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module] if isinstance(node, ast.ImportFrom) and node.module and node.level == 0 else []
            for name in names:
                top = name.split(".")[0]
                if top != "app" and top not in sys.stdlib_module_names and top not in OPTIONAL:
                    found.add(top)
    return found


def test_every_app_import_is_in_requirements():
    listed = {line.split("==")[0].split("[")[0].strip().lower()
              for line in (ROOT / "requirements.txt").read_text().splitlines() if line.strip()}
    missing = sorted(m for m in third_party_imports() if PACKAGE_OF.get(m, m) not in listed)
    assert missing == []
