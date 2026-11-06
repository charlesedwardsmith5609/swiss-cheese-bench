"""Seeded-defect fixtures: loading, diff generation and validation.

Threading: none. Everything here is synchronous, single-threaded file I/O plus bounded
subprocess calls to git. There is no shared mutable state.
"""

from __future__ import annotations

import json
import shutil
import subprocess  # noqa: S404 - git is invoked with fixed argument lists, never a shell
import sys
import tempfile
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

GIT_TIMEOUT_S = 30
MAX_FIXTURES = 1000
MAX_FILE_BYTES = 256 * 1024
LANGUAGES = frozenset({"python", "go", "terraform"})


class FixtureError(Exception):
    """A fixture is malformed or its ground truth does not match its diff."""


class Category(StrEnum):
    UNRELATED_DELETION = "unrelated_deletion"
    DROPPED_REQUIREMENT = "dropped_requirement"
    TEST_BYPASSES_ROUTE = "test_bypasses_route"
    VALIDATION_DISABLED = "validation_disabled"
    HARDCODED_EXPECTED = "hardcoded_expected"
    SWALLOWED_ERROR = "swallowed_error"
    SECRET_LOGGED = "secret_logged"  # noqa: S105 - a category name, not a credential
    OVERBROAD_IAM = "overbroad_iam"
    NONE = "none"


DEFECT_CATEGORIES = tuple(c for c in Category if c is not Category.NONE)


@dataclass(frozen=True)
class Label:
    category: Category
    file: str | None = None
    description: str | None = None
    evidence: str | None = None


@dataclass(frozen=True)
class Fixture:
    id: str
    language: str
    task: str
    label: Label
    diff: str
    base_dir: Path
    after_dir: Path


@dataclass
class ParsedDiff:
    """Added and removed hunk lines per changed path (file headers excluded)."""

    added: dict[str, list[str]] = field(default_factory=dict)
    removed: dict[str, list[str]] = field(default_factory=dict)

    @property
    def paths(self) -> set[str]:
        return set(self.added) | set(self.removed)


