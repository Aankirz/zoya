"""One-time model download: `python -m zoya.setup_models` (needs network; run it once per Mac).

At runtime Zoya never touches the network for models (HF_HUB_OFFLINE=1, set in zoya/main.py).
Found live: Hugging Face revision checks at startup hung Zoya indefinitely when this network's
IPv6 route black-holed (AUDIT §6). Every model is pinned to a revision, and the weights to sha256.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path

from zoya.config import (
    APP_BUNDLE,
    LOG_DIR,
    MEMORY_SERVER_BIN,
    MEMORY_SERVER_DOWNLOAD_TIMEOUT_S,
    MEMORY_SERVER_SHA256,
    MEMORY_SERVER_URL,
    MODEL_DOWNLOAD_BYTES,
    MODEL_PINS,
)

SETUP_ETAG_TIMEOUT_S = "5"
SETUP_DOWNLOAD_TIMEOUT_S = "30"
SETUP_COMMAND = ".venv/bin/python -m zoya.setup_models"
SETUP_LOG = LOG_DIR / "setup_models.log"
PROGRESS_EVERY_S = 20.0
BYTES_PER_GB = 1e9
DOWNLOADING = (
    "Now I'll download my speech models. That's about {size} gigabytes, so it can take a few "
    "minutes. I'll tell you how it's going."
)
PROGRESS = "Downloading, {percent} percent."
DOWNLOADED = "My speech models are downloaded."
DOWNLOAD_FAILED = (
    "I couldn't download my speech models. Check that this Mac is online, then open me again."
)


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


def missing_models() -> list[str]:
    missing = []
    for repo in MODEL_PINS:
        try:
            local_model_dir(repo)
        except ModelsMissing:
            missing.append(repo)
    return missing


def downloaded_bytes() -> int:
    from huggingface_hub import constants

    total = 0
    for repo in MODEL_PINS:
        blobs = Path(constants.HF_HUB_CACHE) / f"models--{repo.replace('/', '--')}" / "blobs"
        if blobs.is_dir():
            total += sum(blob.stat().st_size for blob in blobs.iterdir() if blob.is_file())
    return total


def ensure_downloaded(say: Callable[[str], None]) -> None:
    if not missing_models():
        return
    say(DOWNLOADING.format(size=round(MODEL_DOWNLOAD_BYTES / BYTES_PER_GB, 1)))
    SETUP_LOG.parent.mkdir(parents=True, exist_ok=True)
    with SETUP_LOG.open("a", encoding="utf-8") as log:
        child = subprocess.Popen(
            [sys.executable, "-m", "zoya.setup_models"], stdout=log, stderr=subprocess.STDOUT
        )
        _report_progress(child, say)
    if child.returncode != 0 or missing_models():
        say(DOWNLOAD_FAILED)
        raise ModelsMissing(f"the model download failed, see {SETUP_LOG}")
    say(DOWNLOADED)


def _report_progress(child: subprocess.Popen, say: Callable[[str], None]) -> None:
    spoken = -1
    while True:
        try:
            child.wait(timeout=PROGRESS_EVERY_S)
            return
        except subprocess.TimeoutExpired:
            percent = min(99, int(100 * downloaded_bytes() / MODEL_DOWNLOAD_BYTES))
            if percent != spoken:
                say(PROGRESS.format(percent=percent))
                spoken = percent


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


def download_memory_server() -> list[str]:
    """Supermemory local's server binary (production P2), pinned by version and sha256."""
    if APP_BUNDLE:
        return []
    if MEMORY_SERVER_BIN.exists() and _sha256(MEMORY_SERVER_BIN) == MEMORY_SERVER_SHA256:
        print(f"supermemory-server: ok ({MEMORY_SERVER_BIN})")
        return []
    MEMORY_SERVER_BIN.parent.mkdir(parents=True, exist_ok=True)
    partial = MEMORY_SERVER_BIN.with_suffix(".download")
    source = urllib.request.urlopen(MEMORY_SERVER_URL, timeout=MEMORY_SERVER_DOWNLOAD_TIMEOUT_S)
    with source as src, partial.open("wb") as out:
        for chunk in iter(lambda: src.read(1 << 20), b""):
            out.write(chunk)
    actual = _sha256(partial)
    if actual != MEMORY_SERVER_SHA256:
        partial.unlink()
        print(f"supermemory-server: CHECKSUM MISMATCH {actual}")
        return ["supermemory-server"]
    partial.chmod(0o755)
    partial.replace(MEMORY_SERVER_BIN)
    print(f"supermemory-server: ok ({MEMORY_SERVER_BIN})")
    return []


def main() -> int:
    os.environ["HF_HUB_OFFLINE"] = "0"
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", SETUP_ETAG_TIMEOUT_S)
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", SETUP_DOWNLOAD_TIMEOUT_S)
    problems = download_all() + download_memory_server()
    print("all models ready" if not problems else f"failed: {problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
