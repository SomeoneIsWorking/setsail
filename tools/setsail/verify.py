"""setsail's normal verifier.

Each gate reports what it examined even when it passes, so a gate that looked
at nothing cannot be mistaken for a gate that found nothing wrong.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

DEFAULT_LINE_CAP = 1200
CRITICAL_LINE_CAP = 2000
FIRST_PARTY_ROOTS: tuple[str, ...] = ("src", "tools", "tests")
LEGACY_LIMITS: dict[str, int] = {}
"""Pinned sizes for known oversized files. Entries are removed as code is
extracted, never raised to land a change."""


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    examined: int
    detail: str

    def render(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}] {self.name}: examined {self.examined}\n{self.detail}".rstrip()


def _sources(root: Path) -> list[Path]:
    found: list[Path] = []
    for relative in FIRST_PARTY_ROOTS:
        directory = root / relative
        if directory.is_dir():
            for suffix in ("*.py", "*.cpp", "*.h", "*.hpp"):
                found.extend(sorted(directory.rglob(suffix)))
    entry = root / "bootstrap.py"
    if entry.is_file():
        found.append(entry)
    return found


def check_source_sizes(root: Path) -> list[str]:
    findings: list[str] = []
    for source in _sources(root):
        relative = source.relative_to(root).as_posix()
        lines = len(source.read_text(encoding="utf-8", errors="replace").splitlines())
        cap = LEGACY_LIMITS.get(relative, DEFAULT_LINE_CAP)
        if lines > cap:
            severity = "CRITICAL " if lines >= CRITICAL_LINE_CAP else ""
            findings.append(
                f"{severity}{relative}: {lines} lines exceeds the {cap}-line limit; "
                "split by responsibility rather than raising the limit"
            )
    return findings


def _uv(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--frozen", "--group", "dev", *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


def gate_lint(root: Path) -> GateResult:
    result = _uv(root, "ruff", "check", "tools", "tests", "bootstrap.py")
    return GateResult(
        "python lint (ruff)",
        result.returncode == 0,
        len([s for s in _sources(root) if s.suffix == ".py"]),
        (result.stdout + result.stderr).strip(),
    )


def check_format(root: Path, targets: list[Path]) -> GateResult:
    """`ruff format --check` over `targets`, with the formatter `root` locks."""
    result = _uv(root, "ruff", "format", "--check", *(str(target) for target in targets))
    return GateResult(
        "python format (ruff format --check)",
        result.returncode == 0,
        len(targets),
        (result.stdout + result.stderr).strip(),
    )


def gate_format(root: Path) -> GateResult:
    return check_format(root, [root / "tools", root / "tests", root / "bootstrap.py"])


def gate_tests(root: Path) -> GateResult:
    result = _uv(root, "python", "-m", "pytest", "-q")
    output = (result.stdout + result.stderr).strip()
    return GateResult(
        "python tests (pytest)",
        result.returncode == 0,
        len(sorted((root / "tests").rglob("test_*.py"))),
        output.splitlines()[-1] if output else "(no output)",
    )


def gate_launcher_is_a_shim(root: Path) -> GateResult:
    """run.sh must stay a shim; launcher policy belongs in Python."""
    script = root / "run.sh"
    if not script.is_file():
        return GateResult("launcher is a shim", False, 0, f"{script} does not exist")
    body = [
        line.strip()
        for line in script.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    too_long = len(body) > 5
    hands_off = any(line.startswith("exec uv run --frozen python bootstrap.py") for line in body)
    detail = "\n".join(
        ([f"run.sh has {len(body)} non-comment lines; keep it a shim"] if too_long else [])
        + (
            []
            if hands_off
            else ['run.sh must hand straight to: exec uv run --frozen python bootstrap.py "$@"']
        )
    )
    return GateResult("launcher is a shim", not too_long and hands_off, len(body), detail)


def gate_structure(root: Path) -> GateResult:
    findings = check_source_sizes(root)
    return GateResult(
        "structure (source size limits)",
        not findings,
        len(_sources(root)),
        "\n".join(findings),
    )


GATES = (gate_lint, gate_format, gate_tests, gate_launcher_is_a_shim, gate_structure)


def run_all(root: Path) -> list[GateResult]:
    return [gate(root) for gate in GATES]
