"""Detects potential bugs in SystemVerilog files using an LLM."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, assert_never

import orjson
import tyro
import uuid_extension
from loguru import logger
from tqdm import tqdm

from rtl_bug_detection_llm_experiments.llm import LlmModelNameLiteral, prompt_llm

NO_MODIFICATIONS_DETECTED_STR = "No modifications detected"

PROMPT_TEMPLATE_V1 = """
A malicious actor has modified the following {verilog_or_systemverilog} file to introduce
a bug or security vulnerability.

Please identify where the modification happened. Repeat the full line(s) of code that
you believe have been modified. Place sequential lines in a markdown code block; create
separate code blocks for non-sequential lines.

If you do not believe an actor has introduced a bug or security vulnerability,
then say "{NO_MODIFICATIONS_DETECTED_STR}".

```
{content}
```
"""

PROMPT_TEMPLATE_V2 = """
A malicious actor may have modified the following {verilog_or_systemverilog} file to
introduce a bug or security vulnerability.

If a modification occurred, please identify where the modification happened. Repeat the
full line(s) of code that you believe have been modified. Place sequential lines in a
markdown code block; create separate code blocks for non-sequential lines.

If you do not believe an actor has introduced a bug or security vulnerability,
then say "{NO_MODIFICATIONS_DETECTED_STR}".

```
{content}
```
"""

PROMPT_TEMPLATE_V3 = """
There may be a bug or security vulnerability in the following {verilog_or_systemverilog}
file.

If a bug is present, please identify where the bug is located. Repeat the
full line(s) of code that you believe have the bug. Place sequential lines in a
markdown code block; create separate code blocks for non-sequential lines.

If you do not believe there is a bug or security vulnerability, then say
"{NO_MODIFICATIONS_DETECTED_STR}".

```
{content}
```
"""

PromptVersionLiteral = Literal["v1", "v2", "v3"]

OUTPUT_ROOT = Path(__file__).parent.parent / "out" / "collect_llm_bug_detection_data"
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
    llm_model_name: str


def construct_llm_prompt(
    sv_code: str,
    prompt_version: PromptVersionLiteral,
    verilog_or_systemverilog: Literal["Verilog", "SystemVerilog"],
) -> str:
    """Prompt GPT to analyze a single SystemVerilog file for potential bugs.

    Return the result from GPT, or None if there was an error.
    """
    if prompt_version == "v1":
        prompt_template = PROMPT_TEMPLATE_V1
    elif prompt_version == "v2":
        prompt_template = PROMPT_TEMPLATE_V2
    elif prompt_version == "v3":
        prompt_template = PROMPT_TEMPLATE_V3
    else:
        assert_never(prompt_version)

    return prompt_template.format(
        content=sv_code,
        verilog_or_systemverilog=verilog_or_systemverilog,
        NO_MODIFICATIONS_DETECTED_STR=NO_MODIFICATIONS_DETECTED_STR,
    )


def scan_directory(
    *,
    input_dir: Path | str,
    output_path: Path | str,
    llm_model_name: LlmModelNameLiteral,
    prompt_version: PromptVersionLiteral,
) -> None:
    """Scan all SystemVerilog files in the given directory for potential bugs.

    Args:
        - input_dir: Directory to scan.
        - output_path: Path to write results to. If this is a directory, a single ndjson file
            will be written to that directory with a decent name.
    """
    input_dir = Path(input_dir)

    if Path(output_path).is_dir():
        output_ndjson_file = (
            Path(output_path)
            / f"prompt_{prompt_version}_{llm_model_name}_{log_file_date_time}.ndjson"
        )
    else:
        output_ndjson_file = Path(output_path)

    if output_ndjson_file.exists():
        msg = f"Output file {output_ndjson_file} already exists."
        raise FileExistsError(msg)

    file_count = 0
    results: list[LlmPromptResult] = []
    for file_path in tqdm(
        sorted(list(input_dir.rglob("*.v")) + list(input_dir.rglob("*.sv"))),
        smoothing=0,  # Average over whole duration.
    ):
        if file_path.is_dir():
            continue

        rel_file_path = file_path.relative_to(input_dir)

        file_contents = file_path.read_text(encoding="utf-8")
        prompt = construct_llm_prompt(
            sv_code=file_contents,
            prompt_version=prompt_version,
            verilog_or_systemverilog=(
                "SystemVerilog" if file_path.suffix == ".sv" else "Verilog"
            ),
        )
        response: str = prompt_llm(prompt, model=llm_model_name)

        result = LlmPromptResult(
            uuid=str(uuid_extension.uuid7()),
            input_file_rel_path=rel_file_path.as_posix(),
            input_file_contents=file_contents,
            llm_prompt=prompt,
            llm_response=response,
            llm_model_name=llm_model_name,
        )
        results.append(result)

        with output_ndjson_file.open("ab") as open_file:
            open_file.write(orjson.dumps(result, option=orjson.OPT_APPEND_NEWLINE))

        file_count += 1

    logger.info(f"Scanning complete. Processed {file_count} files.")


def main() -> None:
    """Run main entry point for the script."""
    tyro.cli(scan_directory)


if __name__ == "__main__":
    main()
