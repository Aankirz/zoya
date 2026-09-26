from __future__ import annotations

from functools import cache
from typing import Any

import objc

SECURITY_FRAMEWORK = "/System/Library/Frameworks/Security.framework"
SERVICE = "Zoya"
ERR_SEC_SUCCESS = 0
ERR_SEC_ITEM_NOT_FOUND = -25300
_NAMES = (
    "kSecClass",
    "kSecClassGenericPassword",
    "kSecAttrService",
    "kSecAttrAccount",
    "kSecValueData",
    "kSecReturnData",
    "kSecMatchLimit",
    "kSecMatchLimitOne",
    "kSecReturnAttributes",
)


class KeychainError(Exception):
    pass


@cache
def _security() -> dict[str, Any]:
    bundle = objc.loadBundle("Security", {}, bundle_path=SECURITY_FRAMEWORK)
    found: dict[str, Any] = {}
    objc.loadBundleFunctions(
        bundle,
        found,
        [
            ("SecItemAdd", b"i@o^@"),
            ("SecItemCopyMatching", b"i@o^@"),
            ("SecItemDelete", b"i@"),
            ("SecKeychainSetUserInteractionAllowed", b"iZ"),
        ],
    )
    objc.loadBundleVariables(bundle, found, [(name, b"@") for name in _NAMES])
    return found


def _query(account: str) -> dict:
    sec = _security()
    return {
        sec["kSecClass"]: sec["kSecClassGenericPassword"],
        sec["kSecAttrService"]: SERVICE,
        sec["kSecAttrAccount"]: account,
    }


def read(account: str) -> str:
    sec = _security()
    query = {**_query(account), sec["kSecReturnData"]: True}
    query[sec["kSecMatchLimit"]] = sec["kSecMatchLimitOne"]
    status, data = sec["SecItemCopyMatching"](query, None)
    if status == ERR_SEC_ITEM_NOT_FOUND:
        return ""
    if status != ERR_SEC_SUCCESS:
        raise KeychainError(f"reading the keychain failed with status {status}")
    return bytes(data).decode("utf-8")


def exists(account: str) -> bool:
    sec = _security()
    status, _ = sec["SecItemCopyMatching"](
        {**_query(account), sec["kSecReturnAttributes"]: True}, None
    )
    return status == ERR_SEC_SUCCESS


def readable_without_prompt(account: str) -> bool:
    allow = _security()["SecKeychainSetUserInteractionAllowed"]
    allow(False)
    try:
        read(account)
        return True
    except KeychainError:
        return False
    finally:
        allow(True)


def delete(account: str) -> None:
    status = _security()["SecItemDelete"](_query(account))
    if status not in (ERR_SEC_SUCCESS, ERR_SEC_ITEM_NOT_FOUND):
        raise KeychainError(f"deleting from the keychain failed with status {status}")


def store(account: str, value: str) -> None:
    from Foundation import NSData

    delete(account)
    secret = value.encode("utf-8")
    item = {
        **_query(account),
        _security()["kSecValueData"]: NSData.dataWithBytes_length_(secret, len(secret)),
    }
    status, _ = _security()["SecItemAdd"](item, None)
    if status != ERR_SEC_SUCCESS:
        raise KeychainError(f"saving to the keychain failed with status {status}")
