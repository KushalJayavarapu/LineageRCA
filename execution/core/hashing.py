"""Content hash of a table: the same rows give the same hash, whatever the row order. Used to prove determinism."""
from __future__ import annotations

import hashlib

import pyarrow as pa


def table_hash(table: pa.Table) -> str:
    """SHA-256 of the table contents (rows sorted by every column, then serialised)."""
    if table.num_rows > 0:
        table = table.sort_by([(name, "ascending") for name in table.column_names])
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table.combine_chunks())
    return hashlib.sha256(sink.getvalue().to_pybytes()).hexdigest()
