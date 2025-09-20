"""Export per-branch single-file diffs vs main for HACK-EVENT/hackatdac21.

Steps implemented:
1) Clone https://github.com/HACK-EVENT/hackatdac21
2) For each remote branch (except main/HEAD):
   - Create out/hackatdac21/<branch_name>/
   - Compute list of files changed vs origin/main
   - If exactly one path changed, copy:
       * main version  -> buggy.<ext>
       * branch version-> base.<ext>
     and write source_path.txt with the repo-relative path.
   - If 0 or >1 files changed, skip and warn.

"""

from pathlib import Path
from typing import Any

import git
import orjson
import polars as pl
from beartype import beartype
from loguru import logger


def ensure_clone(repo_url: str, work_dir: Path) -> git.Repo:
    """Clone the repo into work_dir if needed; otherwise open and fetch."""
    if work_dir.exists():
        repo = git.Repo(work_dir)
        if repo.bare:
            msg = f"Existing repo at {work_dir} is bare"
            raise RuntimeError(msg)
        logger.info("Using existing clone at {}", work_dir)

        # Refresh remotes
        logger.info("Fetching updates from origin…")
        repo.remotes.origin.fetch(prune=True)
    else:
        logger.info("Cloning {} -> {}", repo_url, work_dir)
        repo = git.Repo.clone_from(repo_url, work_dir)
    return repo


def list_remote_branches(repo: git.Repo) -> list[str]:
    """Return remote branch names under origin (e.g., ['feature-x', 'bugfix/y']).

    Excludes 'main'.
    """
    names: list[str] = []
    for ref in repo.remotes.origin.refs:
        # ref.name looks like 'origin/<branch>'
        if ref.name.endswith("/HEAD"):
            continue
        br = ref.name.split("/", 1)[1]
        if br == "main":
            continue
        names.append(br)
    names = sorted(set(names))
    logger.info("Found {} remote branch(es) (excluding main): {}", len(names), names)
    return names


def branch_point_commit(repo: git.Repo, branch_name: str) -> git.Commit:
    """Return the merge-base commit between origin/main and origin/<branch_name>."""
    try:
        main_commit = repo.remotes.origin.refs["main"].commit
    except Exception as e:
        msg = "origin/main not found. Does the repo use 'main' as default branch?"
        raise RuntimeError(msg) from e

    try:
        branch_commit = repo.remotes.origin.refs[branch_name].commit
    except Exception as e:
        msg = f"origin/{branch_name} not found."
        raise RuntimeError(msg) from e

    bases = repo.merge_base(main_commit, branch_commit)
    if not bases:
        msg = f"No merge-base between origin/main and origin/{branch_name}."
        raise RuntimeError(msg)
    return bases[0]


def changed_files_since_branch_point(repo: git.Repo, branch_name: str) -> list[str]:
    """Return repo-relative paths changed from branch-point -> branch tip.

    Includes added/modified/renamed/deleted paths from the branch's perspective.
    Uses destination names for renames.
    """
    base = branch_point_commit(repo, branch_name)
    tip = repo.remotes.origin.refs[branch_name].commit

    try:
        # name-only output keeps rename targets as destination names (relative to tip).
        out = repo.git.diff("--name-only", f"{base.hexsha}", f"{tip.hexsha}")
    except git.GitCommandError as e:
        msg = f"git diff failed for branch {branch_name}: {e}"
        raise RuntimeError(msg) from e

    paths: list[str] = [p.strip() for p in out.splitlines() if p.strip()]
    return paths


