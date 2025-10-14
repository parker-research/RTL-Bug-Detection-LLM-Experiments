"""Tests of the `assess_bug_report_contents_score()` function.

Note that this is a large "unit" to test. These tests depend on the other functions
called within working correctly.
"""

import pytest

from rtl_bug_detection_llm_experiments.assess_bug_report_contents import (
    assess_bug_report_contents_score,
)


def test_exact_match() -> None:
    """Test that exact matches return score of 1.0."""
    base_code = """
    module counter(
        input clk,
        output reg [7:0] count
    );
        always @(posedge clk) begin
            count <= count + 1;
        end
    endmodule
    """

    buggy_code = """
    module counter(
        input clk,
        output reg [7:0] count
    );
        always @(posedge clk) begin
            count <= count + 2;  // Bug: incrementing by 2 instead of 1
        end
    endmodule
    """

    bug_report = """
# Bug Report: Counter increments incorrectly

The counter module has a bug in the increment logic:

```verilog
count <= count + 2;  // Bug: incrementing by 2 instead of 1
```

Expected behavior: increment by 1
Actual behavior: increments by 2
    """

    score = assess_bug_report_contents_score(base_code, buggy_code, bug_report)
    assert score == 1.0, f"Expected 1.0, got {score}"


def test_no_match() -> None:
    """Test that completely different code returns low score."""
    base_code = """
    always @(posedge clk) begin
        count <= count + 1;
    end
    """

    buggy_code = """
    always @(posedge clk) begin
        count <= count - 1;
    end
    """

    bug_report_1 = """
# Bug Report

Here's some unrelated code:

```verilog
module adder(
    input [7:0] a, b,
    output [7:0] sum
);
    assign sum = a + b;
endmodule
```
    """
    score_1 = assess_bug_report_contents_score(base_code, buggy_code, bug_report_1)
    assert score_1 < 0.4, f"Case 1: Expected low score, got {score_1}"

    bug_report_2 = """
# Bug Report

Here's some unrelated code:

```verilog
assign sum = a + b;
```
    """
    score_2 = assess_bug_report_contents_score(base_code, buggy_code, bug_report_2)
    assert score_2 < 0.25, f"Case 2: Expected low score, got {score_2}"


def test_partial_match_whitespace_difference() -> None:
    """Test that code with different whitespace still matches well."""
    base_code = "always @(posedge clk) count <= count + 1;"

    buggy_code = "always @(posedge clk) count <= count + 2;"

    bug_report = """
```verilog
always @(posedge clk)
    count <= count + 2;
```
    """

    score = assess_bug_report_contents_score(base_code, buggy_code, bug_report)
    assert score >= 0.95, f"Expected high score despite whitespace, got {score}"


def test_similar_code_above_threshold() -> None:
    """Test that very similar code (above threshold) gets full credit."""
    base_code = """
    if (enable) begin
        data_out <= data_in;
    end
    """

    buggy_code = """
    if (enable) begin
        data_out <= ~data_in;  // Bug: inverted data
    end
    """

    bug_report = """
The bug inverts the data:

```verilog
if (enable) begin
    data_out <= ~data_in;  // Bug here
end
```
    """

    score = assess_bug_report_contents_score(
        base_code, buggy_code, bug_report, similarity_threshold=0.8
    )
    assert score >= 0.8, f"Expected score >= 0.8, got {score}"


def test_similar_code_below_threshold() -> None:
    """Test that somewhat similar code gets partial credit."""
    base_code = "assign result = a & b;"
    buggy_code = "assign result = a | b;  // Bug: OR instead of AND"

    bug_report = """
    ```verilog
    assign result = a ^ b;  // Different operator mentioned
    ```
    """

    score = assess_bug_report_contents_score(
        base_code, buggy_code, bug_report, similarity_threshold=0.9
    )
    assert 0.6 < score < 0.9, f"Expected partial credit score, got {score}"


