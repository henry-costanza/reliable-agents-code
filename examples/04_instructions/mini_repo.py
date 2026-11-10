"""Chapter 4: Brindle's billing library, and tools to work on it in memory.

The project lives in a dict of path -> text, so every run starts from the
same files and the result of a run can be checked without touching disk.
"""

from agentkit import Tool

FILES = {
    "README.md": "# brindle-billing\n\nBrindle's library for invoice totals.\n",
    "CHANGELOG.md": (
        "# Changelog\n\n## Unreleased\n\n"
        "## 0.2.0\n\n- subtotal_cents: sum of all invoice lines.\n\n"
        "## 0.1.0\n\n- Invoice and Line models.\n"
    ),
    "invoices/__init__.py": "",
    "invoices/model.py": (
        "from dataclasses import dataclass\n\n\n"
        "@dataclass(frozen=True)\n"
        "class Line:\n"
        "    description: str\n"
        "    quantity: int\n"
        "    unit_price_cents: int\n\n\n"
        "@dataclass(frozen=True)\n"
        "class Invoice:\n"
        "    lines: tuple[Line, ...]\n"
        "    paid_cents: int = 0\n"
    ),
    "invoices/totals.py": (
        "from invoices.model import Invoice\n\n\n"
        "def subtotal_cents(invoice: Invoice) -> int:\n"
        '    """Sum of quantity times unit price over all lines."""\n'
        "    return sum(l.quantity * l.unit_price_cents for l in invoice.lines)\n"
    ),
    "tests/unit/test_model.py": (
        "from invoices.model import Invoice, Line\n\n\n"
        "def test_invoice_starts_unpaid():\n"
        '    assert Invoice((Line("Tea", 1, 250),)).paid_cents == 0\n'
    ),
}

# --8<-- [start:tasks]
TASKS = {
    "total_due": (
        "Add a function total_due(invoice) to invoices/totals.py "
        "that returns the amount still to pay. Make the change "
        "with the tools."
    ),
    "average_line_price": (
        "Add a function average_line_price(invoice) to "
        "invoices/totals.py that returns the average unit price "
        "of the invoice lines. Make the change with the tools."
    ),
}
# --8<-- [end:tasks]

PATH = {"type": "string", "minLength": 1}


def workspace_tools(files: dict[str, str]) -> list[Tool]:
    """list_files, read_file and write_file over `files`, changed in place."""
    def read(path: str) -> str:
        if path not in files:
            raise FileNotFoundError(path)
        return files[path]

    def write(path: str, content: str) -> str:
        files[path] = content
        return f"wrote {len(content)} characters to {path}"

    def schema(**props):
        return {"type": "object", "properties": props,
                "required": list(props), "additionalProperties": False}

    return [
        Tool("list_files", "List every file in the project.", schema(),
             lambda: "\n".join(sorted(files))),
        Tool("read_file", "Return the text of one file.", schema(path=PATH),
             read),
        Tool("write_file", "Create or replace one file with new text.",
             schema(path=PATH, content={"type": "string"}), write),
    ]
