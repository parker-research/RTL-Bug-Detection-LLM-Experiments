"""Export per-branch single-file diffs vs main for HACK-EVENT/hackatdac21.

Steps implemented:
1) Clone https://github.com/HACK-EVENT/hackatdac21 into Path(__file__).with_name("working")
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

import git
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


def changed_files_vs_main(repo: git.Repo, branch_name: str) -> list[str]:
    """Return a list of repo-relative paths changed between main and <branch_name>.

    Includes added/modified/renamed/deleted paths from the branch's perspective.
    """
    a = repo.remotes.origin.refs["main"].commit
    b = repo.remotes.origin.refs[branch_name].commit
    # Use name-only output via git to keep rename paths as destination names.
    try:
        out = repo.git.diff("--name-only", f"{a.hexsha}", f"{b.hexsha}")
    except git.GitCommandError as e:
        msg = f"git diff failed for branch {branch_name}: {e}"
        raise RuntimeError(msg) from e

    paths: list[str] = [p.strip() for p in out.splitlines() if p.strip()]
    return paths


def write_blob_at(commit: git.Commit, relative_path: str, dest: Path) -> None:
    """Write the file at relpath from a given commit to dest.

    Raises FileNotFoundError if missing.
    """
    # Navigate the tree to the blob
    parts = Path(relative_path).parts
    tree = commit.tree
    try:
        for part in parts:
            tree = tree / part  # type: ignore[assignment]
        blob = tree  # type: ignore[assignment]
        data: bytes = blob.data_stream.read()
    except Exception as e:
        msg = f"{relative_path} not found in commit {commit.hexsha[:7]}: {e}"
        raise FileNotFoundError(msg) from e
    dest.parent.mkdir(parents=True, exist_ok=True)

    dest.write_bytes(data)


def main(*, repo_url: str, work_dir: Path, out_root: Path) -> None:
    """Run the normalization process."""
    repo = ensure_clone(repo_url=repo_url, work_dir=work_dir)

    # Make sure we have origin/main
    try:
        main_ref = repo.remotes.origin.refs["main"]
    except Exception as e:
        msg = "origin/main not found. Does the repo use 'main' as default branch?"
        raise RuntimeError(msg) from e

    branches = list_remote_branches(repo)

    skipped = 0
    processed = 0

    for br in branches:
        logger.info("\n=== Processing branch: {} ===", br)
        branch_ref = repo.remotes.origin.refs[br]
        changed_files_list = changed_files_vs_main(repo, br)

        # Exclude README.md changes.
        changed_files_list = sorted(set(changed_files_list) - {"README.md"})

        if len(changed_files_list) == 0:
            logger.warning("Branch '{}' has no changes vs main; skipping.", br)
            skipped += 1
            continue
        if len(changed_files_list) > 1:
            logger.warning(
                "Branch '{}' changed {} files vs main ({}); skipping as per requirement.",
                br,
                len(changed_files_list),
                ", ".join(changed_files_list),
            )
            skipped += 1
            continue

        relpath = changed_files_list[0]
        dest_dir = out_root / br
        dest_dir.mkdir(parents=True, exist_ok=True)

        ext = Path(relpath).suffix  # includes leading dot, or '' if none
        buggy_name = f"buggy{ext}" if ext else "buggy"
        base_name = f"base{ext}" if ext else "base"

        # Write main version -> buggy
        try:
            write_blob_at(main_ref.commit, relpath, dest_dir / buggy_name)
        except FileNotFoundError:
            logger.warning(
                "Path '{}' does not exist on origin/main; skipping branch '{}'.",
                relpath,
                br,
            )
            skipped += 1
            continue

        # Write branch version -> base
        try:
            write_blob_at(branch_ref.commit, relpath, dest_dir / base_name)
        except FileNotFoundError as e:
            logger.warning("{}; skipping branch '{}'", e, br)
            skipped += 1
            continue

        # Write source_path.txt
        (dest_dir / "source_path.txt").write_text(relpath + "\n", encoding="utf-8")

        logger.success(
            "Wrote {} and {} for '{}' (source: {})",
            buggy_name,
            base_name,
            br,
            relpath,
        )
        processed += 1

    logger.info(
        "\nDone. Processed: {}, skipped: {}. Output root: {}",
        processed,
        skipped,
        out_root,
    )


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


if __name__ == "__main__":
    repo_root = get_repo_root_path()

    main(
        repo_url="https://github.com/HACK-EVENT/hackatdac19",
        work_dir=(repo_root / "working" / "hackatdac19").resolve(),
        out_root=(repo_root / "out" / "hackatdac19").resolve(),
    )

    main(
        repo_url="https://github.com/HACK-EVENT/hackatdac21",
        work_dir=(repo_root / "working" / "hackatdac21").resolve(),
        out_root=(repo_root / "out" / "hackatdac21").resolve(),
    )
