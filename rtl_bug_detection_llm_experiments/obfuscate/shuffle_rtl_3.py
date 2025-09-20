"""Conservative Verilog/SystemVerilog obfuscator that reorders module-level chunks.

Usage:
python verilog_obfuscate.py input.sv -o out.sv --seed 42 --level safe --map map.json

Notes:
 - This is a heuristics/regex-based tool (works well for many real-world files).
 - It's intentionally conservative: default "safe" level only shuffles within the same
        chunk type.
 - Always validate output with synthesis/lint/simulation for your codebase!

"""

import argparse
import random
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import orjson
from loguru import logger


# --- Chunk datatype ---
@dataclass
class Chunk:
    """Represents a code chunk within a module."""

    kind: str  # e.g., 'param', 'decl', 'assign', 'always', 'inst', 'func', 'pinned'
    text: str
    pinned: bool = False
    id: str | None = None  # unique id for mapping if desired


# --- Regexes / patterns ---
# Mask comments and strings first so searching is safer
COMMENT_STRING_RE = re.compile(
    r"//.*?$|/\*.*?\*/|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'", re.DOTALL | re.MULTILINE
)

# Module-like blocks:
# module/interface/program/package ... endmodule/endinterface/endprogram/endpackage
MODULE_RE = re.compile(
    r"\b(module|interface|program|package)\b\s+([A-Za-z_]\w*)\b(.*?)(\bendmodule\b|\bendinterface\b|\bendprogram\b|\bendpackage\b)",
    re.DOTALL | re.IGNORECASE,
)

# Chunk detection regexes (conservative)
PARAM_RE = re.compile(r"\b(?:parameter|localparam)\b[^;]*?;", re.DOTALL | re.IGNORECASE)
TYPEDEF_RE = re.compile(r"\b(?:typedef)\b.*?;", re.DOTALL | re.IGNORECASE)
DECL_RE = re.compile(
    r"\b(?:wire|reg|logic|bit|byte|int|shortint|longint)\b[^;]*?;",
    re.DOTALL | re.IGNORECASE,
)
ASSIGN_RE = re.compile(r"\bassign\b[^;]*?;", re.DOTALL | re.IGNORECASE)
ALWAYS_INITIAL_RE = re.compile(
    r"\b(?:always|initial)\b\b.*?(?:end\b|;)", re.DOTALL | re.IGNORECASE
)
FUNC_TASK_RE = re.compile(
    r"\b(?:function|task)\b.*?\bend(?:function|task)\b", re.DOTALL | re.IGNORECASE
)
# Very conservative instantiation detection: <module_name> <inst_name> ( ... ) ;
INSTANCE_RE = re.compile(
    r"^[ \t]*([A-Za-z_]\w*)[ \t]+\w+[ \t]*\([^;{)]*?\)\s*;", re.MULTILINE
)
# generate or preprocessor regions we treat as pinned
GENERATE_RE = re.compile(r"\bgenerate\b.*?\bendgenerate\b", re.DOTALL | re.IGNORECASE)
IFDEF_RE = re.compile(r"`(?:if|ifdef|ifndef|elsif|else|endif)\b", re.IGNORECASE)


def make_chunk_id(kind: str, idx: int) -> str:
    """Generate a unique chunk ID based on kind and index."""
    return f"{kind.upper()}_{idx:06d}"


# --- Masking helpers ---
def mask_comments_and_strings(src: str) -> tuple[str, dict[str, str]]:
    """Replace comments and strings with masks to avoid interference with parsing."""
    masks: dict[str, str] = {}

    def repl(m: re.Match[str]) -> str:
        key = f"__MSK_{len(masks)}__"
        masks[key] = m.group(0)
        return key

    masked = re.sub(COMMENT_STRING_RE, repl, src)
    return masked, masks


def restore_masks(src: str, masks: dict[str, str]) -> str:
    """Replace masks with original text."""
    for k, v in masks.items():
        src = src.replace(k, v)
    return src


# --- Module splitting/extraction ---
def find_modules(masked_src: str) -> list[tuple[str, str, int, int]]:
    """Return list of (kind, full_text, start_idx, end_idx) for each module-like block.

    Indexes are string character indexes in terms of masked_src.
    """
    modules: list[tuple[str, str, int, int]] = []
    for m in MODULE_RE.finditer(masked_src):
        m.group(1)
        name = m.group(2)
        # m.group(0) includes the end token (endmodule etc) because regex captured it
        full = m.group(0)
        modules.append((name, full, m.start(), m.end()))
    return modules


