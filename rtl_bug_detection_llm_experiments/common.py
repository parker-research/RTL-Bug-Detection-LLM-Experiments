"""Common variables for experiments."""

from datetime import datetime
from pathlib import Path

DATA_OUT_DIR = Path(__file__).parent.parent / "out"


def data_out_dir_for(py_file_name: str | Path) -> Path:
    dir_path = DATA_OUT_DIR / Path(py_file_name).stem
    if not dir_path.exists():
        dir_path.mkdir(parents=True)
    return dir_path


def date_for_file_name() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")  # noqa: DTZ005