def write_blob_at(commit: git.Commit, relative_path: str, dest: Path) -> None:
    """Write the file at relpath from a given commit to dest.

    Raises FileNotFoundError if missing.
    """
    parts = Path(relative_path).parts
    tree = commit.tree
    try:
        for part in parts:
            tree = tree / part  # type: ignore[assignment]
        data: bytes = tree.data_stream.read()  # type: ignore[union-attr]
        assert isinstance(data, bytes)
    except Exception as e:
        msg = f"{relative_path} not found in commit {commit.hexsha[:7]}: {e}"
        raise FileNotFoundError(msg) from e
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def process_one_repository(
    *, repo_name: str, repo_url: str, work_dir: Path, out_root: Path
) -> pl.DataFrame:
    """Parse repository, organize it.

    Note: The branches contain commits which fix a bug, and the main branch contains
    the buggy version. A little bit counter-intuitive, compared to how the experiment
    would be setup.
    """
    repo = ensure_clone(repo_url=repo_url, work_dir=work_dir)

    # Ensure origin/main exists.
    try:
        _ = repo.remotes.origin.refs["main"]
    except Exception as e:
        msg = "origin/main not found. Does the repo use 'main' as default branch?"
        raise RuntimeError(msg) from e

    branches: list[str] = list_remote_branches(repo)

    skipped_count = 0
    processed_count = 0

    output_metadata_list: list[dict[str, Any]] = []

    for branch_name in branches:
        logger.info(f"=== Processing branch: {branch_name} ===")

        if (branch_name == "fix_cwe_1244_in_csr_regfile") and (
            repo_name == "hackatdac19"
        ):
            # This branch is a duplicate of 'fix_cwe_1244_in_csr_regfile_new' - skip.
            logger.debug(
                f'Branch "{branch_name}" in hackatdac19 is a duplicate. Skipping.'
            )
            skipped_count += 1
            continue

        branch_ref = repo.remotes.origin.refs[branch_name]

        # Diff against the branch point with main.
        changed_files_list = changed_files_since_branch_point(repo, branch_name)

        # Exclude README.md changes.
        changed_files_list = sorted(set(changed_files_list) - {"README.md"})

        if len(changed_files_list) == 0:
            logger.warning(
                f'Branch "{branch_name}" has no changes since branch point with main. '
                "Skipping."
            )
            skipped_count += 1
            continue
        if len(changed_files_list) > 1:
            if (branch_name == "fix_cwe_1317_in_clint") and (
                repo_name == "hackatdac21"
            ):
                # https://github.com/HACK-EVENT/hackatdac21/compare/main...fix_cwe_1317_in_clint
                # Special override: Select the most influential file.
                logger.debug(f"Special override for branch {branch_name}")

                assert set(changed_files_list) == {
                    "piton/design/chip/tile/ariane/openpiton/riscv_peripherals.sv",
                    "piton/design/chip/tile/ariane/src/clint/clint.sv",
                }
                changed_files_list = [
                    "piton/design/chip/tile/ariane/src/clint/clint.sv"
                ]

            elif (branch_name == "fix_cwe_1245") and (repo_name == "hackatdac21"):
                # https://github.com/HACK-EVENT/hackatdac21/compare/main...fix_cwe_1245
                # Special override: Select the most influential file with the bug.
                # Note: In the future, we COULD split out both files.
                logger.debug(f"Special override for branch {branch_name}")
                assert set(changed_files_list) == {
                    "piton/design/chip/tile/ariane/src/sha256/sha256.v",
                    "piton/design/chip/tile/ariane/src/dma/dma.sv",
                }
                changed_files_list = [
                    "piton/design/chip/tile/ariane/src/sha256/sha256.v",
                ]

            else:
                logger.warning(
                    f'Branch "{branch_name}" changed {len(changed_files_list)} files '
                    f"since branch point ({'.'.join(changed_files_list)}); skipping."
                )
                skipped_count += 1
                continue

        relpath = changed_files_list[0]
        dest_dir_name = (
            repo_name
            + "_"
            + (
                branch_name.replace("#", "_")
                .replace("fix_", "")
                .replace("()", "")
                .replace("fix-", "")
            )
        )
        (dest_dir := out_root / dest_dir_name).mkdir(parents=True, exist_ok=True)

        ext = Path(relpath).suffix  # includes leading dot, or '' if none
        buggy_name = f"buggy{ext}" if ext else "buggy"
        base_name = f"base{ext}" if ext else "base"

        # Compute branch point.
        base_commit = branch_point_commit(repo, branch_name)

        # Write branch-point version -> buggy.
        try:
            write_blob_at(base_commit, relpath, dest_dir / buggy_name)
        except FileNotFoundError:
            logger.warning(
                f"Path '{relpath}' does not exist at the branch point "
                f"(merge-base with main); skipping branch '{branch_name}'."
            )
            skipped_count += 1
            continue

        # Write branch tip version -> base
        try:
            write_blob_at(branch_ref.commit, relpath, dest_dir / base_name)
        except FileNotFoundError as e:
            logger.warning("{}; skipping branch '{}'", e, branch_name)
            skipped_count += 1
            continue

        # Write metadata.json.
        metadata = {
            "output_folder": dest_dir_name,
            "git_repo": repo_url,
            "branch_name": branch_name,
            "source_path": relpath,
            "buggy_commit": base_commit.hexsha,
            "fixed_commit": branch_ref.commit.hexsha,
        }
        (dest_dir / "metadata.json").write_bytes(
            orjson.dumps(metadata, option=orjson.OPT_INDENT_2)
        )
        output_metadata_list.append(metadata)

        logger.success(
            "Wrote {} (branch-point) and {} (branch tip) for '{}' (source: {})",
            buggy_name,
            base_name,
            branch_name,
            relpath,
        )
        processed_count += 1

    logger.success(
        "Done. Processed: {}, skipped: {}.",
        processed_count,
        skipped_count,
    )

    return pl.DataFrame(output_metadata_list)


@beartype
def get_repo_root_path() -> Path:
    """Return the root directory of the git repository containing this script."""
    repo = git.Repo(
        Path(__file__).parent,
        search_parent_directories=True,
    )
    repo_root = repo.working_tree_dir
    assert repo_root is not None
    return Path(repo_root)


def main() -> None:
    """Run the normalization for both hackatdac19 and hackatdac21."""
    repo_root = get_repo_root_path()

    out_root = (repo_root / "out").resolve()

    df1 = process_one_repository(
        repo_name="hackatdac19",
        repo_url="https://github.com/HACK-EVENT/hackatdac19",
        work_dir=(repo_root / "working" / "hackatdac19").resolve(),
        out_root=out_root,
    )

    df2 = process_one_repository(
        repo_name="hackatdac21",
        repo_url="https://github.com/HACK-EVENT/hackatdac21",
        work_dir=(repo_root / "working" / "hackatdac21").resolve(),
        out_root=out_root,
    )

    df_metadata = pl.concat([df1, df2], how="vertical")

    df_metadata.write_ndjson(out_root / "all_metadata.ndjson")
    df_metadata.write_csv(out_root / "all_metadata.csv")
    df_metadata.write_parquet(out_root / "all_metadata.pq")


if __name__ == "__main__":
    main()
