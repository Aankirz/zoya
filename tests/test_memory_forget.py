"""P3c: a memory deleted in the Hub is deleted from every copy (§9.8, D37)."""

import json
from types import SimpleNamespace

import pytest

from zoya.tools import memory

KEPT = {
    "id": "a1",
    "at": "2026-09-20T10:00:00+00:00",
    "category": "preference",
    "content": "Likes tea",
}
GONE = {
    "id": "b2",
    "at": "2026-09-21T10:00:00+00:00",
    "category": "contact",
    "content": "Mom is Asha",
}


class FakeDocuments:
    def __init__(self, fail_custom: bool = False) -> None:
        self.deleted: list[str] = []
        self.fail_custom = fail_custom

    def delete(self, id: str) -> None:  # noqa: A002 — the SDK's own parameter name
        if self.fail_custom and id == GONE["id"]:
            raise RuntimeError("404")
        self.deleted.append(id)

    def list(self, **_options: object) -> SimpleNamespace:
        docs = [
            SimpleNamespace(id="sm-legacy", content=GONE["content"]),
            SimpleNamespace(id="sm-other", content="x"),
        ]
        return SimpleNamespace(memories=docs)


class FakeDynamo:
    def __init__(self) -> None:
        self.deleted: list[dict] = []

    def delete_item(self, **request: object) -> None:
        self.deleted.append(request["Key"])


@pytest.fixture
def copies(tmp_path, monkeypatch: pytest.MonkeyPatch):  # noqa: ANN201
    local = tmp_path / "memory.json"
    local.write_text(json.dumps([KEPT, GONE]))
    monkeypatch.setattr(memory, "MEMORY_LOCAL_FILE", local)
    dynamo = FakeDynamo()
    monkeypatch.setattr(memory.aws, "client", lambda _name: dynamo)
    return local, dynamo


def _supermemory(monkeypatch: pytest.MonkeyPatch, documents: FakeDocuments) -> None:
    monkeypatch.setattr(memory, "_supermemory", lambda: SimpleNamespace(documents=documents))


def test_forget_removes_the_memory_from_every_copy(copies, monkeypatch) -> None:  # noqa: ANN001
    local, dynamo = copies
    documents = FakeDocuments()
    _supermemory(monkeypatch, documents)
    assert memory.forget(GONE["id"]) is True
    assert json.loads(local.read_text()) == [KEPT]
    assert documents.deleted == [GONE["id"]]
    assert dynamo.deleted == [
        {"pk": {"S": f"memory#{memory.MEMORY_USER_TAG}"}, "sk": {"S": f"{GONE['at']}#{GONE['id']}"}}
    ]


def test_forget_finds_a_memory_saved_before_custom_ids(copies, monkeypatch) -> None:  # noqa: ANN001
    documents = FakeDocuments(fail_custom=True)
    _supermemory(monkeypatch, documents)
    assert memory.forget(GONE["id"]) is True
    assert documents.deleted == ["sm-legacy"]


def test_forget_reports_failure_when_supermemory_keeps_it(
    copies, monkeypatch
) -> None:  # noqa: ANN001
    local, _ = copies

    class Stuck(FakeDocuments):
        def delete(self, id: str) -> None:  # noqa: A002
            raise RuntimeError("down")

    _supermemory(monkeypatch, Stuck())
    assert memory.forget(GONE["id"]) is False
    assert json.loads(local.read_text()) == [KEPT, GONE]


def test_forget_of_an_unknown_id_changes_nothing(copies, monkeypatch) -> None:  # noqa: ANN001
    local, dynamo = copies
    _supermemory(monkeypatch, FakeDocuments())
    assert memory.forget("nope") is False
    assert json.loads(local.read_text()) == [KEPT, GONE]
    assert dynamo.deleted == []


def test_new_memories_carry_their_id_to_supermemory(copies, monkeypatch) -> None:  # noqa: ANN001
    added: list[dict] = []
    monkeypatch.setattr(
        memory, "_supermemory", lambda: SimpleNamespace(add=lambda **kw: added.append(kw))
    )
    monkeypatch.setattr(
        memory.threading, "Thread", lambda **_kw: SimpleNamespace(start=lambda: None)
    )
    memory.remember("I like masala chai")
    saved = json.loads(copies[0].read_text())[-1]
    assert added[0]["custom_id"] == saved["id"]
