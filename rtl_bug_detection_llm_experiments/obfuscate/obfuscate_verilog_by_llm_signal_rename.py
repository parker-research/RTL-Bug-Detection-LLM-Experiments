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
8. Writes `<orig>.obf.v`, and leaves a backup `<orig>.bak.v`.

Notes & caveats:
- This is a heuristic approach. It is safer to check the output with a Verilog linter.
- The extraction rule is intentionally conservative (focuses on declarations and ports).
"""

import json
import re
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import orjson
from beartype import beartype
from loguru import logger

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
        token = f"__MASK_{kind}_{next_id}__"
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


def extract_from_declarations(masked_text: str) -> set[str]:
    """Heuristically extract identifiers from common declarations.

    This parses comma-separated declarators before a semicolon.
    """
    # Example output format: decl_kw = r"(?:wire|reg|logic|input|...|output)"
    decl_kw = r"(?:" + "|".join(VERILOG_DECLARATION_KEYWORDS) + ")"
    # Match declarations (rough): keyword [range]? list_of_declarators ;
    pattern = re.compile(
        rf"\b{decl_kw}\b\s*(?:\[[^\]]+\]\s*)?([^;]+);",
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    names: set[str] = set()
    for m in pattern.finditer(masked_text):
        decl_body = m.group(1)
        # split by commas but respect potential braces/parenthesis (rough split)
        parts = split_comma_separated(decl_body)
        for part in parts:
            # strip assignments like "a = 1'b0" or dimensions like "arr [0:7]"
            # take the first identifier-like token in part
            t = re.search(VERILOG_IDENTIFIER_REGEX, part)
            if t:
                name = t.group(0)
                names.add(name)
    return names


def split_comma_separated(s: str) -> list[str]:
    """Split a string by top-level commas.

    Avoid splitting inside parentheses/brackets/braces).
    """
    parts: list[str] = []
    cur: list[str] = []
    level = 0
    for ch in s:
        if ch in "([{":
            level += 1
        elif ch in ")]}" and level > 0:
            level -= 1
        if ch == "," and level == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur).strip())
    return parts


def extract_from_module_ports(masked_text: str) -> set[str]:
    """Best-effort extraction of identifiers appearing in module port lists.

    ```
    module foo (input a, output b, c, ... );
    ```

    We'll parse module ... ( ... ) ; blocks (the header), capturing identifiers inside.
    """
    names: set[str] = set()
    # find module ... ( ... ) optionally with semicolon or newline then body
    module_pattern = re.compile(
        r"\bmodule\b\s+" + VERILOG_IDENTIFIER_REGEX + r"\s*\((.*?)\)\s*;",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for m in module_pattern.finditer(masked_text):
        ports_text = m.group(1)
        # ports are comma separated; pipe through split_comma_separated
        for part in split_comma_separated(ports_text):
            t = re.search(VERILOG_IDENTIFIER_REGEX, part)
            if t:
                names.add(t.group(0))
    # Also try module ... ( ... ) followed by newline and body without trailing
    # semicolon (older style).
    module_pattern2 = re.compile(
        r"\bmodule\b\s+" + VERILOG_IDENTIFIER_REGEX + r"\s*\((.*?)\)\s*",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for m in module_pattern2.finditer(masked_text):
        ports_text = m.group(1)
        for part in split_comma_separated(ports_text):
            t = re.search(VERILOG_IDENTIFIER_REGEX, part)
            if t:
                names.add(t.group(0))
    return names


def extract_extra_by_lhs(masked_text: str) -> set[str]:
    """Heuristic: get left-hand identifiers in simple assign expressions.

    'assign <id> = ...' or '<id> <= ...' or '<id> = ...' statements

    This can catch some signals not declared clearly by earlier parsers.
    """
    names: set[str] = set()
    # assign <id> = ...
    m_assign = re.finditer(
        r"\bassign\b\s+(" + VERILOG_IDENTIFIER_REGEX + r")\b", masked_text
    )
    for m in m_assign:
        names.add(m.group(1))
    # simple stmt patterns: identifier = or <=
    m_lhs = re.finditer(
        r"(^|\s)(" + VERILOG_IDENTIFIER_REGEX + r")\s*(?:<=|=)",
        masked_text,
        flags=re.MULTILINE,
    )
    for m in m_lhs:
        names.add(m.group(2))
    return names


def filter_candidates(raw_names: set[str]) -> set[str]:
    """Remove keywords, system ids, numeric-looking items, and short false positives."""
    out = set[str]()
    for n in raw_names:
        if not n:
            continue
        if n in VERILOG_SYSTEM_IDENTIFIERS:
            continue
        if n.lower() in VERILOG_KEYWORDS:
            continue
        # Skip numeric-like or single-character nets like 'i' maybe keep 'i'? keep >=2
        # chars or end with underscore/digit?
        if re.fullmatch(r"\d+", n):
            continue
        # Skip names that look like an escaped identifier (start with backslash).
        if n.startswith("\\"):
            continue
        # Optionally skip single character names to reduce noise? we will keep them
        # (user asked all variable/signal names).
        out.add(n)
    return out


# ---------------------------
# LLM prompting & batching
# ---------------------------


def chunk_list(lst: list[str], size: int) -> Iterator[list[str]]:
    """Yield successive chunks of given size from lst."""
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


def build_prompt_for_batch(batch: list[str]) -> str:
    """Construct the text prompt to ask the LLM for a JSON mapping.

    We ask for strict JSON only, nothing else.
    """
    names_json = json.dumps(batch, indent=2)
    prompt = (
        "You are given a JSON array of Verilog signal names. "
        "Return a json object mapping each "
        "old name to a new similar-but-different name. "
        "The output MUST be valid JSON and contain exactly "
        "one key for each input name. Do not add any commentary. Example output:\n"
        '{"old_name":"new_name", "another_old":"another_new"}\n\n'
        "Constraints for new names:\n"
        "- Must be valid Verilog identifiers "
        "(start with letter or underscore, then letters/digits/_/$).\n"
        "- Do NOT produce names that collide with Verilog keywords or system "
        "identifiers.\n\n"
        "Input names:\n"
        f"{names_json}\n\n"
        "Return only the JSON mapping object."
    )
    return prompt  # noqa: RET504


def ask_llm_for_mapping(names: list[str], batch_size: int = 200) -> dict[str, str]:
    """Batch names, call prompt_llm for each batch, and aggregate mapping.

    Expects the LLM to return pure JSON text.
    """
    mapping: dict[str, str] = {}
    for batch in chunk_list(names, batch_size):
        prompt = build_prompt_for_batch(batch)
        logger.info(f"[LLM] Requesting mapping for batch of {len(batch)} names...")
        resp = prompt_llm(prompt)

        parsed = extract_json_substring(resp)
        if parsed is None:
            logger.error(
                f"[LLM] Error: could not parse JSON from LLM response:\n{resp}"
            )
            continue

        logger.debug(f"LLM suggested remapping: {parsed}")

        # Validate and merge, but ensure keys cover the batch
        for k in batch:
            if k not in parsed:
                logger.warning(
                    f"[LLM] Warning: mapping for '{k}' missing in LLM response; "
                    f"skipping that name."
                )
            else:
                mapping[k] = parsed[k]
    return mapping


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
            candidate = s[start : end + 1]
            return orjson.loads(candidate)
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
    """
    # Escape regex-special chars in name.
    esc = re.escape(name)
    return rf"(?<![A-Za-z0-9_\$]){esc}(?![A-Za-z0-9_\$])"


