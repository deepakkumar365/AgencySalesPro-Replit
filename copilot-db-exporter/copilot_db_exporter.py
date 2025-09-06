#!/usr/bin/env python3
"""
Copilot DB Exporter

Exports a concise database overview for AI assistants:
- Tables, columns, types, PK/NOT NULL/defaults
- Foreign keys
- Row counts
- Sample rows per table

Also can emit a SQL file for the schema and optional sample INSERTs.

Supports SQLite (path to .db file). Output: markdown (default) or JSON.

Usage examples (Windows paths):
python "d:\\Project\\Workouts\\GitHub\\AgencySalesPro-Replit\\copilot-db-exporter\\copilot_db_exporter.py" \
  --db "d:\\Project\\Workouts\\GitHub\\AgencySalesPro-Replit\\instance\\agency_sales.db" \
  --format markdown --limit 5 \
  --out "d:\\Project\\Workouts\\GitHub\\AgencySalesPro-Replit\\attached_assets\\db_overview.md" \
  --sql-out "d:\\Project\\Workouts\\GitHub\\AgencySalesPro-Replit\\attached_assets\\db_schema.sql" \
  --sql-inserts

python "d:\\Project\\Workouts\\GitHub\\AgencySalesPro-Replit\\copilot-db-exporter\\copilot_db_exporter.py" \
  --db "d:\\Project\\Workouts\\GitHub\\AgencySalesPro-Replit\\instance\\agency_sales.db" \
  --format json --include products,orders \
  --out "d:\\Project\\Workouts\\GitHub\\AgencySalesPro-Replit\\attached_assets\\db_overview.json"
"""
from __future__ import annotations
import argparse
import json
import os
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

# ------------------------------
# SQLite Introspection Utilities
# ------------------------------

def connect_sqlite(db_path: str) -> sqlite3.Connection:
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def list_tables(conn: sqlite3.Connection) -> List[str]:
    # Exclude internal SQLite tables
    sql = """
        SELECT name FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """
    return [r[0] for r in conn.execute(sql)]


def get_table_columns(conn: sqlite3.Connection, table: str) -> List[Dict[str, Any]]:
    cols = []
    for r in conn.execute(f"PRAGMA table_info('{table}')"):
        cols.append({
            "cid": r[0],
            "name": r[1],
            "type": r[2],
            "notnull": bool(r[3]),
            "default": r[4],
            "pk": bool(r[5]),
        })
    return cols


def get_foreign_keys(conn: sqlite3.Connection, table: str) -> List[Dict[str, Any]]:
    fks = []
    for r in conn.execute(f"PRAGMA foreign_key_list('{table}')"):
        fks.append({
            "id": r[0],
            "seq": r[1],
            "table": r[2],
            "from": r[3],
            "to": r[4],
            "on_update": r[5],
            "on_delete": r[6],
            "match": r[7],
        })
    return fks


def get_row_count(conn: sqlite3.Connection, table: str) -> int:
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM '{table}'").fetchone()[0])
    except sqlite3.DatabaseError:
        return -1


def get_sample_rows(conn: sqlite3.Connection, table: str, limit: int) -> List[Dict[str, Any]]:
    try:
        rows = conn.execute(f"SELECT * FROM '{table}' ORDER BY rowid LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.DatabaseError:
        return []

# ------------------------------
# Additional DDL Introspection
# ------------------------------

def get_table_create_sql(conn: sqlite3.Connection, table: str) -> Optional[str]:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row[0] if row and row[0] else None


def get_indexes_sql(conn: sqlite3.Connection, table: str) -> List[Tuple[str, str]]:
    # Only user-defined indexes (ignore auto indexes with NULL sql)
    rows = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL ORDER BY name",
        (table,),
    ).fetchall()
    return [(r[0], r[1]) for r in rows if r[1]]


def get_triggers_sql(conn: sqlite3.Connection, table: str) -> List[Tuple[str, str]]:
    rows = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='trigger' AND tbl_name=? ORDER BY name",
        (table,),
    ).fetchall()
    return [(r[0], r[1]) for r in rows if r[1]]


