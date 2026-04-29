"""Analyze LLM bug detection data for thesis RQ2.

Data is produced by `collect_llm_bug_detection_data.py`.

Outputs (all CSV, written to a sibling `_analysis/` directory):
    10_llm_bug_detection_data_with_analysis.csv  - row-level with detection labels
    20_llm_bug_detection_data_with_scores.csv    - row-level with bug-report scores
    30_overall_metrics.csv                       - Precision / Recall / F1 overall
    31_metrics_by_challenge.csv                  - per-challenge P / R / F1
    32_metrics_by_model.csv                      - per-model P / R / F1 (if model col present)
    33_confusion_matrix.csv                      - raw confusion matrix counts + %
    34_bug_report_scores_summary.csv             - descriptive stats for bug_report_score
"""

from pathlib import Path
from typing import Any

import polars as pl
import tyro
from loguru import logger

from rtl_bug_detection_llm_experiments.assess_bug_report_contents import (
    assess_bug_report_contents_score,
)


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


def _assess_bug_report_contents_score_all_cases(
    base_code: str, buggy_code: str, bug_report: str
) -> float | None:
    """Return bug-report score, or None/0 for edge cases."""
    if base_code == buggy_code:
        return None

    if "```" not in bug_report:
        return 0.0

    return assess_bug_report_contents_score(
        base_code=base_code,
        buggy_code=buggy_code,
        bug_report=bug_report,
    )