def test_multiple_code_blocks() -> None:
    """Test that function checks all code blocks in report."""
    base_code = "wire valid = (state == IDLE);"
    buggy_code = "wire valid = (state == BUSY);  // Bug: wrong state"

    bug_report = """
# Bug Report

First, here's some unrelated code:
```verilog
reg [1:0] state;
```

And here's the buggy line:
```verilog
wire valid = (state == BUSY);  // Bug: wrong state
```
    """

    score = assess_bug_report_contents_score(base_code, buggy_code, bug_report)
    assert score >= 0.95, f"Expected high score, got {score}"


def test_custom_threshold() -> None:
    """Test that custom threshold affects scoring."""
    base_code = "count <= count + 1;"
    buggy_code = "count <= count + 2;"

    bug_report = """
    ```verilog
    count <= count + 3;  // Somewhat different
    ```
    """

    score_strict = assess_bug_report_contents_score(
        base_code, buggy_code, bug_report, similarity_threshold=0.95
    )
    score_lenient = assess_bug_report_contents_score(
        base_code, buggy_code, bug_report, similarity_threshold=0.6
    )

    assert score_lenient > score_strict, "Lenient threshold should give higher score"


def test_no_diffs_raises_assertion() -> None:
    """Test that identical base and buggy code raises assertion."""
    base_code = "assign out = in;"
    buggy_code = "assign out = in;"
    bug_report = "```verilog\nassign out = in;\n```"

    with pytest.raises(AssertionError, match="No diffs found"):
        assess_bug_report_contents_score(base_code, buggy_code, bug_report)


def test_no_code_blocks_raises_assertion() -> None:
    """Test that bug report without code blocks raises assertion."""
    base_code = "assign out = in;"
    buggy_code = "assign out = ~in;"
    bug_report = "This is a bug report with no code blocks, just text."

    with pytest.raises(AssertionError, match="No code blocks found"):
        assess_bug_report_contents_score(base_code, buggy_code, bug_report)


def test_complex_verilog_module() -> None:
    """Test with a more complex Verilog example."""
    base_code = """
module fifo #(parameter DEPTH = 8)(
    input wire clk,
    input wire rst,
    input wire wr_en,
    input wire [7:0] din,
    output reg full
);
    reg [2:0] wr_ptr;

    always @(posedge clk) begin
        if (rst) begin
            wr_ptr <= 0;
            full <= 0;
        end else if (wr_en && !full) begin
            wr_ptr <= wr_ptr + 1;
            full <= (wr_ptr == DEPTH - 1);
        end
    end
endmodule
    """

    buggy_code = """
module fifo #(parameter DEPTH = 8)(
    input wire clk,
    input wire rst,
    input wire wr_en,
    input wire [7:0] din,
    output reg full
);
    reg [2:0] wr_ptr;

    always @(posedge clk) begin
        if (rst) begin
            wr_ptr <= 0;
            full <= 0;
        end else if (wr_en && !full) begin
            wr_ptr <= wr_ptr + 1;
            full <= (wr_ptr == DEPTH);  // Bug: should be DEPTH - 1
        end
    end
endmodule
    """

    bug_report = """
# FIFO Full Flag Bug

The full flag is set incorrectly. The condition should check for `DEPTH - 1` but checks
for `DEPTH`:

```verilog
full <= (wr_ptr == DEPTH);  // Bug: should be DEPTH - 1
```

This causes the FIFO to never actually fill properly.
    """

    score = assess_bug_report_contents_score(base_code, buggy_code, bug_report)
    assert score >= 0.95, f"Expected high score, got {score}"


@pytest.mark.parametrize("include_comment_in_bug_report", [True, False])
def test_remove_chunk_of_original(*, include_comment_in_bug_report: bool) -> None:
    """Test that bugs, where a chunk is removed from the original, can be scored.

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

    comment_str = "  // Output 3 active" if include_comment_in_bug_report else ""
    bug_report = f"""
# Bug Report: Decoder Missing Output Case

The decoder is missing the output case for `3'b011`. This causes the decoder to not
activate the correct output line.

```verilog
3'b011: out = 8'b00001000;{comment_str}
```

This should be included in the decoder's case statement.
    """

    score = assess_bug_report_contents_score(base_design, buggy_design, bug_report)
    assert 0.5 <= score <= 0.95, f"Expected high score, got {score}"
