"""Test Yosys equivalence check functionality."""

import os
from pathlib import Path

from rtl_bug_detection_llm_experiments.yosys_equivalence_check import run_equivalence

YOSYS_PATH = os.environ.get("YOSYS_PATH", "yosys")

TESTS_DIR_PATH = Path(__file__).parent


def test_run_equivalence() -> None:
    """Test running Yosys equivalence check on two sample Verilog files."""
    result = run_equivalence(
        input_gold_path=TESTS_DIR_PATH / "test_samples/equivalence_check_1_gold.sv",
        input_gate_path=TESTS_DIR_PATH / "test_samples/equivalence_check_1_gate.sv",
        yosys_command=YOSYS_PATH,
    )
    assert result == 0


def test_run_equivalence_swapped() -> None:
    """Test running Yosys equivalence check on two sample Verilog files."""
    result = run_equivalence(
        input_gold_path=TESTS_DIR_PATH / "test_samples/equivalence_check_1_gate.sv",
        input_gate_path=TESTS_DIR_PATH / "test_samples/equivalence_check_1_gold.sv",
        yosys_command=YOSYS_PATH,
    )
    assert result == 0


def test_run_equivalence_different() -> None:
    """Test running Yosys equivalence check on two sample Verilog files."""
    result = run_equivalence(
        input_gold_path=(
            TESTS_DIR_PATH / "test_samples/equivalence_check_1_gold_different.sv"
        ),
        input_gate_path=TESTS_DIR_PATH / "test_samples/equivalence_check_1_gate.sv",
        yosys_command=YOSYS_PATH,
    )
    assert result == 1
