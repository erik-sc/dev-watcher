from __future__ import annotations
import re

_PATTERNS: list[re.Pattern] = [
    # Anthropic keys
    re.compile(r'sk-ant-[a-zA-Z0-9\-_]{20,}'),
    # OpenAI keys (including sk-proj- format)
    re.compile(r'sk-[a-zA-Z0-9\-_]{20,}'),
    # JWT tokens (header.payload.signature)
    re.compile(r'eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+'),
    # AWS access keys (AKIA, ASIA, AROA, ABIA, ACCA)
    re.compile(r'(?:AKIA|ASIA|AROA|ABIA|ACCA)[0-9A-Z]{16}'),
    # GitHub tokens (ghp_, gho_, ghs_, ghr_, ghu_, gha_)
    re.compile(r'gh[pousra]_[a-zA-Z0-9]{36,}'),
    # Bearer tokens
    re.compile(r'(?i)bearer\s+[a-zA-Z0-9._\-]{20,}'),
    # Connection strings with passwords (preserve ://)
    re.compile(r'(?<=://)[^:@\s]+:[^@\s]+(?=@)'),
    # Generic key=value patterns for sensitive fields (quoted values only)
    re.compile(
        r'(?i)(?:api_?key|secret|token|password|passwd|pwd)\s*[=:]\s*'
        r'["\'][\w+/=.\-]{8,}["\']'
    ),
]


def sanitize(text: str) -> str:
    for pattern in _PATTERNS:
        text = pattern.sub('[REDACTED]', text)
    return text


def _sanitize_value(v) -> object:
    if isinstance(v, str):
        return sanitize(v)
    elif isinstance(v, dict):
        return sanitize_dict(v)
    elif isinstance(v, list):
        return [_sanitize_value(item) for item in v]
    return v


def sanitize_dict(d: dict) -> dict:
    return {k: _sanitize_value(v) for k, v in d.items()}
