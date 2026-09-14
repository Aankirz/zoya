"""One-time model download: `python -m zoya.setup_models` (needs network; run it once per Mac).

At runtime Zoya never touches the network for models (HF_HUB_OFFLINE=1, set in zoya/main.py).
Found live: Hugging Face revision checks at startup hung Zoya indefinitely when this network's
IPv6 route black-holed (AUDIT §6). Every model is pinned to a revision, and the weights to sha256.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

from zoya.config import MODEL_PINS

SETUP_ETAG_TIMEOUT_S = "5"
SETUP_DOWNLOAD_TIMEOUT_S = "30"
SETUP_COMMAND = ".venv/bin/python -m zoya.setup_models"


class ModelsMissing(RuntimeError):
    """A pinned model isn't in the local cache; the message says how to fix it."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def local_model_dir(repo: str) -> str:
    """The cached snapshot of a pinned model, without any network access."""
    from huggingface_hub import snapshot_download

    revision, _files = MODEL_PINS[repo]
    try:
        return snapshot_download(repo, revision=revision, local_files_only=True)
    except Exception as error:  # noqa: BLE001 — any cache miss means the same fix
        raise ModelsMissing(f"Model {repo} is not downloaded. Run once: {SETUP_COMMAND}") from error


def download_all() -> list[str]:
    from huggingface_hub import snapshot_download

    problems = []
    for repo, (revision, files) in MODEL_PINS.items():
        folder = Path(snapshot_download(repo, revision=revision))
        for name, expected in files.items():
            actual = _sha256(folder / name)
            status = "ok" if actual == expected else f"CHECKSUM MISMATCH {actual}"
            print(f"{repo}@{revision[:8]} {name}: {status}")
            if actual != expected:
                problems.append(f"{repo}/{name}")
    return problems


def main() -> int:
    os.environ["HF_HUB_OFFLINE"] = "0"
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", SETUP_ETAG_TIMEOUT_S)
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", SETUP_DOWNLOAD_TIMEOUT_S)
    problems = download_all()
    print("all models ready" if not problems else f"failed: {problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
