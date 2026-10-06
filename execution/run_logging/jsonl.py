"""Tiny structured run log: one JSON object per line. Only logical times are written, never the wall clock."""
from __future__ import annotations

import json
from pathlib import Path


class RunLog:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")          # start a fresh file for this run

    def event(self, kind: str, **fields: object) -> None:
        if self.path is None:
            return
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"event": kind, "source": "synthetic", **fields}, sort_keys=True) + "\n")