# --- Chunk splitting inside a module ---
def split_module_into_chunks(module_text: str) -> list[Chunk]:
    """Conservative linear scanner that finds known chunk types.

    Leaves the rest as "Pinned".
    """
    body = module_text
    chunks: list[Chunk] = []
    idx = 0
    n = len(body)
    patterns = [
        ("generate", GENERATE_RE),
        ("param", PARAM_RE),
        ("typedef", TYPEDEF_RE),
        ("decl", DECL_RE),
        ("assign", ASSIGN_RE),
        ("always", ALWAYS_INITIAL_RE),
        ("func", FUNC_TASK_RE),
        ("inst", INSTANCE_RE),
    ]

    # We will repeatedly search for the nearest next match among patterns
    chunk_counter = 0
    while idx < n:
        nearest_start = None
        nearest_kind = None
        nearest_span = None
        for kind, pat in patterns:
            m = pat.search(body, idx)
            if m:
                s = m.start()
                if nearest_start is None or s < nearest_start:
                    nearest_start = s
                    nearest_kind = kind
                    nearest_span = m.span()
        if nearest_start is None:
            # remainder is pinned (text we don't touch)
            remainder = body[idx:]
            if remainder:
                c = Chunk(
                    kind="pinned",
                    text=remainder,
                    pinned=True,
                    id=make_chunk_id("pinned", chunk_counter),
                )
                chunks.append(c)
                chunk_counter += 1
            break
        # text before match -> pinned
        if nearest_start > idx:
            pre = body[idx:nearest_start]
            c = Chunk(
                kind="pinned",
                text=pre,
                pinned=True,
                id=make_chunk_id("pinned", chunk_counter),
            )
            chunks.append(c)
            chunk_counter += 1
        assert nearest_span is not None
        s, e = nearest_span
        text = body[s:e]
        # classify pinnedness
        pinned = nearest_kind in ("generate",)
        assert nearest_kind is not None
        c = Chunk(
            kind=nearest_kind,
            text=text,
            pinned=pinned,
            id=make_chunk_id(nearest_kind, chunk_counter),
        )
        chunks.append(c)
        chunk_counter += 1
        idx = e
    return chunks


# --- Reordering strategies ---
def reorder_chunks(  # noqa: C901, PLR0912
    chunks: list[Chunk], seed: int = 0, level: str = "safe"
) -> tuple[list[Chunk], dict[str, list[str | None]]]:
    """Reorder chunk list and return (new_chunks, mapping).

    Where mapping maps original index order per kind to new IDs to help with
    traceability.

    - safe: shuffle only within same 'kind' groups (e.g., assigns among assigns)
    - medium: allow shuffling across compatible kinds (decl <-> param?), conservative
    - aggressive: shuffle across most non-pinned chunks.
    """
    random.seed(seed)
    # build index lists for reorderable groups
    reorderable_indices_by_kind: dict[str, list[int]] = {}
    for i, c in enumerate(chunks):
        if c.pinned:
            continue
        # Few chunk kinds to consider reorderable
        reorderable_indices_by_kind.setdefault(c.kind, []).append(i)

    # Mapping for output: old order of ids -> new order of ids per kind.
    mapping: dict[str, list[str | None]] = {}

    # Shallow copy; we'll replace entries by index.
    new_chunks: list[Chunk] = list(chunks)

    if level == "safe":
        # Shuffle only within each kind bucket
        for kind, indices in reorderable_indices_by_kind.items():
            if len(indices) <= 1:
                mapping[kind] = [chunks[i].id for i in indices]
                continue
            # Extract chunk objects and shuffle
            orig_chunks = [chunks[i] for i in indices]
            shuffled = orig_chunks[:]
            random.shuffle(shuffled)
            # Place back
            for pos_idx, new_chunk in zip(indices, shuffled, strict=False):
                new_chunks[pos_idx] = new_chunk
            mapping[kind] = [c.id for c in shuffled]
    elif level == "medium":
        # Combine some compatible kinds into buckets
        # (example: param, typedef, decl together).
        buckets: dict[str, list[int]] = {
            "types_params_decls": [],
            "assigns": [],
            "procedural": [],
        }
        for i, c in enumerate(chunks):
            if c.pinned:
                continue
            if c.kind in ("param", "typedef", "decl"):
                buckets["types_params_decls"].append(i)
            elif c.kind == "assign":
                buckets["assigns"].append(i)
            elif c.kind in ("always", "func", "inst"):
                buckets["procedural"].append(i)
        for bname, indices in buckets.items():
            if not indices:
                continue
            orig = [chunks[i] for i in indices]
            shuffled = orig[:]
            random.shuffle(shuffled)
            for pos_idx, new_chunk in zip(indices, shuffled, strict=False):
                new_chunks[pos_idx] = new_chunk
            mapping[bname] = [c.id for c in shuffled]
    else:  # aggressive
        # Shuffle across all non-pinned chunks
        indices = [i for i, c in enumerate(chunks) if not c.pinned]
        orig = [chunks[i] for i in indices]
        shuffled = orig[:]
        random.shuffle(shuffled)
        for pos_idx, new_chunk in zip(indices, shuffled, strict=False):
            new_chunks[pos_idx] = new_chunk
        mapping["aggressive_all"] = [c.id for c in shuffled]

    return new_chunks, mapping


