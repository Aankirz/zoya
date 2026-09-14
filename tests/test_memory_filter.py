"""Done-when #7: memory_add never stores card numbers, OTPs or passwords (§9.8, §12.3)."""

import pytest

from zoya.tools import ToolError, memory


@pytest.mark.parametrize(
    "text",
    [
        "My card number is 4111 1111 1111 1111",
        "card 4111-1111-1111-1111 expires soon",
        "5500005555555559",
        "Remember the OTP 482913",
        "my one-time password is 5521",
        "the verification code was 90210",
        "My Amazon password is hunter2",
        "UPI PIN 1234",
        "my pin is 4321",
        "CVV 123",
        "debit card ending 4242",
        "card expiry 09/28",
        "the code is four eight two nine one three",
        "netbanking login is ravi and ravi@123",
    ],
)
def test_secrets_are_rejected(text):
    assert memory.secret_reason(text) is not None


@pytest.mark.parametrize(
    "text",
    [
        "My usual groceries are 2 litres of Amul milk, a dozen eggs and brown bread",
        "Home address: 12 MG Road, Indiranagar, Bengaluru, pin code 560038",
        "Rahul Sharma's phone is 9876543210",
        "Ordered usual groceries on 2026-09-14 for ₹412",
        "I like spinach and pineapple",
        "Order 402-1234567-7654321 arrives tomorrow",
    ],
)
def test_ordinary_memories_pass(text):
    assert memory.secret_reason(text) is None


def test_memory_add_refuses_before_anything_is_stored(monkeypatch):
    stored = []
    monkeypatch.setattr(memory, "_save_local", stored.append)
    monkeypatch.setattr(memory, "_supermemory", lambda: pytest.fail("reached Supermemory"))

    with pytest.raises(ToolError):
        memory.remember("my card is 4111 1111 1111 1111")

    assert stored == []
