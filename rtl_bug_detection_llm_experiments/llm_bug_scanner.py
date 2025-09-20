"""Detects potential bugs in SystemVerilog files using OpenAI's GPT-4o model."""

import random
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import openai
from loguru import logger

client = openai.OpenAI()

PROMPT_TEMPLATE = """
"A malicious actor has modified the following SystemVerilog file (part of the OpenTitan
core) to introduce a bug or security vulnerability.

Please identify where the modification happened.

If you do not believe a modification happened, then say "No modifications detected."

```systemverilog
{content}
```
"""

OUTPUT_ROOT = Path("./scanner_58_output")
OUTPUT_ROOT.mkdir(exist_ok=True)

log_file_date_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")  # noqa: DTZ005
logger.add(OUTPUT_ROOT / f"scanner_58_{log_file_date_time}.log")


def analyze_sv_file(file_path: Path) -> str | None:
    """Prompt GPT to analyze a single SystemVerilog file for potential bugs.

    Return the result from GPT, or None if there was an error.
    """
    content = file_path.read_text(encoding="utf-8")

    logger.info(f"Sending {file_path.name} to ChatGPT...")

    response = client.responses.create(
        model="gpt-4o",
        input=PROMPT_TEMPLATE.format(content=content),
        temperature=0.2,  # Lower is less creative.
    )

    reply = response.output_text
    return reply.strip()


def scan_directory(input_dir: Path) -> None:
    """Scan all SystemVerilog files in the given directory for potential bugs."""
    for file_path in input_dir.rglob("*.sv"):
        if file_path.is_dir():
            continue

        rel_file_path = file_path.relative_to(input_dir)

        file_contents = file_path.read_text(encoding="utf-8")
        # Check if the file already has a marker indicating it has been analyzed.
        if re.search(r"//.+FOUND.+Bug", file_contents, re.IGNORECASE):
            logger.success(
                f"Skipping file which has marker of found bug: {rel_file_path}"
            )
            continue

        analysis = analyze_sv_file(file_path)
        if analysis is None:
            continue

        msg = "\n".join([f"Analysis for {rel_file_path}:", analysis])

        if "No modifications detected" in analysis:
            logger.info(f"No modifications detected in {rel_file_path}\n{analysis}")
            continue

        logger.success(f"Found a bug in {rel_file_path}:\n{msg}")

        # Create a new folder for the bug and copy the file there.
        # Then, write the analysis to a text file.
        bug_folder = (
            OUTPUT_ROOT.joinpath(file_path.relative_to(input_dir).parent)
            / file_path.stem
        )
        bug_folder.mkdir(parents=True, exist_ok=True)

        bug_id = random.randint(100, 400)

        # Copy the orig file there for easy reference.
        shutil.copy(file_path, bug_folder / file_path.name)

        # Write the analysis to a text file.
        (bug_folder / f"bug_{bug_id}_analysis.md").write_text(analysis)


def main() -> None:
    """Run the scanner on a given directory."""
    if len(sys.argv) != 2:  # noqa: PLR2004
        logger.warning("Usage: python scanner_58.py <path_to_directory>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.is_dir():
        logger.warning(f"Error: {input_path} is not a directory")
        sys.exit(1)

    scan_directory(input_path)


if __name__ == "__main__":
    main()
