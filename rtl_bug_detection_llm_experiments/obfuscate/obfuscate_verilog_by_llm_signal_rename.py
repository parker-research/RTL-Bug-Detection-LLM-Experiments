"""Obfuscator for Verilog files using LLM-based signal renaming.

File inspired by LLM query:
Write a Python script which obfuscates a Verilog file by extracting all variable/signal
names, prompting an LLM with "prompt_llm(prompt: str) -> str" with batches of the input
names, requesting a json mapping of old-to-new names. Then, convert all the old names
to uuids, then convert them to new signal names.


==========================

Verilog obfuscator

Usage:
    python verilog_obfuscate.py path/to/design.v

Requirements:
    - Provide a `prompt_llm(prompt: str) -> str` function in the same runtime which will
        be used to query an LLM.
      The LLM must return a JSON object mapping old names to desired new names, e.g.:
        {"sig_a":"X1", "my_reg":"r_42", ...}

What this script does:
1. Reads the Verilog file.
2. Masks comments and string literals so they won't be modified.
3. Extracts candidate signal/variable names from:
   - declarations like `wire`, `reg`, `logic`, `input`, `output`, `inout`, etc.
   - module port lists (best-effort)
4. Deduplicate extracted names and removes Verilog keywords
        and obvious system identifiers.
5. Batches names and prompts the LLM (via `prompt_llm`) to produce a JSON mapping
        old->new names.
6. Replaces old names -> UUID tokens, then UUID tokens -> new names
        (two-step avoids collisions).
7. Restores masked comments and strings.
8. Writes `<orig>.obf.v`.

Notes & caveats:
- This is a heuristic approach. It is safer to check the output with a Verilog linter.
- The extraction rule is intentionally conservative (focuses on declarations and ports).
"""

import re
import sys
import textwrap
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import orjson
from beartype import beartype
from loguru import logger
from tqdm import tqdm

from rtl_bug_detection_llm_experiments.llm import prompt_llm
from rtl_bug_detection_llm_experiments.verilog_spec import (
    VERILOG_DECLARATION_KEYWORDS,
    VERILOG_KEYWORDS,
    VERILOG_SYSTEM_IDENTIFIERS,
)

# ---------------------------
# Helper utilities
# ---------------------------


# Rough identifier regex for Verilog (escaped ids like \... are not handled).
VERILOG_IDENTIFIER_REGEX = r"[A-Za-z_][A-Za-z0-9_$]*"

# ---------------------------
# Masking comments/strings
# ---------------------------


def mask_comments_and_strings(text: str) -> tuple[str, dict[str, str]]:
    """Replace comments/string literals with placeholders, return mapping to originals.

    Supports:
      - block comments /* ... */
      - line comments // ...
      - double-quoted and single-quoted strings

    Returns masked_text, placeholders_map (placeholder -> original_text)
    """
    placeholders: dict[str, str] = {}
    next_id = 0

    def make_placeholder(kind: str) -> str:
        nonlocal next_id
        token = f"__OBFUSCATE_MASK_{kind}_{next_id}__"
        next_id += 1
        return token

    # Combined regex covering comments and strings (non-greedy)
    pattern = re.compile(
        r"(?P<block>/\*[\s\S]*?\*/)|(?P<line>//[^\n]*\n?)|(?P<dq>\"(?:\\.|[^\"\\])*\")|(?P<sq>'(?:\\.|[^'\\])*')",
        flags=re.MULTILINE,
    )

    def repl(m: "re.Match[str]") -> str:
        kind = "UNK"
        if m.group("block"):
            kind = "CMT_BLOCK"
            s = m.group("block")
        elif m.group("line"):
            kind = "CMT_LINE"
            s = m.group("line")
        elif m.group("dq"):
            kind = "STR_DQ"
            s = m.group("dq")
        elif m.group("sq"):
            kind = "STR_SQ"
            s = m.group("sq")
        else:
            s = m.group(0)
        ph = make_placeholder(kind)
        placeholders[ph] = s
        # If the match ends with newline (line comment), preserve newline so code lines
        # remain intact.
        return ph

    masked = pattern.sub(repl, text)
    return masked, placeholders


def unmask_placeholders(text: str, placeholders: dict[str, str]) -> str:
    """Replace placeholders back with original content."""
    # Ensure we replace longest placeholders first (not strictly necessary here).
    for ph in sorted(placeholders.keys(), key=len, reverse=True):
        text = text.replace(ph, placeholders[ph])
    return text


# ---------------------------
# Name extraction
# ---------------------------