def parse_diff(text: str) -> ParsedDiff:
    parsed = ParsedDiff()
    current: str | None = None
    in_hunk = False
    for line in text.splitlines():
        if line.startswith("diff --git "):
            current = None
            in_hunk = False
            parts = line.split(" ")
            if len(parts) >= 4 and parts[3].startswith("b/"):
                current = parts[3][2:]
                parsed.added.setdefault(current, [])
                parsed.removed.setdefault(current, [])
        elif line.startswith("@@"):
            in_hunk = True
        elif current is not None and in_hunk:
            if line.startswith("+"):
                parsed.added[current].append(line[1:])
            elif line.startswith("-"):
                parsed.removed[current].append(line[1:])
    return parsed


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(  # noqa: S603
            ["git", "-c", "user.name=bench", "-c", "user.email=bench@example.invalid", *args],  # noqa: S607
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_S,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise FixtureError(f"git {args[0]} timed out after {GIT_TIMEOUT_S}s") from exc


def _copy_tree(src: Path, dst: Path) -> None:
    for item in src.rglob("*"):
        if item.is_file():
            target = dst / item.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(item, target)


def make_diff(base_dir: Path, after_dir: Path) -> str:
    """Unified diff (-U8) from base_dir to after_dir with root-relative a/ b/ headers."""
    with tempfile.TemporaryDirectory(prefix="scb-diff-") as tmp:
        work = Path(tmp)
        for args in (["init", "-q"], ["config", "core.autocrlf", "false"]):
            res = _run_git(args, work)
            if res.returncode != 0:
                raise FixtureError(f"git {args[0]} failed: {res.stderr.strip()}")
        _copy_tree(base_dir, work)
        for args in (["add", "-A"], ["commit", "-q", "-m", "base", "--allow-empty"]):
            res = _run_git(args, work)
            if res.returncode != 0:
                raise FixtureError(f"git {args[0]} failed: {res.stderr.strip()}")
        for item in work.iterdir():
            if item.name == ".git":
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        _copy_tree(after_dir, work)
        _run_git(["add", "-A"], work)
        res = _run_git(["diff", "--cached", "-U8", "--no-color", "--no-ext-diff"], work)
        if res.returncode != 0:
            raise FixtureError(f"git diff failed: {res.stderr.strip()}")
        return res.stdout


def _read_json(path: Path, fixture_id: str) -> dict[str, object]:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            raise FixtureError(f"{fixture_id}: {path.name} exceeds {MAX_FILE_BYTES} bytes")
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FixtureError(f"{fixture_id}: missing {path.name}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
        raise FixtureError(f"{fixture_id}: cannot read {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise FixtureError(f"{fixture_id}: {path.name} must be a JSON object")
    return data


def _field_str(data: dict[str, object], key: str, fixture_id: str, fname: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise FixtureError(f"{fixture_id}: {fname} field '{key}' must be a non-empty string")
    return value


def _opt_str(data: dict[str, object], key: str, fixture_id: str) -> str | None:
    if key not in data or data[key] is None:
        return None
    return _field_str(data, key, fixture_id, "label.json")


def _load_label(data: dict[str, object], fixture_id: str) -> Label:
    raw = _field_str(data, "category", fixture_id, "label.json")
    try:
        category = Category(raw)
    except ValueError as exc:
        raise FixtureError(f"{fixture_id}: unknown category '{raw}'") from exc
    file = _opt_str(data, "file", fixture_id)
    description = _opt_str(data, "description", fixture_id)
    evidence = _opt_str(data, "evidence", fixture_id)
    present = [v is not None for v in (file, description, evidence)]
    if category is Category.NONE and any(present):
        raise FixtureError(f"{fixture_id}: clean control must not have file/description/evidence")
    if category is not Category.NONE and not all(present):
        raise FixtureError(f"{fixture_id}: defective fixture needs file, description, evidence")
    return Label(category, file, description, evidence)


def validate(fixture: Fixture) -> None:
    """Check that the label is consistent with the diff. Raises FixtureError."""
    if fixture.language not in LANGUAGES:
        raise FixtureError(f"{fixture.id}: unknown language '{fixture.language}'")
    parsed = parse_diff(fixture.diff)
    if not parsed.paths:
        raise FixtureError(f"{fixture.id}: diff changes no files")
    label = fixture.label
    if label.category is Category.NONE:
        return
    assert label.file is not None and label.evidence is not None  # noqa: S101 - narrowed by loader
    if label.file not in parsed.paths:
        raise FixtureError(f"{fixture.id}: label.file '{label.file}' is not a changed path")
    lines = parsed.added[label.file] + parsed.removed[label.file]
    if not any(label.evidence in line for line in lines):
        raise FixtureError(f"{fixture.id}: evidence not found on a changed line of {label.file}")


def load_fixture(directory: Path) -> Fixture:
    fixture_id = directory.name
    meta = _read_json(directory / "meta.json", fixture_id)
    if _field_str(meta, "id", fixture_id, "meta.json") != fixture_id:
        raise FixtureError(f"{fixture_id}: meta.json id does not match directory name")
    language = _field_str(meta, "language", fixture_id, "meta.json")
    task = _field_str(meta, "task", fixture_id, "meta.json")
    label = _load_label(_read_json(directory / "label.json", fixture_id), fixture_id)
    try:
        patch = directory / "diff.patch"
        if patch.stat().st_size > MAX_FILE_BYTES:
            raise FixtureError(f"{fixture_id}: diff.patch exceeds {MAX_FILE_BYTES} bytes")
        diff = patch.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise FixtureError(f"{fixture_id}: cannot read diff.patch: {exc}") from exc
    base, after = directory / "base", directory / "after"
    if not base.is_dir() or not after.is_dir():
        raise FixtureError(f"{fixture_id}: base/ and after/ directories are required")
    fixture = Fixture(fixture_id, language, task, label, diff, base, after)
    validate(fixture)
    return fixture


def load_fixtures(root: Path) -> list[Fixture]:
    if not root.is_dir():
        raise FixtureError(f"fixtures root not found: {root}")
    dirs = sorted(p for p in root.iterdir() if p.is_dir())
    if len(dirs) > MAX_FIXTURES:
        raise FixtureError(f"too many fixtures ({len(dirs)} > {MAX_FIXTURES})")
    return [load_fixture(d) for d in dirs]


def regen(root: Path) -> int:
    """Rewrite diff.patch for every fixture directory under root. Returns the count."""
    count = 0
    for directory in sorted(p for p in root.iterdir() if p.is_dir()):
        diff = make_diff(directory / "base", directory / "after")
        (directory / "diff.patch").write_text(diff, encoding="utf-8", newline="\n")
        count += 1
    return count


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] != "regen":
        print("usage: python -m swiss_cheese_bench.fixtures regen [root]", file=sys.stderr)
        return 2
    root = Path(argv[2]) if len(argv) > 2 else Path("fixtures")
    print(f"regenerated {regen(root)} diffs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
