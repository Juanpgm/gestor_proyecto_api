"""Local development launcher — runs uvicorn from the correct directory with .env loaded."""

import os
import sys
import pathlib

# Force UTF-8 I/O on Windows to prevent UnicodeEncodeError with emoji characters
# Must be set BEFORE importing modules that call print() with non-ASCII chars.
# PYTHONUTF8=1 also propagates to uvicorn's spawned worker subprocess.
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Ensure CWD is the back/ directory so all relative imports work
BACK_DIR = pathlib.Path(__file__).parent
os.chdir(BACK_DIR)
sys.path.insert(0, str(BACK_DIR))

# Load .env before any module import
from dotenv import load_dotenv

load_dotenv(dotenv_path=BACK_DIR / ".env", override=False)

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=[str(BACK_DIR)],
    )
