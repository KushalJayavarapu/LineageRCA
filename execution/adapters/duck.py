"""DuckDB helper: run SQL over Arrow tables and get an Arrow table back. Stages are pure SQL functions of their inputs."""
from __future__ import annotations

import duckdb
import pyarrow as pa


def query(sql: str, **tables: pa.Table) -> pa.Table:
    """Run `sql` where each keyword argument is available as a table name. No state is kept between calls."""
    con = duckdb.connect(":memory:")
    try:
        con.execute("PRAGMA threads=1")  # one thread: float sums are then added in a fixed order (reproducible)
        for name, table in tables.items():
            con.register(name, table)
        return con.execute(sql).to_arrow_table()
    finally:
        con.close()
