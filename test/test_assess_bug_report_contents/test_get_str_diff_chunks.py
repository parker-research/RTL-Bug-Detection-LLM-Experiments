"""Tests for assessing bug report contents."""

from rtl_bug_detection_llm_experiments.assess_bug_report_contents import (
    get_str_diff_chunks,
)


def test_multiple_chunks_separated_by_unchanged_lines() -> None:
    """Test that diffs are split when 3+ unchanged lines separate them."""
    old = """def hello():
    print("Hello")
    x = 1
    y = 2
    z = 3
    return x + y + z

def goodbye():
    print("Goodbye")"""

    new = """def hello():
    print("Hi there")
    x = 1
    y = 2
    z = 3
    return x + y + z

def goodbye():
    print("See you later")"""

    diffs = get_str_diff_chunks(old, new)

    assert len(diffs) == 2, "Should find 2 separate diff chunks"
    assert "Hello" in diffs[0].old_version
    assert "Hi there" in diffs[0].new_version
    assert "Goodbye" in diffs[1].old_version
    assert "See you later" in diffs[1].new_version


def test_single_chunk_with_few_unchanged_lines() -> None:
    """Test that diffs remain in one chunk with fewer than 3 unchanged lines."""
    old = """line1
line2
line3
line4"""

    new = """line1_changed
line2
line3
line4_changed"""

    diffs = get_str_diff_chunks(old, new)

    assert len(diffs) == 1, "Should find 1 diff chunk"


def test_whitespace_normalization() -> None:
    """Test that consecutive whitespaces are ignored in comparison."""
    old = "hello" + ("\n" * 6) + "world"
    new = "hello" + ("\n" * 8) + "world"

    diffs = get_str_diff_chunks(old, new)

    assert len(diffs) == 0, (
        f"Should find no diffs when only whitespace differs: {diffs}"
    )


def test_no_changes() -> None:
    """Test identical texts return no diffs."""
    text = """def hello():
    print("Hello")
    return True"""

    diffs = get_str_diff_chunks(text, text)

    assert len(diffs) == 0, "Identical texts should have no diffs"


def test_completely_different() -> None:
    """Test completely different texts return single diff."""
    old = "old text"
    new = "new text"

    diffs = get_str_diff_chunks(old, new)

    assert len(diffs) == 1, "Should find 1 diff chunk"
    assert diffs[0].old_version == "old text"
    assert diffs[0].new_version == "new text"