def get_views_sql(conn: sqlite3.Connection) -> List[Tuple[str, str]]:
    rows = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='view' ORDER BY name"
    ).fetchall()
    return [(r[0], r[1]) for r in rows if r[1]]


# ------------------------------
# Formatting Helpers
# ------------------------------

def truncate_value(val: Any, max_len: int = 200) -> Any:
    if val is None:
        return None
    s = str(val)
    if len(s) > max_len:
        return s[:max_len] + "…"  # ellipsis to indicate truncation
    return s


def to_markdown(db_path: str, data: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# Database Overview\n")
    lines.append(f"- **Database**: `{db_path}`\n")
    lines.append(f"- **Tables**: {len(data['tables'])}\n")

    for t in data["tables"]:
        lines.append(f"\n## Table: {t['name']}\n")
        lines.append(f"- **Row count**: {t['row_count']}\n")

        # Columns
        lines.append("\n### Columns\n")
        lines.append("| name | type | pk | not null | default |")
        lines.append("|---|---|---|---|---|")
        for c in t["columns"]:
            default_str = ("`" + str(c["default"]) + "`") if c["default"] is not None else ""
            lines.append(f"| `{c['name']}` | `{c['type']}` | {int(c['pk'])} | {int(c['notnull'])} | {default_str} |")

        # Foreign Keys
        lines.append("\n### Foreign Keys\n")
        if t["foreign_keys"]:
            lines.append("| from | to table | to column | on update | on delete | match |")
            lines.append("|---|---|---|---|---|---|")
            for fk in t["foreign_keys"]:
                lines.append(
                    f"| `{fk['from']}` | `{fk['table']}` | `{fk['to']}` | `{fk['on_update']}` | `{fk['on_delete']}` | `{fk['match']}` |"
                )
        else:
            lines.append("(none)")

        # Sample rows
        if t["sample_rows"]:
            lines.append("\n### Sample Rows\n")
            # Build header from keys
            headers = list(t["sample_rows"][0].keys())
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("|" + "|".join(["---"] * len(headers)) + "|")
            for row in t["sample_rows"]:
                values = [str(truncate_value(row.get(h))) for h in headers]
                values = [v.replace("\n", " ") for v in values]  # keep table neat
                lines.append("| " + " | ".join(values) + " |")
        else:
            lines.append("\n### Sample Rows\n(none)")

    return "\n".join(lines) + "\n"


def sqlite_literal(value: Any) -> str:
    # Convert Python value to a SQLite SQL literal
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (dict, list)):
        # Store as JSON text
        value = json.dumps(value, ensure_ascii=False)
    if isinstance(value, bytes):
        return "X'" + value.hex() + "'"
    # Escape single quotes for TEXT
    s = str(value).replace("'", "''")
    return f"'{s}'"


def to_sql_dump(
    conn: sqlite3.Connection,
    overview: Dict[str, Any],
    include_inserts: bool = False,
    include_indexes: bool = True,
    include_triggers: bool = True,
    include_views: bool = True,
) -> str:
    lines: List[str] = []
    lines.append("-- SQL dump generated by Copilot DB Exporter")
    lines.append("PRAGMA foreign_keys=OFF;")
    lines.append("BEGIN TRANSACTION;")

    # Tables and their CREATE statements
    for t in overview["tables"]:
        name = t["name"]
        create_sql = get_table_create_sql(conn, name)
        if create_sql:
            lines.append("")
            lines.append(f"-- Table: {name}")
            lines.append(create_sql.rstrip("; ") + ";")

        # Optional INSERTs from sample rows
        if include_inserts and t.get("sample_rows"):
            # Column order consistent with PRAGMA table_info
            col_order = [c["name"] for c in t.get("columns", [])]
            # If sample row has extra keys (unlikely), align with column order
            cols = col_order if col_order else list(t["sample_rows"][0].keys())
            col_list = ", ".join([f"'{c}'" for c in cols])
            for row in t["sample_rows"]:
                vals = ", ".join([sqlite_literal(row.get(c)) for c in cols])
                lines.append(f"INSERT INTO '{name}' ({col_list}) VALUES ({vals});")

        # Indexes and triggers for this table
        if include_indexes:
            for idx_name, idx_sql in get_indexes_sql(conn, name):
                lines.append(idx_sql.rstrip("; ") + ";")
        if include_triggers:
            for trg_name, trg_sql in get_triggers_sql(conn, name):
                lines.append(trg_sql.rstrip("; ") + ";")

    # Views last
    if include_views:
        views = get_views_sql(conn)
        if views:
            lines.append("")
            lines.append("-- Views")
            for view_name, view_sql in views:
                lines.append(view_sql.rstrip("; ") + ";")

    lines.append("COMMIT;")
    return "\n".join(lines) + "\n"

