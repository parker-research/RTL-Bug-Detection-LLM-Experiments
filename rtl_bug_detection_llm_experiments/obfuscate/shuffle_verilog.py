"""Reorders reorderable blocks (focus on continuous assigns) inside Verilog files.

Supports Verilog and SystemVerilog files.

Usage:
    python verilog_obfuscator.py input.v [-o out.v] [--inplace] [--seed SEED]
    python verilog_obfuscator.py --help

Notes:
- Conservative approach: only reorders consecutive assign statements that form a block.
- Uses a simple data-dependency heuristic to avoid reordering dependent assigns.

"""

import argparse
import random
import re
from collections import defaultdict, deque


# ---------- Masking utils (comments and strings) ----------
def mask_patterns(text: str) -> tuple[str, list[str]]:
    """Replace comments and string literals with placeholders and return masked text + list of originals.

    Placeholders are __MASK_0__, __MASK_1__, ...
    """
    # order matters: block comments, line comments, strings (double and single), backtick macros?
    regex = re.compile(
        r"(?P<block>/\*.*?\*/)|(?P<line>//[^\n]*)|(?P<dstr>\"(?:\\.|[^\"\\])*?\")|(?P<sstr>'(?:\\.|[^'\\])*?')",
        re.DOTALL,
    )

    parts: list[str] = []
    last = 0
    masks: list[str] = []

    for m in regex.finditer(text):
        parts.append(text[last : m.start()])
        orig = m.group(0)
        placeholder = f"__MASK_{len(masks)}__"
        masks.append(orig)
        parts.append(placeholder)
        last = m.end()
    parts.append(text[last:])
    masked = "".join(parts)
    return masked, masks


def restore_masks(text: str, masks: list[str]) -> str:
    """Restore masked patterns in text using the provided list of originals."""
    for i, orig in enumerate(masks):
        text = text.replace(f"__MASK_{i}__", orig)
    return text


# ---------- Utilities ----------
ident_re = re.compile(r"\b([A-Za-z_]\w*)\b")


def extract_identifiers(s: str) -> list[str]:
    """Return identifiers in the string (very coarse)."""
    return ident_re.findall(s)


# ---------- Assign handling ----------
assign_stmt_re = re.compile(
    r"\bassign\b\s*(?:#\s*\d+\s*)?(.*?);", re.DOTALL
)  # captures content after 'assign' up to ;
# We'll capture the full assign including 'assign ... ;' when substituting
full_assign_re = re.compile(r"(\bassign\b\s*(?:#\s*\d+\s*)?.*?;)", re.DOTALL)


def get_lhs_rhs_from_assign(assign_text: str) -> tuple[str | None, str | None]:
    """Try to split an assign statement into LHS and RHS.

    Very simple: look for the first '=' that is not inside parentheses/brackets.
    Returns lhs_text, rhs_text (strings) or (None, None) if can't parse.
    """
    # Remove leading 'assign'
    t = assign_text.strip()
    if t.startswith("assign"):
        t = t[len("assign") :].strip()
    # strip trailing ';'
    t = t.removesuffix(";")
    # find '=' balanced by parentheses/brackets
    depth = 0
    for i, ch in enumerate(t):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "=" and depth == 0:
            lhs = t[:i].strip()
            rhs = t[i + 1 :].strip()
            return lhs, rhs
    return None, None


def extract_lhs_ident(lhs_text: str) -> list[str]:
    """Extract identifiers from LHS of an assign statement."""
    return extract_identifiers(lhs_text)


def extract_rhs_ident(rhs_text: str) -> list[str]:
    """Extract identifiers from RHS of an assign statement."""
    return extract_identifiers(rhs_text)


# ---------- Dependency grouping & ordering ----------
def build_dependency_graph(
    assign_texts: list[str],
) -> tuple[dict[int, list[int]], dict[int, list[int]]]:
    """Build a simple dependency graph among assigns.

    Nodes are indices into assign_texts.

    Edge i -> j means j depends on i (i's LHS appears in j's RHS).
    Returns (graph_outgoing, graph_incoming).
    """
    lhs_sets: list[set[str]] = []
    rhs_sets: list[set[str]] = []
    for a in assign_texts:
        lhs_text, rhs_text = get_lhs_rhs_from_assign(a)
        lhs_ids = set[str]()
        rhs_ids = set[str]()
        if lhs_text:
            lhs_ids.update(extract_lhs_ident(lhs_text))
        if rhs_text:
            rhs_ids.update(extract_rhs_ident(rhs_text))
        lhs_sets.append(lhs_ids)
        rhs_sets.append(rhs_ids)

    graph_out: defaultdict[int, list[int]] = defaultdict(list[int])
    graph_in: defaultdict[int, list[int]] = defaultdict(list[int])
    n = len(assign_texts)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            # if any lhs identifier from i is used in rhs of j, then j depends on i
            if lhs_sets[i] & rhs_sets[j]:
                graph_out[i].append(j)
                graph_in[j].append(i)
    return graph_out, graph_in


