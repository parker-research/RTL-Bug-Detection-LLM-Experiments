"""Script to generate histogram of bug report location scores.

High scores indicate that the bug report explanation points to the "correct" code.
"""

# pyright: standard

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import orjson
import pandas as pd
from loguru import logger

from rtl_bug_detection_llm_experiments.common import (
    data_out_dir_for,
    date_for_file_name,
)


def generate_score_histogram(
    csv_paths: dict[str, Path], *, output_png_path: Path
) -> None:
    """Generate a histogram of bug report scores.

    csv_path should point to a CSV produced by `analyze_llm_bug_detection_data.py`, as
    the `21_llm_bug_detection_data_with_scores_no_contents.csv` step.
    """
    n = len(csv_paths)

    if n == 3:  # Special override.
        ncols = 3
        nrows = 1
    else:
        ncols = min(n, 2)
        nrows = (n + ncols - 1) // ncols

    fig, axes = plt.subplots(
        nrows=nrows,
        ncols=ncols,
        figsize=(6 * ncols, 4 * nrows),
        sharey=True,
    )

    # Normalize axes to always be a flat list
    axes_flat = [axes] if n == 1 else list(axes.flat)

    colors = ["#4C72B0", "#DD8452", "#55A868", "#C44E52"]

    for ax, (label, csv_path), color in zip(
        axes_flat, csv_paths.items(), colors, strict=False
    ):
        df = pd.read_csv(csv_path)

        # Filter: both expected and experimental are contains_bug
        filtered = df[
            (df["expected_detection_result"] == "contains_bug")
            & (df["experimental_detection_result"] == "contains_bug")
        ].dropna(subset=["bug_report_score"])

        logger.info(f"[{label}] Rows after filter: {len(filtered)}")
        logger.info(filtered["bug_report_score"].describe())

        ax.hist(
            filtered["bug_report_score"],
            bins=10,
            color=color,
            edgecolor="white",
            linewidth=0.6,
        )

        subplot_title = f"{label} ({len(filtered)}/{len(df) // 2} True Positives)"

        ax.set_title(subplot_title, fontsize=13, fontweight="bold")
        ax.set_xlabel("Bug Report Score", fontsize=11)
        ax.set_ylabel("Count", fontsize=11)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="y", alpha=0.3, linestyle="--")

    # Hide any unused axes (e.g. if n is odd and ncols=2)
    for ax in axes_flat[n:]:
        ax.set_visible(False)

    fig.suptitle(
        "Location Score Distribution of True Positive Bug Detections",
        fontsize=15,
        fontweight="bold",
    )

    plt.tight_layout()
    plt.savefig(output_png_path, dpi=150)
    logger.success(f"Saved: {output_png_path}")


def main() -> None:
    """Generate plots."""
    logger.info("Reading CSV paths from stdin. Pressed Ctrl+D when done.")
    csv_paths = orjson.loads(sys.stdin.read())

    generate_score_histogram(
        csv_paths,
        output_png_path=(
            data_out_dir_for(__file__) / f"histogram_{date_for_file_name()}.png"
        ),
    )


if __name__ == "__main__":
    main()
