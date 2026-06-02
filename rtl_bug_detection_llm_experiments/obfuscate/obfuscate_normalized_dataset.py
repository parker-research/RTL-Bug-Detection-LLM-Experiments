"""Obfuscate a normalized bug dataset (base.v + buggy.v pairs).

For each challenge folder, the same LLM-derived signal rename mapping is applied
to both base and buggy files so the only diff between the obfuscated pair is still
the original bug (now expressed in obfuscated signal names). The same shuffle seed
is used for both files so block ordering is consistent.

Usage:
    python -m rtl_bug_detection_llm_experiments.obfuscate.obfuscate_normalized_dataset \
        --input-dir /path/to/step_1_normalized_bug_examples \
        --output-dir /path/to/step_1_normalized_bug_examples_obfuscated

The output mirrors the input directory structure exactly. metadata.json files
are copied unchanged.
"""

import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import tyro
from loguru import logger
from tqdm import tqdm

from rtl_bug_detection_llm_experiments.obfuscate.obfuscate_verilog_by_llm_signal_rename import (
    apply_mapping_two_step,
    ask_llm_for_mapping_from_file,
    filter_candidates,
    mask_comments_and_strings,
)
from rtl_bug_detection_llm_experiments.obfuscate.shuffle_rtl_3 import obfuscate_source

_SHUFFLE_SEED = 42
_SHUFFLE_LEVEL = "safe"


def _find_verilog_file(folder: Path, stem: str) -> Path | None:
    """Return the .sv or .v file with the given stem in folder, or None."""
    for suffix in (".sv", ".v"):
        candidate = folder / (stem + suffix)
        if candidate.is_file():
            return candidate
    return None


def _apply_rename_mapping(text: str, mapping: dict[str, str]) -> str:
    """Apply the LLM-derived rename mapping to text (no masking needed here)."""
    valid_keys = filter_candidates(set(mapping.keys()))
    clean_mapping = {k: v for k, v in mapping.items() if k in valid_keys}
    return apply_mapping_two_step(text, clean_mapping)


def obfuscate_challenge(
    challenge_dir: Path,
    out_challenge_dir: Path,
) -> bool:
    """Obfuscate one challenge folder (base + buggy pair).

    Returns True on success, False if files are missing or an error occurs.
    """
    base_path = _find_verilog_file(challenge_dir, "base")
    buggy_path = _find_verilog_file(challenge_dir, "buggy")

    if base_path is None or buggy_path is None:
        logger.warning(f"Skipping {challenge_dir.name}: missing base or buggy file.")
        return False

    suffix = base_path.suffix

    try:
        base_text = base_path.read_text(encoding="utf-8")
        buggy_text = buggy_path.read_text(encoding="utf-8")

        # Step 1: derive rename mapping from base file only, then apply to both.
        masked_base, _ = mask_comments_and_strings(base_text)
        mapping = ask_llm_for_mapping_from_file(masked_base)

        if mapping:
            base_renamed = _apply_rename_mapping(base_text, mapping)
            buggy_renamed = _apply_rename_mapping(buggy_text, mapping)
        else:
            logger.warning(
                f"{challenge_dir.name}: LLM returned empty mapping; "
                "skipping rename (shuffle only)."
            )
            base_renamed = base_text
            buggy_renamed = buggy_text

        # Step 2: shuffle blocks (same seed for both files for consistent ordering).
        base_shuffled, _ = obfuscate_source(base_renamed, seed=_SHUFFLE_SEED, level=_SHUFFLE_LEVEL)
        buggy_shuffled, _ = obfuscate_source(buggy_renamed, seed=_SHUFFLE_SEED, level=_SHUFFLE_LEVEL)

        # Write outputs.
        out_challenge_dir.mkdir(parents=True, exist_ok=True)
        (out_challenge_dir / f"base{suffix}").write_text(base_shuffled, encoding="utf-8")
        (out_challenge_dir / f"buggy{suffix}").write_text(buggy_shuffled, encoding="utf-8")

        # Copy metadata.json if present.
        meta = challenge_dir / "metadata.json"
        if meta.is_file():
            shutil.copy2(meta, out_challenge_dir / "metadata.json")

    except Exception:
        logger.exception(f"Error obfuscating {challenge_dir.name}")
        return False

    return True


def obfuscate_normalized_dataset(
    *,
    input_dir: Path,
    output_dir: Path,
    max_workers: int = 8,
) -> None:
    """Obfuscate all challenge pairs in input_dir and write to output_dir."""
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)

    if not input_dir.is_dir():
        msg = f"input_dir does not exist or is not a directory: {input_dir}"
        raise NotADirectoryError(msg)

    challenge_dirs = sorted(p for p in input_dir.iterdir() if p.is_dir())
    total = len(challenge_dirs)
    logger.info(f"Found {total} challenge folders in {input_dir}")

    if output_dir.exists() and any(output_dir.iterdir()):
        logger.warning(
            f"output_dir already exists and is non-empty: {output_dir}. "
            "Existing files may be overwritten."
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    success_count = 0
    skip_count = 0

    def _worker(challenge_dir: Path) -> tuple[Path, bool]:
        out = output_dir / challenge_dir.name
        ok = obfuscate_challenge(challenge_dir, out)
        return challenge_dir, ok

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_worker, d): d for d in challenge_dirs}
        with tqdm(total=total, desc="Obfuscating challenges", unit="challenge") as pbar:
            for fut in as_completed(futures):
                _, ok = fut.result()
                if ok:
                    success_count += 1
                else:
                    skip_count += 1
                pbar.update(1)

    logger.info(
        f"Done. {success_count}/{total} challenges obfuscated successfully "
        f"({skip_count} skipped/failed)."
    )


def main() -> None:
    """CLI entry point."""
    tyro.cli(obfuscate_normalized_dataset)


if __name__ == "__main__":
    main()
