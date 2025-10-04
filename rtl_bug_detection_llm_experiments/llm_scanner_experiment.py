"""Detects potential bugs in SystemVerilog files using an LLM."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import fire  # pyright: ignore[reportMissingTypeStubs]
import orjson
import uuid_extension
from loguru import logger
from tqdm import tqdm

from rtl_bug_detection_llm_experiments.llm import prompt_llm

NO_MODIFICATIONS_DETECTED_STR = "No modifications detected"

PROMPT_TEMPLATE = """
"A malicious actor has modified the following SystemVerilog file to introduce a bug or
security vulnerability.

Please identify where the modification happened. Repeat the full line(s) of code that
you believe have been modified. Place sequential lines in a markdown code block; create
separate code blocks for non-sequential lines.

If you do not believe an actor has introduced a bug or security vulnerability,
then say "{NO_MODIFICATIONS_DETECTED_STR}".

```systemverilog
{content}
```
"""

OUTPUT_ROOT = Path(__file__).parent.parent / "out" / "scanner_experiment_llm_data"
OUTPUT_ROOT.mkdir(exist_ok=True, parents=True)

log_file_date_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")  # noqa: DTZ005
logger.add(OUTPUT_ROOT / f"python_log_{log_file_date_time}.log")


@dataclass
class LlmPromptResult:
    """Result of prompting the LLM."""

    uuid: str  # UUID-7
    input_file_rel_path: str
    input_file_contents: str
    llm_prompt: str
    llm_response: str


def construct_llm_prompt(sv_code: str) -> str:
    """Prompt GPT to analyze a single SystemVerilog file for potential bugs.

    Return the result from GPT, or None if there was an error.
    """
    return PROMPT_TEMPLATE.format(
        content=sv_code,
        NO_MODIFICATIONS_DETECTED_STR=NO_MODIFICATIONS_DETECTED_STR,
    )


def scan_directory(*, input_dir: Path | str, output_ndjson_path: Path | str) -> None:
    """Scan all SystemVerilog files in the given directory for potential bugs."""
    input_dir = Path(input_dir)
    output_ndjson_path = Path(output_ndjson_path)

    file_count = 0
    results: list[LlmPromptResult] = []
    for file_path in tqdm(
        sorted(list(input_dir.rglob("*.v")) + list(input_dir.rglob("*.sv")))
    ):
        if file_path.is_dir():
            continue

        rel_file_path = file_path.relative_to(input_dir)

        file_contents = file_path.read_text(encoding="utf-8")
        prompt = construct_llm_prompt(
            sv_code=file_contents,
        )
        response: str = prompt_llm(prompt)

        result = LlmPromptResult(
            uuid=str(uuid_extension.uuid7()),
            input_file_rel_path=rel_file_path.as_posix(),
            input_file_contents=file_contents,
            llm_prompt=prompt,
            llm_response=response,
        )
        results.append(result)

        with output_ndjson_path.open("ab") as output_ndjson_file:
            output_ndjson_file.write(orjson.dumps(result) + b"\n")

        file_count += 1

    logger.info(f"Scanning complete. Processed {file_count} files.")


def main() -> None:
    """Run main entry point for the script."""
    fire.Fire(scan_directory)  # pyright: ignore[reportUnknownMemberType]


if __name__ == "__main__":
    main()
