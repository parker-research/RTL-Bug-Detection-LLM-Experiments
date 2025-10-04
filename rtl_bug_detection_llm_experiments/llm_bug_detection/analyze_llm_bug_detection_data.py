"""Analyze LLM bug detection data.

Data is produced by `collect_llm_bug_detection_data.py`.
"""

from pathlib import Path

import fire  # pyright: ignore[reportMissingTypeStubs]
import polars as pl
from loguru import logger


def _read_any_table(path: Path) -> pl.DataFrame:
    """Read a table from a file, inferring the format from the file extension."""
    if path.suffix in (".parquet", ".parq", ".pq"):
        return pl.read_parquet(path)
    if path.suffix == ".csv":
        return pl.read_csv(path)
    if path.suffix in (".jsonl", ".ndjson"):
        return pl.read_ndjson(path)

    msg = f"Unsupported file format: {path.suffix}"
    raise ValueError(msg)


def analyze_response(input_table_data_path: Path | str) -> None:
    """Analyze LLM bug detection data."""
    input_table_data_path = Path(input_table_data_path)
    df = _read_any_table(input_table_data_path)
    logger.info(f"Read {len(df)} rows from {input_table_data_path}")

    out_dir = input_table_data_path.with_name(input_table_data_path.stem + "_analysis")
    out_dir.mkdir(exist_ok=True, parents=True)

    df = df.with_columns(
        challenge_id=pl.col("input_file_rel_path").str.split("/").list.get(0),
        expected_detection_result=(
            pl.when(pl.col("input_file_rel_path").str.contains("/buggy."))
            .then(pl.lit("contains_bug"))
            .when(pl.col("input_file_rel_path").str.contains("/base."))
            .then(pl.lit("no_bug"))
            .otherwise(pl.lit("unknown"))
            .cast(pl.Enum(["contains_bug", "no_bug"]))
        ),
        actual_detection_result=(
            pl.when(pl.col("llm_response").str.contains("No modifications detected"))
            .then(pl.lit("no_bug"))
            .when(pl.col("llm_response").str.len_chars() < pl.lit(50))
            .then(pl.lit("response_very_short"))
            .when(pl.col("llm_response").str.contains("```", literal=True).not_())
            .then(pl.lit("response_contains_no_code_block"))
            .otherwise(pl.lit("contains_bug"))
            .cast(pl.Enum(["contains_bug", "no_bug"]))
        ),
    )
    df.write_parquet(out_dir / "10_llm_bug_detection_data_with_analysis.pq")

    rows_count = df.height
    df_confusion_matrix = (
        df.group_by(["expected_detection_result", "actual_detection_result"])
        .agg(count=pl.len(), percent=(pl.len() / rows_count * 100).round(2))
        .sort(["expected_detection_result", "actual_detection_result"])
    )
    df_confusion_matrix.write_parquet(out_dir / "confusion_matrix.pq")
    logger.info(f"Confusion matrix: {df_confusion_matrix}")

    df_by_challenge = (
        df.group_by("challenge_id")
        .agg(
            total_llm_prompts=pl.len(),
            correct_overall=(
                (
                    pl.col("expected_detection_result")
                    == pl.col("actual_detection_result")
                )
                .cast(pl.Int64)
                .sum()
            ),
            correctly_detected_bug=(
                (
                    (pl.col("expected_detection_result") == "contains_bug")
                    & (pl.col("actual_detection_result") == "contains_bug")
                )
                .cast(pl.Int64)
                .sum()
            ),
            correctly_detected_no_bug=(
                (
                    (pl.col("expected_detection_result") == "no_bug")
                    & (pl.col("actual_detection_result") == "no_bug")
                )
                .cast(pl.Int64)
                .sum()
            ),
        )
        .with_columns(
            correct_overall_pct=(
                (pl.col("correct_overall") / pl.col("total_llm_prompts") * 100).round(2)
            ),
            correctly_detected_bug_pct=(
                (
                    pl.col("correctly_detected_bug")
                    / pl.col("total_llm_prompts")
                    * 100
                    * 2
                ).round(2)
            ),
            correctly_detected_no_bug_pct=(
                (
                    pl.col("correctly_detected_no_bug")
                    / pl.col("total_llm_prompts")
                    * 100
                    * 2
                ).round(2)
            ),
        )
        .sort("challenge_id")
    )
    df_by_challenge.write_parquet(out_dir / "results_by_challenge.pq")
    logger.info(f"Results by challenge: {df_by_challenge}")


def main() -> None:
    """Analyze LLM bug detection data."""
    fire.Fire(analyze_response)  # pyright: ignore[reportUnknownMemberType]


if __name__ == "__main__":
    main()