def strongly_connected_components(
    n: int, graph_out: dict[int, list[int]]
) -> list[list[int]]:
    """Tarjan's algorithm for SCC.

    Returns list of components (each component is list of node indices).
    """
    index = 0
    indices = [-1] * n
    lowlink = [0] * n
    stack: list[int] = []
    onstack = [False] * n
    comps: list[list[int]] = []

    def strongconnect(v: int) -> None:
        nonlocal index
        indices[v] = index
        lowlink[v] = index
        index += 1
        stack.append(v)
        onstack[v] = True

        w: int
        for w in graph_out.get(v, []):
            if indices[w] == -1:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif onstack[w]:
                lowlink[v] = min(lowlink[v], indices[w])
        if lowlink[v] == indices[v]:
            comp: list[int] = []
            while True:
                w = stack.pop()
                onstack[w] = False
                comp.append(w)
                if w == v:
                    break
            comps.append(comp)

    for v in range(n):
        if indices[v] == -1:
            strongconnect(v)
    return comps


def topological_sort_component(
    nodes: list[int], graph_out: dict[int, list[int]], graph_in: dict[int, list[int]]
) -> list[int] | None:
    """Try a topo sort for a subgraph induced by nodes.

    If a cycle is detected, return None.
    """
    nodes_set = set(nodes)
    indeg = dict.fromkeys(nodes, 0)
    for u in nodes:
        for v in graph_out.get(u, []):
            if v in nodes_set:
                indeg[v] += 1
    q = deque([u for u in nodes if indeg[u] == 0])
    order: list[int] = []
    while q:
        u = q.popleft()
        order.append(u)
        for v in graph_out.get(u, []):
            if v in nodes_set:
                indeg[v] -= 1
                if indeg[v] == 0:
                    q.append(v)
    if len(order) != len(nodes):
        return None
    return order


