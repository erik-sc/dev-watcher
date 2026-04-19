from __future__ import annotations
import re

_PATTERNS: list[re.Pattern] = [
    # Anthropic keys
    re.compile(r'sk-ant-[a-zA-Z0-9\-_]{20,}'),
    # OpenAI keys
    re.compile(r'sk-[a-zA-Z0-9]{20,}'),
    # JWT tokens (header.payload.signature)
    re.compile(r'eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+'),
    # AWS access keys
    re.compile(r'AKIA[0-9A-Z]{16}'),
    # GitHub tokens (ghp_, gho_, ghs_, ghr_, ghu_)
    re.compile(r'gh[pousr]_[a-zA-Z0-9]{36,}'),
    # Bearer tokens
    re.compile(r'(?i)bearer\s+[a-zA-Z0-9._\-]{20,}'),
    # Connection strings with passwords
    re.compile(r'://[^:@\s]+:[^@\s]+@'),
    # Generic key=value patterns for sensitive fields
    re.compile(
        r'(?i)(?:api_?key|secret|token|password|passwd|pwd)\s*[=:]\s*'
        r'["\']?[\w+/=.\-]{8,}["\']?'
    ),
]


def sanitize(text: str) -> str:
    for pattern in _PATTERNS:
        text = pattern.sub('[REDACTED]', text)
    return text


def sanitize_dict(d: dict) -> dict:
    result: dict = {}
    for k, v in d.items():
        if isinstance(v, str):
            result[k] = sanitize(v)
        elif isinstance(v, dict):
            result[k] = sanitize_dict(v)
        elif isinstance(v, list):
            result[k] = [sanitize(item) if isinstance(item, str) else item for item in v]
        else:
            result[k] = v
    return result
