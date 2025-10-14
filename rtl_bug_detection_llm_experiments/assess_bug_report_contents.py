"""Assessment function(s) for whether a bug report is the "correct" code.

Looks at the part of the code that's been altered from the base code, and checks if the
bug report includes the buggy part.
"""

import difflib
from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class StringDiff:
    """A simple representation of a string diff."""

    old_version: str
    new_version: str


def _normalize_whitespace(text: str) -> str:
    """Normalize consecutive whitespaces to single space."""
    return " ".join(text.split())


def get_str_diff_chunks_v1(old_text: str, new_text: str) -> list[StringDiff]:
    """Find consecutive chunks of diffs between old and new text.

    Splits chunks when there are 3 consecutive lines of unchanged code.
    Ignores consecutive whitespaces when comparing.

    Args:
        old_text: Original text
        new_text: Modified text

    Returns:
        List of StringDiff objects representing diff chunks

    """
    # Split into lines
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    # Get line-by-line diff using SequenceMatcher
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    opcodes = matcher.get_opcodes()

    diffs: list[StringDiff] = []
    current_old: list[str] = []
    current_new: list[str] = []
    unchanged_count = 0

    for tag, i1, i2, j1, j2 in opcodes:
        # Good for debugging: print(f"Opcode: {tag}, old[{i1}:{i2}], new[{j1}:{j2}]")

        if tag == "equal":
            # Check if lines are equal even after normalizing whitespace.
            old_chunk = old_lines[i1:i2]
            new_chunk = new_lines[j1:j2]

            # Verify they're truly equal (ignoring consecutive whitespaces).
            truly_equal: bool = all(
                _normalize_whitespace(o) == _normalize_whitespace(n)
                for o, n in zip(old_chunk, new_chunk, strict=True)
            )

            if truly_equal:
                unchanged_count += len(old_chunk)

                # If we have 3+ consecutive unchanged lines, split the diff.
                if unchanged_count >= 3:
                    if current_old or current_new:
                        diffs.append(
                            StringDiff(
                                old_version="".join(current_old),
                                new_version="".join(current_new),
                            )
                        )
                        current_old = []
                        current_new = []
                    unchanged_count = 0
                else:
                    # Include these unchanged lines in current chunk.
                    current_old.extend(old_chunk)
                    current_new.extend(new_chunk)
            else:
                unchanged_count = 0
                current_old.extend(old_chunk)
                current_new.extend(new_chunk)
        else:
            # Changed, deleted, or inserted lines.
            unchanged_count = 0
            current_old.extend(old_lines[i1:i2])
            current_new.extend(new_lines[j1:j2])

    # Add any remaining diff.
    if current_old or current_new:
        diffs.append(
            StringDiff(
                old_version="".join(current_old),
                new_version="".join(current_new),
            )
        )

    return diffs


def _normalize_lines(text: str) -> list[str]:
    """Normalize lines by stripping extra whitespace for comparison."""
    return [" ".join(line.strip().split()) for line in text.splitlines()]


def get_str_diff_chunks(old_text: str, new_text: str) -> list[StringDiff]:
    """Find consecutive chunks of diffs between old and new text.

    Splits chunks when there are 3 consecutive lines of unchanged code.
    Ignores consecutive whitespaces when comparing.

    Args:
        old_text: Original text
        new_text: Modified text

    Returns:
        List of StringDiff objects representing diff chunks

    """
    old_lines = _normalize_lines(old_text)
    new_lines = _normalize_lines(new_text)
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    diffs: list[StringDiff] = []

    context_threshold = 3
    current_old_chunk: list[str] = []
    current_new_chunk: list[str] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            if i2 - i1 >= context_threshold:
                # If we've accumulated a diff chunk, flush it before resetting.
                if current_old_chunk or current_new_chunk:
                    diffs.append(
                        StringDiff(
                            old_version="\n".join(current_old_chunk).strip(),
                            new_version="\n".join(current_new_chunk).strip(),
                        )
                    )
                    current_old_chunk, current_new_chunk = [], []

            else:
                # Include small context lines in current diff block.
                current_old_chunk.extend(old_lines[i1:i2])
                current_new_chunk.extend(new_lines[j1:j2])
        else:
            current_old_chunk.extend(old_lines[i1:i2])
            current_new_chunk.extend(new_lines[j1:j2])

    # Add final diff block if pending.
    if current_old_chunk or current_new_chunk:
        diffs.append(
            StringDiff(
                old_version="\n".join(current_old_chunk).strip(),
                new_version="\n".join(current_new_chunk).strip(),
            )
        )

    # Remove empty diffs (caused by whitespace-only changes).
    return [d for d in diffs if d.old_version != d.new_version]


def extract_markdown_code_blocks(markdown: str) -> list[str]:
    """Extract code blocks from markdown text.

    Ignores the language specifier after the opening backticks.

    Args:
        markdown: The markdown text to extract code blocks from.

    Returns:
        List of code block contents.

    """
    code_blocks: list[str] = []
    in_code_block: bool = False
    current_block: list[str] = []

    for line in markdown.splitlines():
        if line.strip().startswith("```") and (in_code_block is False):
            in_code_block = True
            current_block = []
        elif line.strip().startswith("```") and (in_code_block is True):
            in_code_block = False
            code_blocks.append("\n".join(current_block))
        elif in_code_block is True:
            current_block.append(line)

    return code_blocks
