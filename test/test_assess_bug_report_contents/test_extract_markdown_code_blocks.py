"""Tests for markdown code block extraction."""

from rtl_bug_detection_llm_experiments.assess_bug_report_contents import (
    extract_markdown_code_blocks,
)


def test_single_code_block() -> None:
    """Test extraction of a single code block."""
    markdown = """
Some text before
```
def hello():
    print("Hello")
```
Some text after
"""
    result = extract_markdown_code_blocks(markdown)
    assert len(result) == 1
    assert result[0] == 'def hello():\n    print("Hello")'


def test_multiple_code_blocks() -> None:
    """Test extraction of multiple code blocks."""
    markdown = """
First block:
```
code1
```
Second block:
```
code2
```
"""
    result = extract_markdown_code_blocks(markdown)
    assert len(result) == 2
    assert result[0] == "code1"
    assert result[1] == "code2"


def test_empty_code_block() -> None:
    """Test extraction of an empty code block."""
    markdown = """
```
```
"""
    result = extract_markdown_code_blocks(markdown)
    assert len(result) == 1
    assert result[0] == ""


def test_no_code_blocks() -> None:
    """Test markdown with no code blocks."""
    markdown = "Just some regular text\nwith no code blocks"
    result = extract_markdown_code_blocks(markdown)
    assert result == []


def test_empty_string() -> None:
    """Test with empty input string."""
    result = extract_markdown_code_blocks("")
    assert result == []


def test_code_block_with_language_identifier() -> None:
    """Test code block with language identifier (e.g., ```python)."""
    markdown = """
```python
def test():
    pass
```
"""
    result = extract_markdown_code_blocks(markdown)
    assert len(result) == 1
    assert result[0] == "def test():\n    pass"


def test_unclosed_code_block() -> None:
    """Test markdown with unclosed code block."""
    markdown = """
```
def incomplete():
print("missing closing backticks")
"""
    result = extract_markdown_code_blocks(markdown)
    assert result == []


def test_nested_backticks_in_code() -> None:
    """Test code block containing backticks that don't start a line."""
    markdown = """
```
x = `command`
not ``` a delimiter
```
"""
    result = extract_markdown_code_blocks(markdown)
    assert len(result) == 1
    assert "x = `command`" in result[0]
    assert "not ``` a delimiter" in result[0]


def test_indented_code_block_markers() -> None:
    """Test code blocks with indented backtick markers."""
    markdown = """
```
  indented code
```
"""
    result = extract_markdown_code_blocks(markdown)
    assert len(result) == 1
    assert result[0] == "  indented code"


def test_whitespace_only_lines_in_code_block() -> None:
    """Test code block with whitespace-only lines."""
    markdown = """
```
line1

line3
```
"""
    result = extract_markdown_code_blocks(markdown)
    assert len(result) == 1
    assert result[0] == "line1\n\nline3"


def test_consecutive_code_blocks() -> None:
    """Test consecutive code blocks with no text between them."""
    markdown = """
```
block1
```
```
block2
```
"""
    result = extract_markdown_code_blocks(markdown)
    assert len(result) == 2
    assert result[0] == "block1"
    assert result[1] == "block2"


def test_preserves_indentation() -> None:
    """Test that indentation within code blocks is preserved."""
    markdown = """
```
def outer():
    def inner():
        pass
```
"""
    result = extract_markdown_code_blocks(markdown)
    assert len(result) == 1
    assert "    def inner():" in result[0]
    assert "        pass" in result[0]


def test_backticks_with_extra_characters() -> None:
    """Test backticks followed by extra characters (language identifiers)."""
    markdown = """
```javascript
const x = 5;
```

```python
y = 10
```
"""
    result = extract_markdown_code_blocks(markdown)
    assert len(result) == 2
    assert result[0] == "const x = 5;"
    assert result[1] == "y = 10"


def test_mixed_content() -> None:
    """Test realistic markdown with mixed content."""
    markdown = """
# My Document

Here's some Python code:

```python
def fibonacci(n):
if n <= 1:
    return n
return fibonacci(n-1) + fibonacci(n-2)
```

And here's some JavaScript:

```javascript
function factorial(n) {
return n <= 1 ? 1 : n * factorial(n - 1);
}
```

End of document.
"""
    result = extract_markdown_code_blocks(markdown)
    assert len(result) == 2
    assert "def fibonacci(n):" in result[0]
    assert "function factorial(n)" in result[1]
