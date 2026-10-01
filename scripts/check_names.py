"""Fail if a holy name appears in full anywhere in the repo or the build.

Usage:
  python scripts/check_names.py              # tracked + untracked files, and build/ if present
  python scripts/check_names.py PATH ...     # specific files or directories
  python scripts/check_names.py --git-log    # also scan commit messages

Allowed without a kinui:
  - Halleluyah;
  - occurrences approved as chol in data/annotations/chol_names.json;
  - in unvocalized prose, phrases the detector itself classifies as chol by
    context (e.g. "...the peoples", "other ...").
Findings are reported by type and location, and printed only in masked form.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import names  # noqa: E402
from hebrew import tokenize  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TEXT_EXT = {".json", ".py", ".md", ".html", ".htm", ".js", ".mjs", ".css", ".txt", ".yml",
            ".yaml", ".xml", ".svg", ".webmanifest", ".toml", ".cfg", ".ini", ".j2", ".jinja", ""}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}


def approved_chol_words() -> set[tuple[str, str]]:
    """(word, next word) pairs of approved chol occurrences, from the data itself."""
    allowed = set()
    for f in sorted((ROOT / "data" / "psalms").glob("*.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        for v in doc["verses"]:
            words = tokenize(v["text"])
            for e in v["names"]:
                if e.get("chol"):
                    i = next(w.index for w in words if w.start == e["start"])
                    nxt = words[i + 1].raw(v["text"]) if i + 1 < len(words) else ""
                    allowed.add((v["text"][e["start"]:e["end"]], nxt))
    return allowed


def scan_text(text: str, allowed: set) -> list[tuple[int, str, str]]:
    words = tokenize(text)
    found = []
    for m in names.find_unmasked(text):
        w = words[m.word]
        raw = w.raw(text)
        nxt = words[m.word + 1].raw(text) if m.word + 1 < len(words) else ""
        if (raw, nxt) in allowed:
            continue
        if not w.vocalized and m.chol_reason in ("next-word", "after-kol"):
            continue
        line = text.count("\n", 0, w.start) + 1
        found.append((line, m.type, names.kinui_for(raw, w, m)))
    return found


def iter_files(paths: list[Path]):
    for p in paths:
        if p.is_file():
            yield p
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and not (SKIP_DIRS & set(f.relative_to(p).parts)):
                    yield f


def default_paths() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout.split("\n")
    paths = [ROOT / p for p in out if p]
    build = ROOT / "build"
    if build.is_dir():
        paths.append(build)
    return paths


def main(argv: list[str]) -> int:
    git_log = "--git-log" in argv
    argv = [a for a in argv if a != "--git-log"]
    paths = [Path(a).resolve() for a in argv] or default_paths()
    allowed = approved_chol_words()
    failures = 0
    scanned = 0
    for f in iter_files(paths):
        rel = f.relative_to(ROOT) if f.is_relative_to(ROOT) else f
        for line, t, form in scan_text(str(rel), allowed):
            print(f"{rel}: file name contains {t} (as {form})")
            failures += 1
        if f.suffix.lower() not in TEXT_EXT:
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        scanned += 1
        if f.suffix == ".json":
            try:  # also catch names hidden behind \\u escapes
                text = json.dumps(json.loads(text), ensure_ascii=False, indent=0)
            except json.JSONDecodeError:
                pass
        for line, t, form in scan_text(text, allowed):
            print(f"{rel}:{line}: {t} (should be {form})")
            failures += 1
    if git_log:
        log = subprocess.run(["git", "log", "--format=%H%n%B%x00"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
        for entry in log.split("\0"):
            entry = entry.strip()
            if not entry:
                continue
            sha, _, body = entry.partition("\n")
            for line, t, form in scan_text(body, allowed):
                print(f"commit {sha[:10]}: {t} (should be {form})")
                failures += 1
    if failures:
        print(f"FAIL: {failures} unmasked name(s) in {scanned} files")
        return 1
    print(f"OK: no unmasked names in {scanned} files")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
