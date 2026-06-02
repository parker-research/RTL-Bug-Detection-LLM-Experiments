"""Verilog/SystemVerilog language specification snippets."""

from pathlib import Path

# Conservative set of Verilog/SystemVerilog keywords to exclude (not exhaustive but
# useful).
VERILOG_KEYWORDS = {
    "module",
    "endmodule",
    "input",
    "output",
    "inout",
    "wire",
    "reg",
    "logic",
    "assign",
    "always",
    "begin",
    "end",
    "if",
    "else",
    "for",
    "while",
    "case",
    "endcase",
    "parameter",
    "localparam",
    "generate",
    "endgenerate",
    "genvar",
    "function",
    "endfunction",
    "task",
    "endtask",
    "signed",
    "unsigned",
    "int",
    "integer",
    "real",
    "time",
    "repeat",
    "posedge",
    "negedge",
    "default",
    "package",
    "import",
    "export",
    "class",
    "endclass",
    "new",
    "this",
    "virtual",
    "interface",
    "endinterface",
    "typedef",
    "struct",
    "enum",
    "union",
    "covergroup",
    "cover",
    "fork",
    "join",
    "unique",
    "priority",
    "local",
    "static",
}


VERILOG_DECLARATION_KEYWORDS = (
    "wire",
    "reg",
    "logic",
    "input",
    "output",
    "inout",
    "parameter",
    "localparam",
    "genvar",
    "integer",
    "int",
    "bit",
    "byte",
    "shortint",
)


# Common system identifiers we likely should not touch.
VERILOG_SYSTEM_IDENTIFIERS = {"$display", "$finish", "$time", "$random", "$clog2"}

# Additional keywords loaded from keywords_list.txt (same directory as this file).
# Lines starting with '#' and blank lines are ignored.
_KEYWORDS_FILE = Path(__file__).with_name("keywords_list.txt")
VERILOG_AND_SYSTEMVERILOG_KEYWORDS_FROM_SPEC: frozenset[str] = frozenset(
    line.strip()
    for line in _KEYWORDS_FILE.read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.strip().startswith("#")
)
