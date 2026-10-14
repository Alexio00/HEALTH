"""Безопасные, неавторизующие проверки входного контура ChatGPT Writer.

Модуль не предоставляет медицинскую запись, не подтверждает личность пользователя,
не читает секреты и не заменяет действующий health_writer/chat_worker.py.
Перед использованием в production требуется аутентифицированный OAuth/MCP шлюз.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

_KEY = re.compile(r"writer-[a-f0-9]{32}\Z")
_DIGEST = re.compile(r"[a-f0-9]{64}\Z")
_SHA = re.compile(r"[a-f0-9]{40}\Z")

class GatewayBlocked(ValueError):
    """Непубликуемая техническая блокировка; сообщение не содержит данных пациента."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code

def _exact(data: Mapping[str, Any], keys: frozenset[str], error: str) -> None:
    """Only a plain decoded JSON object with an exact key set is accepted.

    No arbitrary Mapping implementations, coercion or extra metadata from an
    untrusted caller can influence the protocol boundary.
    """
    if type(data) is not dict or data.keys() != keys:
        raise GatewayBlocked(error)

def workflow_envelope(request_key: str, kind: str, digest: str) -> dict[str, str]:
    """Только три непрозрачных параметра GitHub OIDC; никаких медицинских данных."""
    if type(request_key) is not str or not _KEY.fullmatch(request_key):
        raise GatewayBlocked("invalid_request_key")
    if type(kind) is not str or kind not in ("intent", "candidate"):
        raise GatewayBlocked("invalid_approval_kind")
    if type(digest) is not str or not _DIGEST.fullmatch(digest):
        raise GatewayBlocked("invalid_digest")
    return {"request_key": request_key, "kind": kind, "digest": digest}

@dataclass(frozen=True)
class Capability:
    mode: str
    matching_sha: str | None
    reasons: tuple[str, ...]

def capability(readback: Mapping[str, Any]) -> Capability:
    """Сверяет форму наблюдений, но НЕ подтверждает право на запись.

    Положительный результат означает совпадение предъявленных технических
    предусловий, а не подтверждённого владельца или принятого release SHA.
    Даже если все значения True и все SHA совпали, этот результат нельзя
    использовать как authorization/consent для любого mutating RPC.
    Достоверность наблюдений, OAuth identity, exact owner intent/candidate,
    nonce/expiry/replay и отдельные approval receipts проверяет только
    будущий защищённый gateway. Данные модели и пользователя не являются evidence.
    """
    keys = frozenset({
        "backend_active", "writer_enabled", "main_sha", "runtime_sha",
        "workflow_sha", "unfinished_operations", "source_registered",
        "restricted_operator_ready", "independent_verifier_ready",
        "oauth_owner_verified",
    })
    _exact(readback, keys, "capability_evidence_incomplete")
    reasons: list[str] = []
    for key in ("backend_active", "writer_enabled", "source_registered",
                "restricted_operator_ready", "independent_verifier_ready",
                "oauth_owner_verified"):
        if readback[key] is not True:
            reasons.append(key + "_not_verified")
    versions = (readback["main_sha"], readback["runtime_sha"], readback["workflow_sha"])
    if any(not isinstance(v, str) or not _SHA.fullmatch(v) for v in versions):
        reasons.append("invalid_version_pin")
    elif len(set(versions)) != 1:
        reasons.append("version_pin_mismatch")
    unfinished = readback["unfinished_operations"]
    if type(unfinished) is not int or unfinished < 0:
        reasons.append("unfinished_count_invalid")
    elif unfinished:
        reasons.append("another_operation_unfinished")
    return Capability("PRECONDITIONS_MATCH" if not reasons else "READ_ONLY",
                      versions[0] if not reasons else None, tuple(reasons))

def safe_status(result: Mapping[str, Any]) -> dict[str, str]:
    """Минимальный отчёт для технических логов, строго без body_text, Source, URLs."""
    _exact(result, frozenset({"request_key", "state", "result_sha"}), "status_untrusted")
    key = result["request_key"]
    state = result["state"]
    digest = result["result_sha"]
    if type(key) is not str or not _KEY.fullmatch(key):
        raise GatewayBlocked("status_key_invalid")
    if type(state) is not str or state not in ("PREPARED", "COMMITTED_REGISTRY", "VALIDATED", "FINALIZED", "FAILED", "BLOCKED"):
        raise GatewayBlocked("status_state_invalid")
    if type(digest) is not str or not _DIGEST.fullmatch(digest):
        raise GatewayBlocked("status_digest_invalid")
    return {"request_key": key, "state": state, "result_sha": digest}