# --- Main obfuscation of a module text ---
def obfuscate_module_text(
    module_text: str, seed: int = 0, level: str = "safe"
) -> tuple[str, dict[str, list[str | None]]]:
    """Obfuscate a single module-like block.

    Returns (new_module_text, mapping_for_this_module).
    """
    chunks = split_module_into_chunks(module_text)
    new_chunks, mapping = reorder_chunks(chunks, seed=seed, level=level)
    new_text = "".join(c.text for c in new_chunks)
    return new_text, mapping


# --- Whole-file obfuscation ---
def obfuscate_source(
    src: str, seed: int = 0, level: str = "safe"
) -> tuple[str, dict[str, dict[str, list[str | None]]]]:
    """Return (obfuscated_src, full_mapping).

    Maps full_mapping maps module_name -> mapping dict.
    """
    masked_src, masks = mask_comments_and_strings(src)
    full_mapping: dict[str, dict[str, list[str | None]]] = {}

    # We'll iterate modules found and replace them. Use re.sub with a function.
    def repl(m: re.Match[str]) -> str:
        m.group(1)
        name = m.group(2)
        full = m.group(0)
        new_text, mapping = obfuscate_module_text(full, seed=seed, level=level)
        full_mapping[name] = mapping
        return new_text

    obf_masked = re.sub(MODULE_RE, repl, masked_src)
    obf = restore_masks(obf_masked, masks)
    return obf, full_mapping


# --- Syntax check helpers ---
def run_syntax_check(path: str) -> tuple[bool, str]:
    """Try to run verilator --lint-only or yosys read_verilog - to check syntax.

    Returns (ok, stdout+stderr).
    """
    # Try verilator first
    if shutil.which("verilator"):
        cmd = ["verilator", "--lint-only", path]
        try:
            proc = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
            ok = proc.returncode == 0
            out = proc.stdout + proc.stderr
        except Exception as e:
            return False, f"verilator run failed: {e}"
        else:
            return ok, out

    # Fallback to yosys (fast read)
    if shutil.which("yosys"):
        cmd = ["yosys", "-p", f"read_verilog -sv {path}; synth -top dummy || true"]
        # The synth command may fail; we just try read_verilog
        try:
            proc = subprocess.run(  # noqa: S603
                ["yosys", "-p", f"read_verilog -sv {path}; prep"],  # noqa: S607
                capture_output=True,
                text=True,
                check=False,
            )
            ok = proc.returncode == 0
            out = proc.stdout + proc.stderr
        except Exception as e:
            return False, f"yosys run failed: {e}"
        else:
            return ok, out

    return False, "no verilator or yosys found in PATH; skipping syntax check"


# --- CLI / main ---
def main() -> None:
    """Run CLI."""
    p = argparse.ArgumentParser(
        description=(
            "Obfuscate SystemVerilog modules by reordering safe top-level chunks."
        )
    )
    p.add_argument("infile", help="Input SystemVerilog file")
    p.add_argument(
        "-o", "--out", help="Output filename (default: <infile>.obf.sv)", default=None
    )
    p.add_argument(
        "--seed", type=int, default=0, help="Random seed (for reproducible shuffles)"
    )
    p.add_argument(
        "--level",
        choices=("safe", "medium", "aggressive"),
        default="safe",
        help="Shuffle aggressiveness",
    )
    p.add_argument(
        "--map", help="Write JSON map of module -> mapping (ids)", default=None
    )
    p.add_argument(
        "--check",
        action="store_true",
        help="Run syntax check (verilator or yosys) on output (if available)",
    )
    args = p.parse_args()

    infile = args.infile
    src = Path(infile).read_text(encoding="utf-8")

    obf_src, full_map = obfuscate_source(src, seed=args.seed, level=args.level)

    outpath = args.out or (infile + ".obf.sv")
    Path(outpath).write_text(obf_src, encoding="utf-8")

    if args.map:
        Path(args.map).write_bytes(orjson.dumps(full_map, option=orjson.OPT_INDENT_2))

    if args.check:
        ok, out = run_syntax_check(outpath)
        logger.debug(f"Syntax check output:\n{out}")
        if ok:
            logger.info("Syntax check passed.")
        else:
            logger.error("Syntax check FAILED!")


if __name__ == "__main__":
    main()
