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
        # Hindi / Hinglish / spoken digits (coordinator review, gap G)
        "मेरा एटीएम पिन ४१११ है",
        "याद रखना मेरा लॉकर कोड ४ १ १ १ है",
        "mera otp 482913 hai",
        "locker code is 4111",
        "मेरा ओटीपी चार आठ दो नौ है",
        "मेरा पासवर्ड राम123 है",
        "कार्ड नंबर ४१११ ११११ ११११ ११११",
        "double four double one",
        "remember four four one one",
        "एक दो तीन चार",
        "4 8 2 9 1 3",
        "５５００００５５５５５５５５５９",
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
        "मेरा पिन कोड 560038 है",
        "My usual: two litres milk, one dozen eggs",
        "The dress code for the wedding is ethnic",
        "Ordered 2 kg rice and 1 kg dal for ₹243",
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
