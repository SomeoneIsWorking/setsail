"""The verifier's own gates must fire on the negative case."""

from __future__ import annotations

from pathlib import Path

from setsail.verify import (
    CRITICAL_LINE_CAP,
    DEFAULT_LINE_CAP,
    check_format,
    check_source_sizes,
    gate_launcher_is_a_shim,
)


def test_oversized_source_is_reported_with_its_size(tmp_path: Path) -> None:
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "big.py").write_text("# line\n" * (DEFAULT_LINE_CAP + 3))
    findings = check_source_sizes(tmp_path)
    assert len(findings) == 1
    assert "tools/big.py" in findings[0] and str(DEFAULT_LINE_CAP + 3) in findings[0]


def test_a_file_at_the_cap_passes(tmp_path: Path) -> None:
    """The negative half. A size check that only ever ran against an oversized
    file could be reporting every file and nobody would know."""
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "exact.py").write_text("# line\n" * DEFAULT_LINE_CAP)
    assert check_source_sizes(tmp_path) == []


def test_a_critical_file_is_marked_as_such(tmp_path: Path) -> None:
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "huge.py").write_text("# line\n" * (CRITICAL_LINE_CAP + 1))
    findings = check_source_sizes(tmp_path)
    assert len(findings) == 1
    assert findings[0].startswith("CRITICAL ")


def test_a_missing_launcher_fails_rather_than_passing_quietly(tmp_path: Path) -> None:
    result = gate_launcher_is_a_shim(tmp_path)
    assert not result.passed
    assert "does not exist" in result.detail


def test_a_launcher_that_grew_shell_logic_fails(tmp_path: Path) -> None:
    (tmp_path / "run.sh").write_text(
        "#!/usr/bin/env sh\n"
        + "echo step\n" * 6
        + 'exec uv run --frozen python bootstrap.py "$@"\n'
    )
    result = gate_launcher_is_a_shim(tmp_path)
    assert not result.passed
    assert "shim" in result.detail


def test_the_real_launcher_passes() -> None:
    result = gate_launcher_is_a_shim(Path(__file__).resolve().parent.parent)
    assert result.passed, result.detail


def test_unformatted_python_fails_the_format_gate(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parent.parent
    formatted = tmp_path / "formatted.py"
    formatted.write_text("x = [1, 2]\n")
    assert check_format(root, [formatted]).passed
    packed = tmp_path / "packed.py"
    packed.write_text("x=[1,2]\n")
    result = check_format(root, [packed])
    assert not result.passed
    assert "packed.py" in result.detail
