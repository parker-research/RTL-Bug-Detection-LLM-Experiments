#!/usr/bin/env bash
# merge_all_hackatdac21_branches.sh
# Usage: ./merge_all_hackatdac21_branches.sh [path-to-repo]
# Runs from the repo root by default.

set -u -o pipefail   # don't exit on merge conflicts, but do fail on unset vars

REPO_DIR="${1:-.}"
cd "$REPO_DIR"

# 1) Fetch everything from origin
git fetch --all --prune

# 2) Create the aggregate branch off main (force recreate if exists)
git checkout main
git checkout -B main-all-fixes-merged

# List of branches to merge
branches=(
  remotes/origin/cwe_1199_in_reglk
  remotes/origin/cwe_1221_in_fuse_mem
  remotes/origin/cwe_1254_bootrom
  remotes/origin/cwe_1298_in_dma
  remotes/origin/cwe_1310_riscv_peripheral
  remotes/origin/cwe_1329_in_jtag_hmac
  remotes/origin/fix-cwe-1258-124
  remotes/origin/fix-cwe-1276
  remotes/origin/fix-cwe-1300
  remotes/origin/fix-cwe-1303
  remotes/origin/fix-cwe-440
  remotes/origin/fix_cwe_1191_in_dmi_jtag_sv
  remotes/origin/fix_cwe_1191_in_dmi_jtag_sv_1
  remotes/origin/fix_cwe_1205_in_dmi_jtag_sv
  remotes/origin/fix_cwe_1232
  remotes/origin/fix_cwe_1234_in_reglk
  remotes/origin/fix_cwe_1239
  remotes/origin/fix_cwe_1240
  remotes/origin/fix_cwe_1243_in_aes0
  remotes/origin/fix_cwe_1245
  remotes/origin/fix_cwe_1258_in_aes0
  remotes/origin/fix_cwe_1317_in_clint
  remotes/origin/fix_cwe_226
  remotes/origin/fix_cwe_276
  remotes/origin/fix_cwe_440_HD21bug#51
)

for b in "${branches[@]}"; do
  echo "=== Merging $b ==="
  if ! git merge --no-ff "$b"; then
    echo
    echo "!!! Merge conflict detected while merging $b."
    echo "Resolve the conflict manually, then run:"
    echo "    git add <files>"
    echo "    git commit"
    echo
    read -p "Press ENTER once the conflict is resolved to continue..." _
  fi
done

echo "=== All merges attempted. ==="
