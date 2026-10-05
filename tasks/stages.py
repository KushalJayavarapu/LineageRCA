"""The pipeline stages as PURE functions: the output depends only on the input tables and the code version.

Each stage handles ONE day (a partition): its output holds only that day's rows.
Each stage has named code versions. The healthy one is *_v1. Faulty or special versions exist so that a scenario can
"deploy" them, and so that the replay harness can pin the exact code version an anomalous run used.
No wall-clock time and no random numbers anywhere, except aggregate_v2_sample (scenario s6, on purpose).
"""
from __future__ import annotations

import pyarrow as pa

from adapters.duck import query
from tasks.datagen import date_for_day

# Orders are joined to customers and to the FX rate of their own day. Orders whose amount cannot be parsed are KEPT
# (amount = NULL) so that the null rate is visible to the monitor instead of the rows silently vanishing.
_CLEAN_SELECT = """
SELECT o.order_id, o.order_date, o.customer_id, c.region, c.segment, o.product, o.quantity, o.status, o.currency,
       TRY_CAST(o.amount AS DOUBLE) AS amount,
       TRY_CAST(o.amount AS DOUBLE) * f.rate_to_usd AS amount_usd
FROM raw_orders o
JOIN raw_customers c ON o.customer_id = c.customer_id
JOIN raw_fx_rates f ON o.currency = f.currency AND o.order_date = f.rate_date
WHERE o.order_date = '{day}' AND COALESCE(TRY_CAST(o.amount AS DOUBLE) > 0, TRUE)
"""
_STATUS_FILTER = " AND o.status NOT IN ('cancelled', 'test')"
_ORDER_BY = " ORDER BY o.order_id"

CLEAN_SQL = {
    "clean_v1": _CLEAN_SELECT + _STATUS_FILTER + _ORDER_BY,
    "clean_v2_no_filter": _CLEAN_SELECT + _ORDER_BY,          # s2: the cancelled/test filter was removed
}

# revenue_usd is rounded so float summation order can never change a content hash.
_AGG = ("SELECT order_date, region, ROUND(SUM(amount_usd), 2) AS revenue_usd, COUNT(*) AS order_count "
        "FROM cleaned_orders WHERE order_date = '{{day}}'{where} GROUP BY order_date, region "
        "ORDER BY order_date, region")
AGGREGATE_SQL = {
    "aggregate_v1": _AGG.format(where=""),
    "aggregate_v2_sample": _AGG.format(where=" AND random() < 0.9"),   # s6: UNSEEDED random 90% sample
}


def clean(raw_orders: pa.Table, raw_customers: pa.Table, raw_fx_rates: pa.Table, day: int,
          code_version: str = "clean_v1") -> pa.Table:
    """raw tables -> the cleaned_orders rows of `day`."""
    sql = CLEAN_SQL[code_version].replace("{day}", date_for_day(day))
    return query(sql, raw_orders=raw_orders, raw_customers=raw_customers, raw_fx_rates=raw_fx_rates)


def aggregate(cleaned_orders: pa.Table, day: int, code_version: str = "aggregate_v1") -> pa.Table:
    """cleaned_orders -> the daily_revenue_agg rows of `day` (one row per region)."""
    sql = AGGREGATE_SQL[code_version].replace("{day}", date_for_day(day))
    return query(sql, cleaned_orders=cleaned_orders)
