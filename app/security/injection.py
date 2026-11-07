"""Prompt injection detection."""
from __future__ import annotations

import re
from dataclasses import dataclass

INJECTION_PATTERNS: list[tuple[str, str]] = [
    (r"ignore\s+(?:all\s+)?(?:the\s+)?previous\s+instructions", "ignore_previous"),
    (r"ignore\s+(?:all\s+)?above", "ignore_above"),
    (r"disregard\s+(?:all\s+)?(?:the\s+)?previous", "disregard_previous"),
    (r"forget\s+(?:all\s+)?(?:your\s+)?(?:instructions|rules)", "forget_rules"),
    (r"you\s+are\s+now\s+(?:a|an|the)\b", "you_are_now"),
    (r"new\s+instructions?\s*:", "new_instructions"),
    (r"^system\s*:", "system_override"),
    (r"###\s*instruction", "instruction_heading"),
    (r"</?\s*(?:system|assistant|user)\s*>", "role_tags"),
    (r"jailbreak", "jailbreak_keyword"),
    (r"(?:base64|atob|eval)\s*\(", "encoded_payload"),
]


@dataclass
class InjectionCheck:
    is_safe: bool
    reason: str | None
    matched_pattern: str | None


def check_injection(text: str) -> InjectionCheck:
    if not text:
        return InjectionCheck(is_safe=True, reason=None, matched_pattern=None)
    lowered = text.lower()
    for pattern, label in INJECTION_PATTERNS:
        if re.search(pattern, lowered, re.IGNORECASE | re.MULTILINE):
            return InjectionCheck(
                is_safe=False,
                reason=f"injection_pattern:{label}",
                matched_pattern=label,
            )
    return InjectionCheck(is_safe=True, reason=None, matched_pattern=None)