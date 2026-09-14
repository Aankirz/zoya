"""Parsers (D37): reminder times, document read-backs and edits, Excel totals, share recipients."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from zoya.tools import ToolError, office, reminders, share

NOW = datetime(2026, 9, 14, 21, 30, 15, tzinfo=ZoneInfo("Asia/Kolkata"))


@pytest.mark.parametrize(
    ("in_minutes", "at_time", "expected"),
    [
        (2, "", datetime(2026, 9, 14, 21, 32, 15)),
        (0, "22:00", datetime(2026, 9, 14, 22, 0)),
        (0, "9 pm", datetime(2026, 9, 15, 21, 0)),  # 9 pm already passed today → tomorrow
        (0, "9:45am", datetime(2026, 9, 15, 9, 45)),
        (0, "12 am", datetime(2026, 9, 15, 0, 0)),
    ],
)
def test_reminder_times(in_minutes, at_time, expected):
    when = reminders.reminder_time(NOW, in_minutes, at_time)

    assert when.replace(tzinfo=None) == expected


@pytest.mark.parametrize(
    ("in_minutes", "at_time"), [(0, "25:00"), (0, "13 pm"), (-5, ""), (5, "9 pm"), (0, "soon")]
)
def test_impossible_reminder_times_are_refused(in_minutes, at_time):
    with pytest.raises(ToolError):
        reminders.reminder_time(NOW, in_minutes, at_time)


def test_missing_schedule_group_is_said_plainly(monkeypatch):
    class Missing(Exception):
        response = {"Error": {"Code": "ResourceNotFoundException"}}

    def create_schedule(**_):
        raise Missing()

    monkeypatch.setattr(
        reminders.aws, "client", lambda _name: SimpleNamespace(create_schedule=create_schedule)
    )
    monkeypatch.setattr(reminders, "_speak", lambda _text: None)

    said = reminders.set_reminder("drink water", in_minutes=2)

    assert said.endswith(reminders.EMAIL_NOT_SET_UP + ".") and "drink water" in said


def test_the_email_schedule_is_one_time_in_ist_and_deletes_itself(monkeypatch):
    calls = []
    monkeypatch.setattr(
        reminders.aws,
        "client",
        lambda _name: SimpleNamespace(create_schedule=lambda **kw: calls.append(kw)),
    )
    monkeypatch.setattr(reminders, "_speak", lambda _text: None)

    reminders.set_reminder("drink water", in_minutes=2)

    request = calls[0]
    assert request["ScheduleExpression"].startswith("at(")
    assert request["ScheduleExpressionTimezone"] == "Asia/Kolkata"
    assert request["ActionAfterCompletion"] == "DELETE"
    assert request["Target"]["Arn"].endswith(":zoya-alerts")


def test_replace_append_and_delete_parts():
    items = ["a", "b", "c"]

    assert office.replace_item(items, 2, "", "B") == ["a", "B", "c"]
    assert office.replace_item(items, 4, "", "d") == ["a", "b", "c", "d"]
    assert office.replace_item(items, 1, "DELETE", None) == ["b", "c"]
    with pytest.raises(ToolError):
        office.replace_item(items, 6, "", "x")


def test_excel_sheet_has_a_real_sum_formula_and_reads_back_rows_and_total(tmp_path):
    table = office.Table(
        "Monthly Expenses",
        ["Category", "Amount"],
        [["Rent", 15000], ["Groceries", "₹4,200"], ["Internet", 999]],
        ["Amount"],
    )
    path = tmp_path / "expenses.xlsx"
    office.write_table(table, path)

    from openpyxl import load_workbook

    last = list(load_workbook(path).active.rows)[-1]
    back = office.read_table_file(path)

    assert [c.value for c in last] == ["Total", "=SUM(B2:B4)"]
    assert office.table_summary(back).endswith("3 rows; total Amount 20,199.")
    assert office.row_text(back, 3) == "Row 3: Category Internet, Amount 999."


@pytest.mark.parametrize("kind", ["pptx", "docx", "pdf", "md"])
def test_documents_read_back_their_structure(tmp_path, kind):
    doc = office.Doc(
        "Renewable Energy",
        [
            {"title": "Solar", "lines": ["Sunlight to power"]},
            {"title": "Wind", "lines": ["Turbines"]},
        ],
    )
    path = tmp_path / f"deck.{kind}"
    office.write_document(doc, path)

    back = office.read_document_file(path)

    assert [part["title"] for part in back.parts][-2:] == ["Solar", "Wind"]
    assert "Turbines" in office.part_text(back, len(back.parts), "slide")


def test_share_recipients_are_names_never_guessed_addresses(monkeypatch):
    monkeypatch.setattr(share, "SHARE_CONTACTS", ("sister",))
    monkeypatch.delenv(share.SHARE_TEST_ENV, raising=False)

    topic, attributes, spoken = share.recipient_route("my sister")

    assert topic.endswith(":zoya-shares") and spoken == "your sister"
    assert attributes["recipient"]["StringValue"] == "sister"
    with pytest.raises(ToolError):
        share.recipient_route("rahul@example.com")