def filter_candidates(raw_names: set[str]) -> set[str]:
    """Remove keywords, system ids, numeric-looking items, and short false positives."""
    out = set[str]()
    for n in raw_names:
        if not n:
            continue

        if (
            (n in VERILOG_SYSTEM_IDENTIFIERS)
            or (n in VERILOG_DECLARATION_KEYWORDS)
            or (n in VERILOG_KEYWORDS)
        ):
            continue

        # Skip numeric-looking names (all digits).
        if n.isdigit():
            continue

        # Skip names that look like an escaped identifier (start with backslash).
        if n.startswith("\\"):
            continue

        # Skip the masking placeholders we introduced.
        if n.startswith("__OBFUSCATE_MASK_"):
            continue

        out.add(n)

    return out


# ---------------------------
# LLM prompting & batching
# ---------------------------


def build_prompt_for_full_file(masked_verilog: str) -> str:
    """Ask the LLM to scan the entire (masked) Verilog file and return a JSON mapping.

    We pass the masked code so comments/strings aren't considered for renames.
    """
    # Keep it explicit and JSON-only to reduce chatter.
    return textwrap.dedent(f"""
    You are given a Verilog/SystemVerilog source file (with comments/strings masked).
    Identify all renamable identifiers (signals, nets, variables, ports, params,
    localparams, genvars, typedef names, interface names, package-scoped symbols, etc.)
    that appear in code.

    Produce a single JSON object mapping OLD_NAME -> NEW_NAME.

    STRICT REQUIREMENTS:
    - Only include identifiers that appear in the provided code (outside masks).
    - New names must be valid Verilog/SystemVerilog identifiers:
      start with [A-Za-z_] then [A-Za-z0-9_$]*.
    - Do NOT use any keyword or system identifier (like $display).
    - Avoid collisions (no two old names mapped to the same new name).
    - Preserve case style loosely (e.g., foo_bar -> x1_bar or r42_foo is fine).
    - Do NOT include the masking tokens that look like __OBFUSCATE_MASK_* in the
        mapping.

    --- BEGIN CODE ---
    {masked_verilog}
    --- END CODE ---
    """).strip()


def ask_llm_for_mapping_from_file(masked_text: str) -> dict[str, str]:
    """Query the LLM once with the entire file. Validate and return a mapping."""
    prompt = build_prompt_for_full_file(masked_text)
    logger.info("[LLM] Requesting full-file rename mapping...")
    resp = prompt_llm(prompt)

    parsed = extract_json_substring(resp)
    if parsed is None:
        logger.error("[LLM] Could not parse JSON mapping from response.")
        return {}

    # Filter out anything that isn't a simple string->string mapping,
    # and ensure the old key exists in masked_text as a standalone identifier.
    clean: dict[str, str] = {}
    for old, new in parsed.items():
        if old.startswith("__OBFUSCATE_MASK_"):
            continue
        # Must appear as a standalone identifier in the masked text.
        if re.search(safe_identifier_regex(old), masked_text) is None:
            continue
        # Basic validity of new name.
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_\$]*", new):
            continue
        clean[old] = new

    # De-dup target names: if collisions, drop later ones to be safe.
    seen_new: set[str] = set()
    final_map: dict[str, str] = {}
    for old, new in clean.items():
        if new in seen_new:
            logger.warning(
                f"[LLM] Collision on new name '{new}' for old '{old}' — skipping."
            )
            continue
        seen_new.add(new)
        final_map[old] = new

    logger.info(f"[LLM] Accepted {len(final_map)} rename pairs.")
    return final_map


@beartype
def extract_json_substring(s: str) -> dict[str, Any] | None:
    """Try to find first { ... } JSON object in string s.

    Very naive but sometimes useful when LLM adds commentary around JSON.
    """
    start = s.find("{")
    if start == -1:
        return None

    # Find matching brace.
    end = s.find("}", start)
    if end == -1:
        return None

    while end != -1:
        try:
            potential_json = s[start : end + 1]
            return orjson.loads(potential_json)
        except orjson.JSONDecodeError:
            end = s.find("}", end + 1)

    return None


# ---------------------------
# Replacement
# ---------------------------


def safe_identifier_regex(name: str) -> str:
    """Build a regex that matches the identifier as a standalone token.

    Does not match parts of a longer identifier.

    Verilog identifiers may contain letters, digits, _, $.
    We'll use lookaround to ensure the name isn't wrapped by identifier characters.

    Similar goal as word boundary and re.escape(), but adapted for Verilog identifiers.
    """
    # Escape regex-special chars in name.
    esc = re.escape(name)
    return r"(?<![A-Za-z0-9_\$])" + esc + r"(?![A-Za-z0-9_\$])"


