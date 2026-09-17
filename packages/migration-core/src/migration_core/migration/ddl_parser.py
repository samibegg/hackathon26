"""Lightweight PostgreSQL DDL parser for PoC inventory."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ColumnDef:
    name: str
    data_type: str


@dataclass
class TableDef:
    name: str
    columns: list[ColumnDef] = field(default_factory=list)
    references: list[tuple[str, str]] = field(default_factory=list)


_CREATE_TABLE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
    re.IGNORECASE,
)
_REF = re.compile(
    r"REFERENCES\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([a-zA-Z_][a-zA-Z0-9_]*)\)",
    re.IGNORECASE,
)
_COL = re.compile(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s+([A-Z0-9_\(\),\s]+?)(?:,|\s*$)", re.IGNORECASE)


def parse_ddl(ddl_text: str) -> list[TableDef]:
    tables: list[TableDef] = []
    for match in _CREATE_TABLE.finditer(ddl_text):
        table_name = match.group(1)
        start = match.end()
        depth = 1
        i = start
        while i < len(ddl_text) and depth > 0:
            if ddl_text[i] == "(":
                depth += 1
            elif ddl_text[i] == ")":
                depth -= 1
            i += 1
        body = ddl_text[start : i - 1]
        table = TableDef(name=table_name)
        for line in body.splitlines():
            stripped = line.strip().rstrip(",")
            if not stripped or stripped.upper().startswith(
                ("CONSTRAINT", "PRIMARY", "UNIQUE", "CHECK", "FOREIGN")
            ):
                ref = _REF.search(stripped)
                if ref:
                    table.references.append((ref.group(1), ref.group(2)))
                continue
            col_match = _COL.match(stripped)
            if col_match:
                col_name, col_type = col_match.group(1), col_match.group(2).strip()
                if col_name.upper() in ("PRIMARY", "FOREIGN", "UNIQUE", "CHECK"):
                    continue
                table.columns.append(ColumnDef(name=col_name, data_type=col_type.split()[0]))
            ref = _REF.search(stripped)
            if ref:
                table.references.append((ref.group(1), ref.group(2)))
        tables.append(table)
    return tables


def inventory_from_ddl(ddl_text: str) -> dict:
    tables = parse_ddl(ddl_text)
    return {
        "table_count": len(tables),
        "tables": [
            {
                "name": t.name,
                "columns": [{"name": c.name, "type": c.data_type} for c in t.columns],
                "references": [{"table": r[0], "column": r[1]} for r in t.references],
            }
            for t in tables
        ],
    }
