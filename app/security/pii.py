"""PII detection and redaction (regex-based, fast, no model download)."""
from __future__ import annotations

import re
from dataclasses import dataclass

PATTERNS: dict[str, re.Pattern] = {
    "EMAIL": re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    ),
    "PHONE": re.compile(
        r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    ),
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "CREDIT_CARD": re.compile(r"\b(?:\d[ -]?){13,16}\b"),
    "API_KEY": re.compile(
        r"\b(?:sk[_-]|gsk[_-]|AKIA|ghp_|xoxb-|shpss_|pypi-)[A-Za-z0-9_\-]{16,}\b"
    ),
    "IP_ADDRESS": re.compile(
        r"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}"
        r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b"
    ),
}


@dataclass
class RedactionResult:
    text: str
    counts: dict[str, int]

    @property
    def total(self) -> int:
        return sum(self.counts.values())


def redact(text: str) -> RedactionResult:
    """Replace PII with typed placeholders. Returns text + per-type counts."""
    if not text:
        return RedactionResult(text=text, counts={})
    counts: dict[str, int] = {}
    out = text
    for name, pattern in PATTERNS.items():
        out, n = pattern.subn(f"<{name}>", out)
        if n:
            counts[name] = n
    return RedactionResult(text=out, counts=counts)


def redact_dict(d: dict) -> tuple[dict, int]:
    """Recursively redact string values in a dict/list structure."""
    total = 0

    def _walk(x):
        nonlocal total
        if isinstance(x, str):
            r = redact(x)
            total += r.total
            return r.text
        if isinstance(x, list):
            return [_walk(v) for v in x]
        if isinstance(x, dict):
            return {k: _walk(v) for k, v in x.items()}
        return x

    return _walk(d), total