def _compute_prf1(
    df: pl.DataFrame,
    group_col: str | None = None,
) -> pl.DataFrame:
    """Compute Precision, Recall, and F1 for the positive class ('contains_bug').

    If `group_col` is provided the metrics are computed per group; otherwise a
    single overall row is returned.

    The function treats 'contains_bug' as the positive class:
        TP - expected contains_bug  AND experimental contains_bug
        FP - expected no_bug        AND experimental contains_bug
        FN - expected contains_bug  AND experimental no_bug
        TN - expected no_bug        AND experimental no_bug

    Macro-averaged P/R/F1 across both classes is also included.
    """

    def _metrics_from_counts(tp: int, fp: int, fn: int, tn: int) -> dict[str, float]:
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        # Metrics for the negative class (no_bug)
        tn_prec = tn / (tn + fn) if (tn + fn) > 0 else 0.0
        tn_rec = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        tn_f1 = (
            2 * tn_prec * tn_rec / (tn_prec + tn_rec) if (tn_prec + tn_rec) > 0 else 0.0
        )

        macro_precision = (precision + tn_prec) / 2
        macro_recall = (recall + tn_rec) / 2
        macro_f1 = (f1 + tn_f1) / 2

        return {
            # Positive class
            "precision_bug": round(precision, 4),
            "recall_bug": round(recall, 4),
            "f1_bug": round(f1, 4),
            # Negative class
            "precision_no_bug": round(tn_prec, 4),
            "recall_no_bug": round(tn_rec, 4),
            "f1_no_bug": round(tn_f1, 4),
            # Macro averages
            "macro_precision": round(macro_precision, 4),
            "macro_recall": round(macro_recall, 4),
            "macro_f1": round(macro_f1, 4),
            # Raw counts
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "total": tp + fp + fn + tn,
            "accuracy": round((tp + tn) / (tp + fp + fn + tn), 4)
            if (tp + fp + fn + tn) > 0
            else 0.0,
        }

    exp = pl.col("experimental_detection_result")
    expd = pl.col("expected_detection_result")

    agg_exprs = [
        ((expd == "contains_bug") & (exp == "contains_bug"))
        .cast(pl.Int64)
        .sum()
        .alias("tp"),
        ((expd == "no_bug") & (exp == "contains_bug")).cast(pl.Int64).sum().alias("fp"),
        ((expd == "contains_bug") & (exp == "no_bug")).cast(pl.Int64).sum().alias("fn"),
        ((expd == "no_bug") & (exp == "no_bug")).cast(pl.Int64).sum().alias("tn"),
    ]

    if group_col:
        grouped = df.group_by(group_col).agg(agg_exprs).sort(group_col)
    else:
        grouped = df.select(agg_exprs)

    rows: list[dict[str, Any]] = []
    for row in grouped.iter_rows(named=True):
        metrics = _metrics_from_counts(row["tp"], row["fp"], row["fn"], row["tn"])
        if group_col:
            metrics[group_col] = row[group_col]
        rows.append(metrics)

    result = pl.DataFrame(rows)

    # Put group col first if present
    if group_col and group_col in result.columns:
        other_cols = [c for c in result.columns if c != group_col]
        result = result.select([group_col, *other_cols])

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def analyze_response(input_table_data_path: Path | str) -> None:
    """Analyze LLM bug detection data and write thesis-ready CSVs."""
    input_table_data_path = Path(input_table_data_path)
    df: pl.DataFrame = _read_any_table(input_table_data_path)
    logger.info(f"Read {len(df)} rows from {input_table_data_path}")

    out_dir = input_table_data_path.with_name(input_table_data_path.stem + "_analysis")
    out_dir.mkdir(exist_ok=True, parents=True)

    # ------------------------------------------------------------------
    # Step 1 - Add detection labels
    # ------------------------------------------------------------------
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
        experimental_detection_result=(
            pl.when(pl.col("llm_response").str.contains("No modifications detected"))
            .then(pl.lit("no_bug"))
            .when(pl.col("llm_response").str.len_chars() < pl.lit(20))
            .then(pl.lit("no_bug"))  # treat degenerate responses as no-detection
            .when(pl.col("llm_response").str.contains("```", literal=True).not_())
            .then(pl.lit("no_bug"))  # no code block → no bug reported
            .otherwise(pl.lit("contains_bug"))
            .cast(pl.Enum(["contains_bug", "no_bug"]))
        ),
    )
    df.write_csv(out_dir / "10_llm_bug_detection_data_with_analysis.csv")

    # ------------------------------------------------------------------
    # Step 2 - Join base file for bug-report scoring
    # ------------------------------------------------------------------
    df = df.join(
        (
            df.filter(pl.col("expected_detection_result") == pl.lit("no_bug"))
            .select(
                "challenge_id",
                base_file_contents=pl.col("input_file_contents"),
            )
            .unique()
        ),
        on="challenge_id",
        how="left",
        validate="m:1",
    )
    df = df.with_columns(
        bug_report_score=(
            pl.struct(["llm_response", "input_file_contents", "base_file_contents"])
            .map_elements(
                lambda row: (
                    _assess_bug_report_contents_score_all_cases(
                        base_code=row["base_file_contents"],
                        buggy_code=row["input_file_contents"],
                        bug_report=row["llm_response"],
                    )
                    if row["base_file_contents"] != row["input_file_contents"]
                    else None
                ),
                return_dtype=pl.Float64,
            )
            .round(4)
        )
    )
    df.write_csv(out_dir / "20_llm_bug_detection_data_with_scores.csv")

    # ------------------------------------------------------------------
    # Step 3 - Confusion matrix (raw counts + %)
    # ------------------------------------------------------------------
    rows_count = df.height
    df_confusion_matrix = (
        df.group_by(["expected_detection_result", "experimental_detection_result"])
        .agg(
            count=pl.len(),
            percent=(pl.len() / rows_count * 100).round(2),
        )
        .sort(["expected_detection_result", "experimental_detection_result"])
    )
    df_confusion_matrix.write_csv(out_dir / "33_confusion_matrix.csv")
    logger.info(f"Confusion matrix:\n{df_confusion_matrix}")

    # ------------------------------------------------------------------
    # Step 4 - Overall Precision / Recall / F1
    # ------------------------------------------------------------------
    df_overall = _compute_prf1(df)
    df_overall.write_csv(out_dir / "30_overall_metrics.csv")
    logger.info(f"Overall metrics:\n{df_overall}")

    # ------------------------------------------------------------------
    # Step 5 - Per-challenge Precision / Recall / F1
    # ------------------------------------------------------------------
    df_by_challenge = _compute_prf1(df, group_col="challenge_id")
    df_by_challenge.write_csv(out_dir / "31_metrics_by_challenge.csv")
    logger.info(f"Per-challenge metrics:\n{df_by_challenge}")

    # ------------------------------------------------------------------
    # Step 6 - Per-model Precision / Recall / F1 (optional)
    #   Looks for a column named 'model', 'llm_model', or 'model_name'.
    # ------------------------------------------------------------------
    model_col_candidates = ["model", "llm_model", "model_name"]
    model_col = next((c for c in model_col_candidates if c in df.columns), None)

    if model_col:
        df_by_model = _compute_prf1(df, group_col=model_col)
        df_by_model.write_csv(out_dir / "32_metrics_by_model.csv")
        logger.info(f"Per-model metrics:\n{df_by_model}")
    else:
        logger.warning(
            "No model column found (looked for: %s). "
            "Skipping per-model breakdown. "
            "Add a column with one of those names to enable it.",
            ", ".join(model_col_candidates),
        )

    # ------------------------------------------------------------------
    # Step 7 - Bug-report score descriptive statistics
    # ------------------------------------------------------------------
    scores = df.filter(pl.col("bug_report_score").is_not_null())["bug_report_score"]
    if scores.len() > 0:
        df_score_summary = pl.DataFrame(
            {
                "metric": [
                    "count",
                    "mean",
                    "median",
                    "std",
                    "min",
                    "p25",
                    "p75",
                    "max",
                ],
                "value": [
                    float(scores.len()),
                    round(scores.mean(), 4),  # type: ignore[arg-type]
                    round(scores.median(), 4),  # type: ignore[arg-type]
                    round(scores.std(), 4),  # type: ignore[arg-type]
                    round(scores.min(), 4),  # type: ignore[arg-type]
                    round(scores.quantile(0.25), 4),  # type: ignore[arg-type]
                    round(scores.quantile(0.75), 4),  # type: ignore[arg-type]
                    round(scores.max(), 4),  # type: ignore[arg-type]
                ],
            }
        )
        df_score_summary.write_csv(out_dir / "34_bug_report_scores_summary.csv")
        logger.info(f"Bug-report score summary:\n{df_score_summary}")

    logger.info(f"All thesis CSVs written to: {out_dir}")


def main() -> None:
    """Analyze LLM bug detection data."""
    tyro.cli(analyze_response)


if __name__ == "__main__":
    main()
