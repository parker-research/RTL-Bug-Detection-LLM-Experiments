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

import argparse
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from loguru import logger


def infer_is_system_verilog(path: str | Path) -> bool:
    """Infer SystemVerilog from file extension."""
    return Path(path).suffix.lower() in {".sv", ".svh", ".svi"}


def yosys_read_cmd(
    file: str | Path, include_dirs: list[str], defines: list[str], *, use_sv: bool
) -> str:
    """Build yosys read_verilog command with options."""
    opts: list[str] = []
    if use_sv:
        opts.append("-sv")
    for inc in include_dirs:
        opts += ["-I", inc]
    for d in defines:
        opts += ["-D", d]
    return "read_verilog {} {}".format(
        " ".join(shlex.quote(o) for o in opts),
        shlex.quote(Path(file).resolve().as_posix()),
    )


def build_yosys_script(  # noqa: PLR0913
    gold_file: str | Path,
    gate_file: str | Path,
    include_dirs: list[str],
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


def main() -> None:
    """Run CLI wrapper for isolated (System)Verilog equivalence via Yosys."""
    ap = argparse.ArgumentParser(
        description="Isolated (System)Verilog equivalence via Yosys (no top needed)."
    )
    ap.add_argument("gold", help="Reference file (gold)")
    ap.add_argument("gate", help="Candidate file (gate)")
    ap.add_argument(
        "-I",
        dest="include_dirs",
        action="append",
        default=[],
        help="Add include directory (repeatable)",
    )
    ap.add_argument(
        "-D",
        dest="defines",
        action="append",
        default=[],
        help="Preprocessor define NAME or NAME=VAL (repeatable)",
    )
    ap.add_argument("--sv", action="store_true", help="Force SystemVerilog parsing")
    ap.add_argument("--yosys", default="yosys", help="Path to yosys binary")
    ap.add_argument(
        "--abc9",
        action="store_true",
        help="Run abc9 -dff after prep (can help some proofs)",
    )
    ap.add_argument(
        "--extra-pass",
        action="append",
        default=[],
        help="Extra Yosys pass after prep (e.g., 'opt -fast')",
    )
    ap.add_argument(
        "--keep-temp", action="store_true", help="Keep generated .ys and .log in CWD"
    )
    ap.add_argument(
        "--show-yosys-cmd", action="store_true", help="logger.info exact Yosys command"
    )
    args = ap.parse_args()

    arg_gold = Path(args.gold)
    arg_gate = Path(args.gate)

    # Validate inputs
    for f in (arg_gold, arg_gate):
        if not f.exists():
            logger.info(f"ERROR: File not found: {f}", file=sys.stderr)
            sys.exit(2)

    yosys_bin = shutil.which(args.yosys) if args.yosys == "yosys" else args.yosys
    if not yosys_bin or not Path(yosys_bin).exists():
        logger.info(f"ERROR: Yosys not found at '{args.yosys}'.", file=sys.stderr)
        sys.exit(2)

    use_sv = (
        args.sv
        or infer_is_system_verilog(arg_gold)
        or infer_is_system_verilog(arg_gate)
    )

    with tempfile.TemporaryDirectory(delete=bool(not args.keep_temp)) as temp_dir_str:
        temp_dir = Path(temp_dir_str)

        ys_script = build_yosys_script(
            gold_file=arg_gold,
            gate_file=arg_gate,
            include_dirs=args.include_dirs,
            defines=args.defines,
            use_sv=use_sv,
            extra_passes=list(args.extra_pass),
            use_abc9=args.abc9,
        )
        ys_path = temp_dir / "equiv_isolated.ys"
        log_path = temp_dir / "yosys.log"
        ys_path.write_text(ys_script, encoding="utf-8")

        cmd = [yosys_bin, "-q", "-s", str(ys_path)]
        if args.show_yosys_cmd:
            logger.info("Yosys command:", " ".join(shlex.quote(c) for c in cmd))
        with log_path.open("w", encoding="utf-8") as yosys_log_out_fp:
            proc = subprocess.run(  # noqa: S603
                cmd,
                check=False,
                stdout=yosys_log_out_fp,
                stderr=subprocess.STDOUT,
            )

        if args.keep_temp:
            logger.debug(f"Yosys script: {ys_path}")
            logger.debug(f"Yosys log: {log_path}")

        if proc.returncode == 0:
            logger.info("✅ Equivalent (equiv_status -assert passed)")
            logger.info(f"Yosys log: {log_path}")
            sys.exit(0)
        else:
            logger.info("❌ Not equivalent OR proof failed.")
            logger.info(
                "Tip: try --abc9 or --extra-pass 'opt -fast' for tougher cones."
            )
            sys.exit(1)


if __name__ == "__main__":
    main()
