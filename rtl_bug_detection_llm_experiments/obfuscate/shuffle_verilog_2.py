# pyright: basic

import random
import re
import sys
from dataclasses import dataclass


@dataclass
class Chunk:
    kind: str  # e.g., 'param', 'decl', 'assign', 'always', 'inst', 'pinned'
    text: str
    pinned: bool = False


COMMENT_RE = re.compile(
    r"(//.*?$|/\*.*?\*/|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')",
    re.DOTALL | re.MULTILINE,
)

MODULE_RE = re.compile(
    r"\b(module|interface|program)\s+([A-Za-z_]\w*)\b(.*?)(endmodule\b)",
    re.DOTALL | re.IGNORECASE,
)

# Patterns for chunk extraction (simplified)
PARAM_RE = re.compile(r"\b(parameter|localparam)\b.*?;", re.DOTALL)
DECL_RE = re.compile(r"\b(?:wire|reg|logic|bit|int|shortint|longint)\b.*?;", re.DOTALL)
ASSIGN_RE = re.compile(r"\bassign\b.*?;", re.DOTALL)
ALWAYS_RE = re.compile(
    r"\b(always|initial)\b\s*([@\(].*?begin\b.*?end\b|;).*?", re.DOTALL
)
FUNC_RE = re.compile(
    r"\b(function|task)\b.*?end(function|task)\b", re.DOTALL | re.IGNORECASE
)
INST_RE = re.compile(
    r"^[\s]*([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*\(.*?\)\s*;", re.DOTALL | re.MULTILINE
)


def mask_comments(src: str) -> tuple[str, dict]:
    masks = {}

    def repl(m):
        key = f"__MASK_{len(masks)}__"
        masks[key] = m.group(0)
        return key

    masked = re.sub(COMMENT_RE, repl, src)
    return masked, masks


def restore_masks(src: str, masks: dict) -> str:
    for k, v in masks.items():
        src = src.replace(k, v)
    return src


def split_module_body(body: str) -> list[Chunk]:
    # naive linear scan, append chunks
    chunks: list[Chunk] = []
    idx = 0
    patterns = [
        ("param", PARAM_RE),
        ("decl", DECL_RE),
        ("assign", ASSIGN_RE),
        ("always", ALWAYS_RE),
        ("func", FUNC_RE),
        ("inst", INST_RE),
    ]
    n = len(body)
    while idx < n:
        # try to match any pattern at current position (or search next)
        # For simplicity, search for nearest next match among patterns
        nearest = None
        nearest_kind = None
        nearest_span = None
        for kind, pat in patterns:
            m = pat.search(body, idx)
            if m:
                start = m.start()
                if nearest is None or start < nearest:
                    nearest = start
                    nearest_kind = kind
                    nearest_span = m.span()
        if nearest is None:
            # remainder as plain text/pinned
            remainder = body[idx:]
            chunks.append(Chunk(kind="pinned", text=remainder, pinned=True))
            break
        # text before nearest -> pinned text
        if nearest > idx:
            chunks.append(Chunk(kind="pinned", text=body[idx:nearest], pinned=True))
        # matched chunk
        assert nearest_span is not None
        s, e = nearest_span
        this_text = body[s:e]
        assert nearest_kind is not None
        chunks.append(Chunk(kind=nearest_kind, text=this_text, pinned=False))
        idx = e
    return chunks


def reorder_chunks(chunks: list[Chunk], seed: int = 0, mode="safe") -> list[Chunk]:
    # group chunks by kind, shuffle each group's internal order
    random.seed(seed)
    kinds = {}
    for i, c in enumerate(chunks):
        if c.pinned:
            continue
        kinds.setdefault(c.kind, []).append((i, c))
    result = list(chunks)
    for items in kinds.values():
        indices, cs = zip(*items, strict=False)
        shuffled = list(cs)
        random.shuffle(shuffled)
        for pos, cnew in zip(indices, shuffled, strict=False):
            result[pos] = cnew
    return result


def obfuscate_module(module_text: str, seed: int = 0) -> str:
    header_m = re.match(r"^(module|interface|program)\b.*?;\s*", module_text, re.DOTALL)
    if header_m:
        header = header_m.group(0)
        body_start = header_m.end()
        body = module_text[body_start:]
    else:
        # fallback
        return module_text
    # split body up to endmodule (assume endmodule retained outside)
    chunks = split_module_body(body)
    reordered = reorder_chunks(chunks, seed=seed, mode="safe")
    return header + "".join(c.text for c in reordered)


def obfuscate(src: str, seed: int = 0) -> str:
    masked, masks = mask_comments(src)

    # naive: find modules and obfuscate bodies
    def repl(m):
        m.group(1)
        m.group(2)
        module_full = m.group(0)
        # extract whole module block and handle endmodule separately
        # split head and tail as needed (this skeleton assumes balanced)
        # For now simply call obfuscate_module on m.group(0) (improve in real impl)
        return obfuscate_module(module_full, seed=seed)

    out = re.sub(MODULE_RE, repl, masked)
    return restore_masks(out, masks)


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    with open(input_path) as f:
        src = f.read()

    obfuscated = obfuscate(src, seed=42)

    with open(output_path, "w") as f:
        f.write(obfuscated)


if __name__ == "__main__":
    main()
