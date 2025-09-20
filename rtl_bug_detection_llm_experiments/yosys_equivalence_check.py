"""Equivalence check for exactly two (System)Verilog files in isolation.

- No top name required. Each file is synthesized on its own:
    read_verilog ... <file>
    prep -auto-top
    rename -top gold|gate

- Then we build an equivalence miter (equiv_make) and assert status.
- Exit code: 0 -> equivalent, 1 -> not equivalent / proof failed, 2 -> usage/env error.

Examples:
  this.py gold.sv gate.sv
  this.py -D FOO=1 -I inc gold.v gate.v

"""

import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import typed_argparse as tap
from loguru import logger


def infer_is_system_verilog(path: str | Path) -> bool:
    """Infer SystemVerilog from file extension."""
    return Path(path).suffix.lower() in {".sv", ".svh", ".svi"}


def yosys_read_cmd(
    file: str | Path, include_dirs: list[Path], defines: list[str], *, use_sv: bool
) -> str:
    """Build yosys read_verilog command with options."""
    opts: list[str] = []
    if use_sv:
        opts.append("-sv")
    for inc in include_dirs:
        opts += ["-I", inc.resolve().as_posix()]
    for d in defines:
        opts += ["-D", d]
    return "read_verilog {} {}".format(
        " ".join(shlex.quote(o) for o in opts),
        shlex.quote(Path(file).resolve().as_posix()),
    )


def build_yosys_script(  # noqa: PLR0913
    gold_file: str | Path,
    gate_file: str | Path,
    include_dirs: list[Path],
    defines: list[str],
    *,
    use_sv: bool,
    extra_passes: list[str],
    use_abc9: bool,
) -> str:
    """Build Yosys script for isolated equivalence check of two (S)V files."""
    lines: list[str] = []

    # GOLD side
    lines.append("# GOLD (isolated)")
    lines.append(yosys_read_cmd(gold_file, include_dirs, defines, use_sv=use_sv))
    lines.append("prep -auto-top")
    if use_abc9:
        lines.append("abc9 -dff")
    lines.extend(extra_passes)
    lines.append("rename -top gold")
    lines.append("design -stash gold")

    # GATE side
    lines.append("\n# GATE (isolated)")
    lines.append(yosys_read_cmd(gate_file, include_dirs, defines, use_sv=use_sv))
    lines.append("prep -auto-top")
    if use_abc9:
        lines.append("abc9 -dff")
    lines.extend(extra_passes)
    lines.append("rename -top gate")
    lines.append("design -stash gate")

    # Equivalence miter & proof
    lines.append("\n# Build miter and prove equivalence")
    lines.append("design -copy-from gold -as gold gold")
    lines.append("design -copy-from gate -as gate gate")
    lines.append("equiv_make gold gate equiv")
    lines.append("hierarchy -top equiv")
    lines.append("opt_clean")

    # https://yosyshq.readthedocs.io/projects/yosys/en/0.40/cmd/equiv_simple.html
    # Broken line: lines.append("equiv_simple -undef -ignore_gold_x -cleanup")
    lines.append("equiv_simple -undef")
    # Broken line: lines.append("equiv_induct -undef -max_steps 20")
    lines.append("equiv_induct -undef")  # TODO(Parker): Maybe add `-seq` flag.
    lines.append("equiv_status")
    lines.append("equiv_status -assert")

    return "\n".join(lines) + "\n"


