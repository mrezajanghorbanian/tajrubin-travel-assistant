from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
}

BLOCKED_FILENAMES = {
    ".env",
    "id_rsa",
    "id_dsa",
    "id_ed25519",
    "credentials.json",
    "service-account.json",
}

BLOCKED_SUFFIXES = {
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".jks",
    ".keystore",
}

TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".ini",
    ".cfg",
    ".ps1",
    ".sh",
}

PATTERNS = {
    "private_key": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ),
    "aws_access_key": re.compile(
        r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"
    ),
    "github_token": re.compile(
        r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"
    ),
    "generic_bearer_token": re.compile(
        r"Authorization\s*[:=]\s*[\"']?Bearer\s+[A-Za-z0-9._\-]{20,}",
        re.IGNORECASE,
    ),
    "database_url": re.compile(
        r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://"
        r"[^ \t\r\n\"']+",
        re.IGNORECASE,
    ),
    "cloud_metadata_endpoint": re.compile(
        r"\b169\.254\.169\.254\b"
    ),
}

ALLOWED_PATTERN_PATHS = {
    "cloud_metadata_endpoint": {
        Path("tests/test_local_provider_runtime_security.py"),
    },
}


def iter_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue

        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue

        yield path


def scan_filename(path: Path, findings: list[str]) -> None:
    name = path.name.lower()

    if name in BLOCKED_FILENAMES:
        findings.append(
            f"blocked sensitive filename: {path.relative_to(ROOT)}"
        )

    if path.suffix.lower() in BLOCKED_SUFFIXES:
        findings.append(
            f"blocked sensitive file type: {path.relative_to(ROOT)}"
        )


def scan_content(path: Path, findings: list[str]) -> None:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return

    try:
        content = path.read_text(
            encoding="utf-8",
            errors="ignore",
        )
    except OSError:
        return

    relative = path.relative_to(ROOT)

    for name, pattern in PATTERNS.items():
        if not pattern.search(content):
            continue

        allowed_paths = ALLOWED_PATTERN_PATHS.get(name, set())

        if relative in allowed_paths:
            continue

        findings.append(
            f"{name}: {relative}"
        )


def main() -> int:
    findings: list[str] = []

    for path in iter_files():
        scan_filename(path, findings)
        scan_content(path, findings)

    if findings:
        print("PUBLIC REPOSITORY SECURITY GATE FAILED")
        for finding in sorted(set(findings)):
            print(f"- {finding}")
        return 1

    print("PUBLIC REPOSITORY SECURITY GATE PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())