# ------------------------------
# Core Export Logic
# ------------------------------

def build_overview(
    conn: sqlite3.Connection,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    sample_limit: int = 5,
) -> Dict[str, Any]:
    include_set = set([t.strip() for t in (include or []) if t.strip()])
    exclude_set = set([t.strip() for t in (exclude or []) if t.strip()])

    tables: List[str] = list_tables(conn)
    if include_set:
        tables = [t for t in tables if t in include_set]
    if exclude_set:
        tables = [t for t in tables if t not in exclude_set]

    out: Dict[str, Any] = {"tables": []}

    for t in tables:
        cols = get_table_columns(conn, t)
        fks = get_foreign_keys(conn, t)
        cnt = get_row_count(conn, t)
        samples = get_sample_rows(conn, t, sample_limit) if sample_limit > 0 else []

        out["tables"].append(
            {
                "name": t,
                "row_count": cnt,
                "columns": cols,
                "foreign_keys": fks,
                "sample_rows": samples,
            }
        )

    return out

# ------------------------------
# CLI
# ------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export DB overview for AI assistants (SQLite)")
    parser.add_argument("--db", required=True, help="Path to SQLite .db file")
    parser.add_argument("--include", help="Comma-separated list of tables to include", default="")
    parser.add_argument("--exclude", help="Comma-separated list of tables to exclude", default="")
    parser.add_argument("--limit", type=int, default=5, help="Sample rows per table (default: 5; 0 to disable)")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown", help="Output format")
    parser.add_argument("--out", help="Output file path (if omitted, prints to stdout)")
    # SQL dump options
    parser.add_argument("--sql-out", help="Write SQL schema dump to this file")
    parser.add_argument("--sql-inserts", action="store_true", help="Include INSERT statements using sample rows (limited by --limit)")
    parser.add_argument("--sql-tables-only", action="store_true", help="Only output CREATE TABLE statements (no indexes, triggers, or views)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    include = [t.strip() for t in args.include.split(",") if t.strip()] if args.include else []
    exclude = [t.strip() for t in args.exclude.split(",") if t.strip()] if args.exclude else []

    conn = connect_sqlite(args.db)
    overview = build_overview(conn, include=include, exclude=exclude, sample_limit=args.limit)

    # Structured doc output
    if args.format == "json":
        content = json.dumps(overview, indent=2, default=str)
    else:
        content = to_markdown(args.db, overview)

    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Wrote: {args.out}")
    else:
        print(content)

    # Optional SQL dump
    if args.sql_out:
        sql_content = to_sql_dump(
            conn,
            overview,
            include_inserts=args.sql_inserts,
            include_indexes=not args.sql_tables_only,
            include_triggers=not args.sql_tables_only,
            include_views=not args.sql_tables_only,
        )
        os.makedirs(os.path.dirname(args.sql_out), exist_ok=True)
        with open(args.sql_out, "w", encoding="utf-8") as f:
            f.write(sql_content)
        print(f"Wrote: {args.sql_out}")


if __name__ == "__main__":
    main()