def run_equivalence(  # noqa: PLR0913
    input_gold_path: Path,
    input_gate_path: Path,
    include_dirs: list[Path] | None = None,
    defines: list[str] | None = None,
    *,
    force_sv: bool = False,
    yosys_command: str = "yosys",
    abc9: bool = False,
    extra_pass: list[str] | None = None,
    keep_temp: bool = False,
) -> int:
    """Run isolated (System)Verilog equivalence via Yosys.

    Returns:
        int: Process exit code
            (0 = equivalent, 1 = not equivalent/proof failed, 2 = usage error).

    """
    include_dirs = include_dirs or []
    defines = defines or []
    extra_pass = extra_pass or []

    # Validate inputs
    for f in (input_gold_path, input_gate_path):
        if not f.exists():
            logger.error(f"File not found: {f}")
            return 2

    yosys_bin = (
        shutil.which(yosys_command) if yosys_command == "yosys" else yosys_command
    )
    if not yosys_bin or not Path(yosys_bin).exists():
        logger.error(f"Yosys not found at '{yosys_command}'.")
        return 2

    use_sv = (
        force_sv
        or infer_is_system_verilog(input_gold_path)
        or infer_is_system_verilog(input_gate_path)
    )

    with tempfile.TemporaryDirectory(delete=not keep_temp) as temp_dir_str:
        temp_dir = Path(temp_dir_str)

        ys_script = build_yosys_script(
            gold_file=input_gold_path,
            gate_file=input_gate_path,
            include_dirs=include_dirs,
            defines=defines,
            use_sv=use_sv,
            extra_passes=list(extra_pass),
            use_abc9=abc9,
        )
        ys_script_path = temp_dir / "equiv_isolated.ys"
        yosys_log_path = temp_dir / "yosys.log"
        ys_script_path.write_text(ys_script, encoding="utf-8")

        cmd: list[str] = [str(yosys_bin), "-q", "-s", str(ys_script_path)]
        logger.debug("Yosys command: " + " ".join(shlex.quote(c) for c in cmd))

        with yosys_log_path.open("w", encoding="utf-8") as yosys_log_out_fp:
            proc = subprocess.run(  # noqa: S603
                cmd,
                check=False,
                stdout=yosys_log_out_fp,
                stderr=subprocess.STDOUT,
            )

        if keep_temp:
            logger.debug(f"Yosys script: {ys_script_path}")
            logger.debug(f"Yosys log:    {yosys_log_path}")

        if proc.returncode == 0:
            logger.info("✅ Equivalent (equiv_status -assert passed)")
            logger.info(f"Yosys log: {yosys_log_path}")
            return 0

        logger.info("❌ Not equivalent OR proof failed.")
        logger.info("Tip: try --abc9 or --extra-pass 'opt -fast' for tougher cones.")
        return 1


# 1. Argument definition
class Args(tap.TypedArgs):
    """Command-line arguments for yosys_equivalence_check.py."""

    gold: Path = tap.arg(help="Reference file (gold)", positional=True)
    gate: Path = tap.arg(help="Candidate file (gate)", positional=True)

    include_dirs: list[Path] = tap.arg(
        "-I",
        default=[],
        help="Add include directory (repeatable)",
    )
    defines: list[str] = tap.arg(
        "-D",
        default=[],
        help="Preprocessor define NAME or NAME=VAL (repeatable)",
    )
    sv: bool = tap.arg(
        "--sv",
        help="Force SystemVerilog parsing",
    )
    yosys: str = tap.arg(
        "--yosys",
        default="yosys",
        help="Path to yosys binary",
    )
    abc9: bool = tap.arg(
        "--abc9",
        help="Run abc9 -dff after prep (can help some proofs)",
    )
    extra_pass: list[str] = tap.arg(
        "--extra-pass",
        default=[],
        help="Extra Yosys pass after prep (e.g., 'opt -fast')",
    )
    keep_temp: bool = tap.arg(
        "--keep-temp",
        help="Keep generated .ys and .log in CWD",
    )


# 2. Business logic
def runner(args: Args) -> None:
    """Run equivalence check with parsed args."""
    return_code = run_equivalence(
        input_gold_path=(args.gold),
        input_gate_path=(args.gate),
        include_dirs=args.include_dirs,
        defines=args.defines,
        force_sv=args.sv,
        yosys_command=args.yosys,
        abc9=args.abc9,
        extra_pass=args.extra_pass,
        keep_temp=args.keep_temp,
    )
    sys.exit(return_code)


# 3. Bind + run
def main_cli() -> None:
    """Run CLI entry point."""
    tap.Parser(Args).bind(runner).run()


if __name__ == "__main__":
    main_cli()
