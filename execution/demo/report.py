"""Self-contained HTML report: no network, no CDN, CSS, JS and images inlined. Everything is labelled SYNTHETIC.

The look (neo-brutalist: demo/report.css), the replay panel (demo/report.js) and the page (demo/report_template.html) are separate
files. This module only fills the template from demo/report_data.py. It does not compute anything about the run.
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment

from core.config import Settings, load_settings
from demo.report_data import page_context
from metrics.scoring import IncidentResult
from runners.run_scenario import Outcome

HERE = Path(__file__).resolve().parent


def render_report(outcomes: list[Outcome], descriptions: dict[str, str], out_dir: Path, heldout: list[IncidentResult] | None,
                  heldout_note: str, cfg_hash: str, seed: int, settings: Settings | None = None) -> str:
    """Build the HTML text. The PNG files must already exist in out_dir (they are embedded as a static fallback)."""
    monitor_cfg = (settings or load_settings()).monitor
    ctx = page_context(outcomes, descriptions, out_dir, heldout, heldout_note, cfg_hash, seed, monitor_cfg)
    template = (HERE / "report_template.html").read_text(encoding="utf-8")
    return Environment(autoescape=True).from_string(template).render(
        css=(HERE / "report.css").read_text(encoding="utf-8"), js=(HERE / "report.js").read_text(encoding="utf-8"), **ctx)
