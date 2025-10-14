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


def test_remove_chunk_of_original() -> None:
    """Test that removing a chunk from the original is detected with a null new_version.

    This case isn't particularly easy to check that the bug logic is correct.
    """
    base_design = """
// 3:8 Decoder
// Decodes a 3-bit input into one of 8 output lines.
// Optional enable input for controlling decoder operation.

module decoder_3to8 (
    input wire [2:0] in,    // 3-bit input
    input wire enable,      // Enable signal (active high)
    output reg [7:0] out    // 8-bit output (one-hot encoded)
);
    always @(*) begin
        if (enable) begin
            case (in)
                3'b000: out = 8'b00000001;  // Output 0 active
                3'b001: out = 8'b00000010;  // Output 1 active
                3'b010: out = 8'b00000100;  // Output 2 active
                3'b011: out = 8'b00001000;  // Output 3 active
                3'b100: out = 8'b00010000;  // Output 4 active
                3'b101: out = 8'b00100000;  // Output 5 active
                3'b110: out = 8'b01000000;  // Output 6 active
                3'b111: out = 8'b10000000;  // Output 7 active
                default: out = 8'b00000000;
            endcase
        end else begin
            out = 8'b00000000;  // All outputs low when disabled
        end
    end

endmodule
"""

    # Remove the 17th line.
    assert (
        base_design.splitlines()[16].strip()
        == "3'b011: out = 8'b00001000;  // Output 3 active"
    )
    buggy_design = "\n".join(
        base_design.splitlines()[0:16] + base_design.splitlines()[18:]
    )

    diffs = get_str_diff_chunks(base_design, buggy_design)
    assert len(diffs) == 1, f"Should find 1 diff chunk, got {len(diffs)}: {diffs}"
    assert "3'b011: out = 8'b00001000;" in diffs[0].old_version
    assert "// Output 3 active" in diffs[0].old_version
    assert diffs[0].new_version.strip() == "", (
        "New version should be empty because it was a strict removal"
    )
