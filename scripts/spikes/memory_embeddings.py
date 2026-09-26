"""P2 spike: does Supermemory local's default English embedding find Hinglish memories?

Runs one local server per embedding model on a throwaway data dir, stores the same memories,
asks paraphrased questions (English, Hinglish, Devanagari) with Zoya's own hybrid search, and
counts how often the right memory is the top result and in the top 3. Also reports each
server's resident memory.

  ZOYA_LICENSE_KEY=... ZOYA_RELAY_URL=http://localhost:8787 \
    .venv/bin/python scripts/spikes/memory_embeddings.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from supermemory import Supermemory

from zoya import memory_server
from zoya.config import LOG_DIR, load_env

MODELS = {"bge-base-en-v1.5": ("Xenova/bge-base-en-v1.5", 768), "bge-m3": ("Xenova/bge-m3", 1024)}
FIRST_PORT = 6781
READY_TIMEOUT_S = 180
INGEST_TIMEOUT_S = 300
POLL_S = 2
TOP_K = 3
TAG = "user_spike"

MEMORIES = [
    ("birthday", "Meri behen ka birthday 12 March ko hai"),
    ("milk", "Mummy ko Amul Taaza doodh pasand hai, hamesha 2 litre wala"),
    ("rahul", "Rahul Verma mera office wala dost hai, Gurgaon mein rehta hai"),
    ("address", "Mera ghar ka address hai B-42, Sector 15, Noida"),
    ("yoga", "Main har Sunday subah yoga karta hoon"),
    ("biryani", "Mujhe Behrouz se biryani mangwana pasand hai"),
    ("medicine", "Papa ki dawai Telma 40 hai, roz subah ek goli"),
    ("car", "Meri gaadi ki service har chhe mahine Maruti workshop mein hoti hai"),
    ("colour", "Priya meri wife hai, uska favourite colour neela hai"),
    ("news", "Main khabar ke liye Aaj Tak dekhta hoon"),
    ("delhi", "मेरी बहन दिल्ली में रहती है"),
    ("gym", "I go to the gym on Monday, Wednesday and Friday evenings"),
]
QUERIES = [
    ("birthday", "when is my sister's birthday"),
    ("birthday", "didi ka janamdin kab hai"),
    ("milk", "which milk does mom like"),
    ("milk", "maa kaunsa doodh leti hain"),
    ("rahul", "who is my colleague in Gurugram"),
    ("address", "where do I live"),
    ("address", "mera pata kya hai"),
    ("yoga", "what do I do on weekend mornings"),
    ("biryani", "what food do I like to order"),
    ("medicine", "what medicine does my father take"),
    ("medicine", "pitaji ki goli ka naam"),
    ("car", "when is the car serviced"),
    ("colour", "biwi ka pasandida rang kya hai"),
    ("news", "which channel do I watch for news"),
    ("delhi", "sister kahan rehti hai"),
    ("delhi", "बहन किस शहर में है"),
    ("gym", "जिम कब जाता हूँ"),
    ("gym", "when do I work out"),
]
NEVER_STORED = [
    "what is my passport number",
    "mera blood group kya hai",
    "which school did my son go to",
    "favourite cricket team kaun si hai",
]
THRESHOLDS = (0.0, 0.2, 0.4)
KEYWORDS = {
    "birthday": ("12 march", "birthday"),
    "milk": ("amul", "doodh", "milk"),
    "rahul": ("rahul",),
    "address": ("b-42", "sector 15", "noida"),
    "yoga": ("yoga",),
    "biryani": ("biryani", "behrouz"),
    "medicine": ("telma",),
    "car": ("maruti", "service"),
    "colour": ("neela", "blue", "colour", "color"),
    "news": ("aaj tak",),
    "delhi": ("दिल्ली", "delhi"),
    "gym": ("gym",),
}


def _rss_mb(pid: int) -> float:
    tree = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,rss="], capture_output=True, text=True)
    rows = [tuple(int(v) for v in line.split()) for line in tree.stdout.splitlines()]
    pids, total = {pid}, 0
    for _ in range(3):
        pids |= {p for p, parent, _rss in rows if parent in pids}
    total = sum(rss for p, _parent, rss in rows if p in pids)
    return total / 1024


def _wait_ready(url: str) -> None:
    deadline = time.monotonic() + READY_TIMEOUT_S
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except urllib.error.HTTPError:
            return
        except OSError:
            time.sleep(POLL_S)
    raise TimeoutError(url)


def _ingest(client: Supermemory, pid: int) -> tuple[float, float]:
    started, peak = time.monotonic(), 0.0
    for key, text in MEMORIES:
        client.add(content=text, container_tag=TAG, dreaming="instant", metadata={"key": key})
    while time.monotonic() - started < INGEST_TIMEOUT_S:
        docs = client.documents.list(container_tags=[TAG], limit=50).memories
        if len(docs) == len(MEMORIES) and all(d.status == "done" for d in docs):
            break
        peak = max(peak, _rss_mb(pid))
        time.sleep(POLL_S)
    return time.monotonic() - started, peak


def _rank(
    client: Supermemory, query: str, expected: str, threshold: float | None = None
) -> tuple[int | None, str]:
    extra = {} if threshold is None else {"threshold": threshold}
    results = client.search.memories(
        q=query, container_tag=TAG, limit=TOP_K, search_mode="hybrid", **extra
    ).results
    texts = [result.memory or result.chunk or "" for result in results]
    for index, text in enumerate(texts):
        if any(word in text.casefold() for word in KEYWORDS[expected]):
            return index, texts[0]
    return None, texts[0] if texts else ""


def _count(client: Supermemory, query: str, threshold: float | None) -> int:
    extra = {} if threshold is None else {"threshold": threshold}
    return len(
        client.search.memories(
            q=query, container_tag=TAG, limit=TOP_K, search_mode="hybrid", **extra
        ).results
    )


def measure(name: str, model: tuple[str, int], port: int) -> dict[str, object]:
    data_dir = Path(tempfile.mkdtemp(prefix=f"zoya-emb-{name}-"))
    env = memory_server.server_env(port=port, data_dir=data_dir, embedding=model)
    process = memory_server.spawn(env, LOG_DIR / f"memory_embeddings_{name}.log")
    try:
        _wait_ready(memory_server.base_url(port))
        client = Supermemory(
            api_key="zoya-local", base_url=memory_server.base_url(port), timeout=30, max_retries=0
        )
        ingest_s, peak_mb = _ingest(client, process.pid)
        ranks = [(query, *_rank(client, query, key)) for key, query in QUERIES]
        sweep = {
            str(threshold): {
                "top1": sum(_rank(client, query, key, threshold)[0] == 0 for key, query in QUERIES),
                "results_for_never_stored": [
                    _count(client, query, threshold) for query in NEVER_STORED
                ],
            }
            for threshold in THRESHOLDS
        }
        default_noise = [_count(client, query, None) for query in NEVER_STORED]
        started = time.monotonic()
        for _key, query in QUERIES:
            _rank(client, query, _key)
        search_ms = (time.monotonic() - started) * 1000 / len(QUERIES)
        return {
            "model": model[0],
            "top1": sum(rank == 0 for _q, rank, _top in ranks),
            "top3": sum(rank is not None for _q, rank, _top in ranks),
            "results_for_never_stored": default_noise,
            "threshold_sweep": sweep,
            "queries": len(QUERIES),
            "misses": {q: top for q, rank, top in ranks if rank != 0},
            "ingest_s": round(ingest_s, 1),
            "search_ms": round(search_ms),
            "rss_idle_mb": round(_rss_mb(process.pid)),
            "rss_peak_ingest_mb": round(peak_mb),
        }
    finally:
        memory_server.terminate(process)


def main() -> int:
    load_env()
    results = [
        measure(name, model, FIRST_PORT + index)
        for index, (name, model) in enumerate(MODELS.items())
    ]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