def apply_mapping_two_step(masked_text: str, mapping: dict[str, str]) -> str:
    """Replace old names -> UUID placeholders, then UUID placeholders -> new names.

    Returns transformed masked_text.
    """
    mapping_three_steps: list[tuple[str, str, str]] = [  # old, uuid, new
        (old, "TEMP_UUID_" + uuid.uuid4().hex, new) for old, new in mapping.items()
    ]

    # Step 1: old -> uuid.
    text = masked_text
    for old_signal_name, mapped_uuid, _new_signal_name in mapping_three_steps:
        text = re.sub(
            safe_identifier_regex(old_signal_name),
            mapped_uuid,
            text,
        )

    # Step 2: uuid -> new name.
    for _old_signal_name, mapped_uuid, new_signal_name in mapping_three_steps:
        text = text.replace(mapped_uuid, new_signal_name)

    return text


# ---------------------------
# Main flow
# ---------------------------


def obfuscate_verilog(in_verilog: str) -> str:  # batch_size kept for API compat
    """Obfuscate a Verilog file by asking the LLM for a full-file rename map."""
    # Ask LLM to scan the whole (masked) file and return a JSON mapping.
    mapping = ask_llm_for_mapping_from_file(in_verilog)

    if not mapping:
        logger.warning("LLM returned no usable mapping. Returning original.")
        return in_verilog
    logger.debug(f"LLM mapping ({len(mapping)} remaps): {mapping}")

    # Filter mapping keys to ensure they are valid candidates.
    valid_mapping_keys = filter_candidates(set(mapping.keys()))
    invalid_mapping_keys = valid_mapping_keys - set(mapping.keys())
    mapping = {k: v for k, v in mapping.items() if k in valid_mapping_keys}
    if invalid_mapping_keys:
        logger.debug(f"Filtered mapping to {len(mapping)} valid remaps: {mapping}")
        logger.debug(
            f"Dropped {len(invalid_mapping_keys)} invalid keys: "
            f"{sorted(invalid_mapping_keys)}"
        )

    # Apply mapping of names.
    final_text = apply_mapping_two_step(in_verilog, mapping)
    logger.debug("Applied name replacements (old->uuid->new).")

    return final_text


def obfuscate_verilog_file(in_path: Path, out_path: Path | None) -> Path:
    """Obfuscate a verilog file given by in_path, write to out_path or <in>.obf.v."""
    if not in_path.is_file():
        msg = f"Input path {in_path} is not a file."
        raise FileNotFoundError(msg)

    in_verilog = in_path.read_text(encoding="utf-8")
    final_text = obfuscate_verilog(in_verilog)

    if not out_path:
        out_path = in_path.with_suffix(".obf" + in_path.suffix)

    out_path.write_text(final_text, encoding="utf-8")
    logger.info(f"Obfuscated file written to {out_path}")

    return out_path


# ---------------------------
# CLI
# ---------------------------


def obfuscate_all_files_cursively_in_place(input_dir: Path) -> None:
    """Obfuscate all .v/.sv files in the given directory and its subdirectories."""
    if not input_dir.is_dir():
        msg = f"Input path {input_dir} is not a directory."
        raise NotADirectoryError(msg)

    # Gather files (sorted for deterministic ordering).
    files = sorted(list(input_dir.rglob("*.v")) + list(input_dir.rglob("*.sv")))
    files = [p for p in files if p.is_file()]

    total = len(files)
    if total == 0:
        logger.info(f"No .v/.sv files found in {input_dir}.")
        return

    success_count = 0

    def _worker(path: Path) -> Path:
        # call the existing obfuscation function (in-place)
        obfuscate_verilog_file(in_path=path, out_path=path)
        return path

    with ThreadPoolExecutor(max_workers=12) as executor:
        future_to_path = {executor.submit(_worker, p): p for p in files}

        # Use tqdm to show progress as futures complete
        with tqdm(total=total, desc="Obfuscating", unit="file") as pbar:
            for fut in as_completed(future_to_path):
                path = future_to_path[fut]
                try:
                    fut.result()  # Will re-raise exception if worker failed.
                    success_count += 1
                except Exception as exc:
                    logger.error(f"Error processing {path}: {exc}")
                finally:
                    pbar.update(1)

    logger.info(f"Obfuscated {success_count} / {total} files in directory {input_dir}.")


def main() -> None:
    """Command-line interface."""
    if len(sys.argv) < 2:  # noqa: PLR2004
        logger.info("Usage: python verilog_obfuscate.py path/to/design.v")
        sys.exit(1)
    p = Path(sys.argv[1])

    if p.is_file():
        obfuscate_verilog_file(in_path=p, out_path=None)
    elif p.is_dir():
        logger.info(f"Obfuscating all .v/.sv files in directory {p}...")
        obfuscate_all_files_cursively_in_place(input_dir=p)


if __name__ == "__main__":
    main()