# ---------- Main transformation ----------
def reorder_assign_blocks_in_module(
    module_text: str, seed: int | None = None, min_block_size: int = 2
) -> tuple[str, int]:
    """Find consecutive assign statement blocks within the module_text and reorder them when safe.

    Returns (new_module_text, count_reordered_blocks).
    """
    # find all assign statements and their spans
    assigns: list[tuple[int, int, str]] = []
    for m in full_assign_re.finditer(module_text):
        assigns.append(
            (m.start(1), m.end(1), m.group(1))
        )  # group 1 is the full "assign ... ;"

    if not assigns:
        return module_text, 0

    # Build a quick index of positions -> assign index
    # We'll scan the module_text, find contiguous assign groups (i.e., sequences of assigns with only whitespace/comments between)
    reordered_count = 0
    out: list[str] = []
    lastpos = 0
    i = 0
    n = len(assigns)

    while i < n:
        start_i, end_i, text_i = assigns[i]
        # If there is non-whitespace/non-placeholder content between lastpos and start_i that is not just whitespace or placeholders,
        # we still treat assigns as separate unless they are contiguous with only whitespace/comments (but comments were masked).
        # For simplicity: if the gap between this assign and the next assign contains only whitespace or masked tokens, we consider contiguous.
        block_indices = [i]
        j = i + 1
        while j < n:
            prev_end = assigns[j - 1][1]
            next_start = assigns[j][0]
            gap = module_text[prev_end:next_start]
            if gap.strip("") == "" or re.fullmatch(r"(?:\s|__MASK_\d+__)*", gap):
                block_indices.append(j)
                j += 1
            else:
                break
        # now block_indices [i..j-1] is a contiguous block candidate
        if len(block_indices) >= min_block_size:
            # extract assign texts
            assign_texts = [assigns[k][2] for k in block_indices]
            # build dependency graph
            graph_out, graph_in = build_dependency_graph(assign_texts)
            comp_list = strongly_connected_components(len(assign_texts), graph_out)
            # comp_list are components in terms of node indices 0..len(assign_texts)-1
            # Convert to original assign indices
            comps_original_idx = []
            for comp in comp_list:
                comps_original_idx.append([block_indices[idx] for idx in comp])

            # For each component, attempt topo sort (within component). If cycle -> keep original order.
            components_ordered: list[list[int]] = []
            for comp in comp_list:
                # comp is in terms of 0..m-1 indices
                topo = topological_sort_component(comp, graph_out, graph_in)
                if topo is None:
                    # map comp to original order (preserve relative)
                    comp_sorted = sorted(comp)
                else:
                    comp_sorted = topo
                # map back to absolute assign index (in module)
                components_ordered.append([block_indices[idx] for idx in comp_sorted])

            # Now we have list of components (each a list of absolute assign indices). We can shuffle these components,
            # but must keep the internal order of each component as determined.
            if len(components_ordered) > 1:
                rng = random.Random(seed)
                # Shuffle the components positions
                indices = list(range(len(components_ordered)))
                rng.shuffle(indices)
                shuffled_components = [components_ordered[idx] for idx in indices]
                # For conservative approach: if a component has a cycle (we detected earlier), do not move *that* component relative to others?
                # Simpler: if any component had cycle, avoid moving internal order; but we can still shuffle components.
                # Reconstruct the new order of assigns for this block
                new_assign_order: list[int] = []
                for comp in shuffled_components:
                    new_assign_order.extend(comp)
                # Replace text segment covering this whole block with assigns in new order
                block_start = assigns[block_indices[0]][0]
                block_end = assigns[block_indices[-1]][1]
                # pieces: before block_start, then new assigns in order, then continue
                out.append(module_text[lastpos:block_start])
                for ai in new_assign_order:
                    out.append(module_text[assigns[ai][0] : assigns[ai][1]])
                    out.append("\n")  # keep separation
                lastpos = block_end
                reordered_count += 1
            else:
                # only one component (nothing to shuffle)
                out.append(module_text[lastpos : assigns[block_indices[-1]][1]])
                lastpos = assigns[block_indices[-1]][1]
        else:
            # block too small -> don't reorder
            out.append(module_text[lastpos : assigns[block_indices[-1]][1]])
            lastpos = assigns[block_indices[-1]][1]

        i = j

    out.append(module_text[lastpos:])
    new_text = "".join(out)
    return new_text, reordered_count


# ---------- Module extraction ----------
module_re = re.compile(r"\bmodule\b\s+([A-Za-z_]\w*)\b.*?\bendmodule\b", re.DOTALL)


def process_file(
    text: str, seed: int | None = None, min_block_size: int = 2
) -> tuple[str, int]:
    """For each module in text, reorder assign blocks.

    Returns (new_text, total_reordered_blocks).
    """
    masked, masks = mask_patterns(text)
    # find modules in masked text
    out_parts: list[str] = []
    last = 0
    total = 0
    for m in module_re.finditer(masked):
        out_parts.append(masked[last : m.start()])
        mod_text_masked = masked[m.start() : m.end()]
        # apply reorder inside module
        new_mod_masked, count = reorder_assign_blocks_in_module(
            mod_text_masked, seed=seed, min_block_size=min_block_size
        )
        total += count
        out_parts.append(new_mod_masked)
        last = m.end()
    out_parts.append(masked[last:])
    combined_masked = "".join(out_parts)
    restored = restore_masks(combined_masked, masks)
    return restored, total


# ---------- CLI ----------
def cli() -> None:
    ap = argparse.ArgumentParser(
        description="Verilog/SystemVerilog obfuscator that reorders reorderable blocks (assigns)."
    )
    ap.add_argument("infile", help="Input Verilog/SystemVerilog file")
    ap.add_argument("-o", "--out", help="Output file (default: stdout)")
    ap.add_argument("--inplace", action="store_true", help="Overwrite input file")
    ap.add_argument(
        "--seed", type=int, default=None, help="Random seed for deterministic shuffling"
    )
    ap.add_argument(
        "--min-block-size",
        type=int,
        default=2,
        help="Minimum number of consecutive assigns to consider reordering (default 2)",
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="Don't write output; just report changes"
    )
    args = ap.parse_args()

    with open(args.infile, encoding="utf-8") as f:
        text = f.read()

    new_text, count = process_file(
        text, seed=args.seed, min_block_size=args.min_block_size
    )

    if args.dry_run:
        return

    if args.inplace:
        with open(args.infile, "w", encoding="utf-8") as f:
            f.write(new_text)
    elif args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(new_text)
    else:
        pass


if __name__ == "__main__":
    cli()