def apply_mapping_two_step(masked_text: str, mapping: dict[str, str]) -> str:
    """Replace old names -> UUID placeholders, then UUID placeholders -> new names.

    Returns transformed masked_text.
    """
    mapping_three_steps: list[tuple[str, str, str]] = [  # old, uuid, new
        (old, "MASK_UUID_" + uuid.uuid4().hex, new) for old, new in mapping.items()
    ]

    # Step 1: old -> uuid.
    text = masked_text
    for old_signal_name, mapped_uuid, _new_signal_name in mapping_three_steps:
        text = re.sub(r"\b" + re.escape(old_signal_name) + r"\b", mapped_uuid, text)

    # Step 2: uuid -> new name.
    for _old_signal_name, mapped_uuid, new_signal_name in mapping_three_steps:
        text = re.sub(r"\b" + re.escape(mapped_uuid) + r"\b", new_signal_name, text)

    return text


# ---------------------------
# Main flow
# ---------------------------


def obfuscate_verilog(in_verilog: str, batch_size: int = 200) -> str:
    """Obfuscate a verilog file/str (main entry point)."""
    masked_text, placeholders = mask_comments_and_strings(in_verilog)
    logger.info("Comments and strings masked.")

    # Extract candidates.
    candidate_decl = extract_from_declarations(masked_text)
    candidate_ports = extract_from_module_ports(masked_text)
    candidate_lhs = extract_extra_by_lhs(masked_text)

    raw_candidates = candidate_decl.union(candidate_ports).union(candidate_lhs)
    candidates = filter_candidates(raw_candidates)

    logger.info(
        f"Found {len(candidates)} candidate names (unique). "
        f"Example few: {list(candidates)[:10]}"
    )

    if not candidates:
        logger.warning("No candidate names found. Returning original.")
        return in_verilog

    # Query LLM for mapping old->new names
    names_list = sorted(candidates)
    mapping = ask_llm_for_mapping(names_list, batch_size=batch_size)

    if not mapping:
        logger.warning("LLM returned no mapping. Returning original.")
        return in_verilog

    # Final mapping might not cover all candidates; filter to those present.
    mapping = {k: v for k, v in mapping.items() if k in candidates}
    logger.info(f"Mappings obtained for {len(mapping)} names.")

    # Apply mapping (two-step)
    transformed_masked_text = apply_mapping_two_step(masked_text, mapping)
    logger.info("Applied name replacements (old->uuid->new).")

    # Unmask comments/strings.
    final_text = unmask_placeholders(transformed_masked_text, placeholders)

    logger.info("Restored comments and strings.")
    return final_text


def obfuscate_verilog_file(
    in_path: Path, out_path: Path | None, batch_size: int = 200
) -> Path:
    """Obfuscate a verilog file given by in_path, write to out_path or <in>.obf.v."""
    if not in_path.is_file():
        msg = f"Input path {in_path} is not a file."
        raise FileNotFoundError(msg)

    in_verilog = in_path.read_text(encoding="utf-8")
    final_text = obfuscate_verilog(in_verilog, batch_size=batch_size)

    if not out_path:
        out_path = in_path.with_suffix(".obf" + in_path.suffix)

    out_path.write_text(final_text, encoding="utf-8")
    logger.info(f"Obfuscated file written to {out_path}")

    return out_path


# ---------------------------
# CLI
# ---------------------------


def main() -> None:
    """Command-line interface."""
    if len(sys.argv) < 2:  # noqa: PLR2004
        logger.info("Usage: python verilog_obfuscate.py path/to/design.v")
        sys.exit(1)
    p = Path(sys.argv[1])

    # TODO(Parker): If provided module path is directory, optionally process all files.
    # For now single file only.
    try:
        obfuscate_verilog_file(in_path=p, out_path=None)
    except Exception as e:
        logger.info("[ERROR]", e)
        raise


if __name__ == "__main__":
    main()
