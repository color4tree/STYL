"""Isolated API entry point that identifies its real process for safe teardown."""

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

import uvicorn


def main() -> None:
    directory = Path(os.environ["STYL_E2E_DATA_DIR"])
    token = os.environ["STYL_E2E_TOKEN"]
    if (not directory.is_absolute() or directory.parent != Path(tempfile.gettempdir())
            or not directory.name.startswith("styl-e2e-") or directory.is_symlink()
            or os.environ.get("STYL_ANALYTICS_ENVIRONMENT") != "test"
            or os.environ.get("STYL_DATA_DIR") != str(directory) or not token):
        raise ValueError("The test API requires its own isolated temporary directory and credentials.")
    owner = directory / "api-process.json"
    with owner.open("x", encoding="utf-8") as output:
        owner.chmod(0o600)
        json.dump({"pid": os.getpid(), "directory": str(directory),
                   "ownerHash": hashlib.sha256(token.encode()).hexdigest()}, output)
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))
    uvicorn.run("app.main:app", host="127.0.0.1", port=8102)


if __name__ == "__main__":
    main()
