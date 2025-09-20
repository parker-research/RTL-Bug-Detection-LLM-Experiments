"""Tests for obfuscate_verilog_by_llm_signal_rename.py.

Does not test the LLM part. Just tests the mapping application part.
"""

from rtl_bug_detection_llm_experiments.obfuscate.obfuscate_verilog_by_llm_signal_rename import (  # noqa: E501
    apply_mapping_two_step,
)


def test_apply_mapping_two_step_not_verilog() -> None:
    assert (
        apply_mapping_two_step("Z a b c", {"a": "x", "b": "y", "c": "z"}) == "Z x y z"
    )


def test_apply_mapping_two_step_basic_verilog_1() -> None:
    input_verilog = """
// Comment here
module counter2 (
    input  logic clk,
    input  logic rst_n,   // active-low reset
    input  logic en,
    output logic [1:0] q
);
    always_ff @(posedge clk) begin
        if (!rst_n)       q <= 2'b00;
        else if (en)      q <= q + 2'd1;
        else              q <= q;
    end
endmodule
""".strip()

    expected_verilog = """
// Comment here
module counter4 (
    input  logic clkA,
    input  logic rstA,   // active-low reset
    input  logic enA,
    output logic [1:0] qA
);
    always_ff @(posedge clkA) begin
        if (!rstA)       qA <= 2'b00;
        else if (enA)      qA <= qA + 2'd1;
        else              qA <= qA;
    end
endmodule
""".strip()

    assert apply_mapping_two_step(input_verilog, {}) == input_verilog
    assert apply_mapping_two_step(expected_verilog, {}) == expected_verilog

    assert (
        apply_mapping_two_step(
            input_verilog,
            {
                "counter2": "counter4",
                "clk": "clkA",
                "rst_n": "rstA",
                "en": "enA",
                "q": "qA",
            },
        )
        == expected_verilog
    )
