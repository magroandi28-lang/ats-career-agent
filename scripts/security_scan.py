"""Gyors, determinisztikus titokellenőrzés a verziókezelt fájlokra."""

from pathlib import Path
import re
import subprocess
import sys


SECRET_PATTERNS = {
    "Supabase secret": re.compile(r"sb_secret_[A-Za-z0-9_-]{20,}"),
    "OpenAI API key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    "Google API key": re.compile(r"\bAIza[A-Za-z0-9_-]{30,}"),
    "JWT": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
}
TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".sql",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        check=True,
        capture_output=True,
    )
    return [
        Path(item.decode("utf-8"))
        for item in result.stdout.split(b"\0")
        if item
    ]


def main() -> int:
    findings: list[str] = []
    for path in tracked_files():
        if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                findings.append(f"{path}: lehetséges {name}")

    if findings:
        print("Titokgyanús érték került verziókezelt fájlba:")
        print("\n".join(f"- {finding}" for finding in findings))
        return 1

    print("Nem találtam titokmintát a verziókezelt szövegfájlokban.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
