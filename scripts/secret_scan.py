"""Minimal pre-commit secret scan (stdlib only). CI additionally runs gitleaks.

Scans files git would commit (tracked + untracked-not-ignored). Exit 1 on any finding.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PATTERNS = {
    "anthropic key": re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    "openai-style key": re.compile(r"\bsk-[A-Za-z0-9]{32,}"),
    "aws access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "assigned secret": re.compile(
        r"(?i)\b(?:api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-+/]{20,}"),
}
SKIP_SUFFIXES = {".png", ".jpg", ".pdf", ".ttf", ".wav", ".lock"}


def files() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"],
                         capture_output=True, text=True, check=True).stdout
    return [Path(p) for p in out.splitlines() if p]


def main() -> int:
    findings = []
    for path in files():
        if path.name == ".env":
            findings.append((path, 0, ".env must never be committed"))
            continue
        if path.suffix in SKIP_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for name, pat in PATTERNS.items():
                if pat.search(line) and "secret-scan: allow" not in line:
                    findings.append((path, lineno, name))
    for path, lineno, name in findings:
        print(f"{path}:{lineno}: possible {name}")
    print(f"secret scan: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
