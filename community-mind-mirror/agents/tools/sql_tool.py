"""Read-only SQL query tool for Agno agents.

Each agent gets an instance scoped to specific tables.
Prevents any write operations. Validates table access.
"""

import json
import re

import asyncpg
from agno.tools import Toolkit


class SQLReadTool(Toolkit):
    """Read-only SQL query tool with table-scoped access."""

    def __init__(self, db_url: str, allowed_tables: list[str]):
        super().__init__(name="sql_read_tool")
        self.db_url = db_url
        self.allowed_tables = [t.lower() for t in allowed_tables]
        self._pool = None
        self.register(self.sql_query)
        self.register(self.get_schema)
        self.register(self.list_tables)

    async def _get_pool(self):
        if self._pool is None:
            self._pool = await asyncpg.create_pool(self.db_url, min_size=1, max_size=3)
        return self._pool

    async def sql_query(self, sql: str) -> str:
        """Execute a read-only SQL query against the Community Mind Mirror database.

        RULES:
        - Only SELECT queries are allowed
        - Always use LIMIT (max 200 rows) to avoid pulling too much data
        - Use ILIKE for case-insensitive text matching
        - JSONB fields can be queried with @> operator or ->> accessor
        - Dates are TIMESTAMP type, use INTERVAL for relative dates
        - Always handle NULL values with COALESCE where needed

        Returns: JSON array of result rows, or error message.
        """
        sql_stripped = sql.strip().rstrip(";")
        sql_upper = sql_stripped.upper()

        # Block write operations
        write_keywords = [
            "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
            "TRUNCATE", "GRANT", "REVOKE", "EXECUTE", "COPY",
        ]
        for keyword in write_keywords:
            if keyword in sql_upper and not (
                keyword == "CREATE" and "CREATE TEMP" not in sql_upper
            ):
                return "ERROR: Write operations are not allowed. Only SELECT queries permitted."

        if not sql_upper.startswith("SELECT"):
            return "ERROR: Query must start with SELECT."

        # Validate table access
        referenced_tables = self._extract_tables(sql_stripped)
        for table in referenced_tables:
            if table.lower() not in self.allowed_tables:
                return (
                    f"ERROR: Access denied to table '{table}'. "
                    f"Allowed tables: {', '.join(self.allowed_tables)}"
                )

        # Force LIMIT if not present
        if "LIMIT" not in sql_upper:
            sql_stripped += " LIMIT 100"

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            try:
                rows = await conn.fetch(sql_stripped)
                results = [dict(r) for r in rows]
                return json.dumps(results, default=str, ensure_ascii=False)
            except Exception as e:
                return f"SQL ERROR: {str(e)}\nQuery was: {sql_stripped}"

    async def get_schema(self, table_name: str) -> str:
        """Get column names, types, and sample values for a table.
        Use this FIRST to understand a table's structure before writing queries.
        """
        if table_name.lower() not in self.allowed_tables:
            return (
                f"ERROR: Access denied to table '{table_name}'. "
                f"Allowed tables: {', '.join(self.allowed_tables)}"
            )

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            try:
                columns = await conn.fetch(
                    """
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = $1
                    ORDER BY ordinal_position
                    """,
                    table_name.lower(),
                )
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {table_name}")
                samples = await conn.fetch(f"SELECT * FROM {table_name} LIMIT 3")

                result = {
                    "table": table_name,
                    "row_count": count,
                    "columns": [dict(c) for c in columns],
                    "sample_rows": [dict(s) for s in samples],
                }
                return json.dumps(result, default=str, ensure_ascii=False)
            except Exception as e:
                return f"SCHEMA ERROR: {str(e)}"

    async def list_tables(self) -> str:
        """List all tables you have access to with their row counts.
        Call this first to understand what data is available."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            results = []
            for table in self.allowed_tables:
                try:
                    count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                    results.append({"table": table, "row_count": count})
                except Exception:
                    results.append({"table": table, "row_count": "ERROR"})
            return json.dumps(results, default=str)

    def _extract_tables(self, sql: str) -> list[str]:
        """Extract table names from SQL query."""
        pattern = r"(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)"
        matches = re.findall(pattern, sql, re.IGNORECASE)
        sql_keywords = {
            "select", "where", "and", "or", "on", "as", "in",
            "not", "null", "true", "false", "case", "when", "then",
            "else", "end", "group", "order", "having", "limit",
            "offset", "union", "intersect", "except", "lateral",
            "information_schema",
        }
        return [m for m in matches if m.lower() not in sql_keywords]

    async def close(self):
        if self._pool:
            await self._pool.close()
