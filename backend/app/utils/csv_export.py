"""CSV export helper (UTF-8 BOM so Excel opens Chinese text correctly)."""
import csv
import io
from datetime import datetime

from flask import Response

from ..domain.rounding import round_value
from ..domain.standards import get_pollutant


def csv_response(rows, columns, filename_prefix):
    """columns: list of (header, key-or-callable)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([header for header, _ in columns])
    for row in rows:
        writer.writerow([_resolve(row, accessor) for _, accessor in columns])

    filename = "%s_%s.csv" % (filename_prefix, datetime.now().strftime("%Y%m%d%H%M%S"))
    payload = "﻿" + buffer.getvalue()
    return Response(
        payload,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=%s" % filename},
    )


def _resolve(row, accessor):
    """Read a column from a model instance, a mapping or a callable."""
    value = accessor(row) if callable(accessor) else getattr(row, accessor, None)
    return "" if value is None else value


# ---------------------------------------------------------------------------
# 监测数据导出的统一取值口径: 与列表/图表/标注页面一致, 按因子精度四舍五入
# ---------------------------------------------------------------------------
def _precision(row):
    """精度优先取记录快照, 历史缺精度数据回退到因子元数据。"""
    precision = getattr(row, "precision", None)
    if precision is not None:
        return int(precision)
    meta = get_pollutant(getattr(row, "pollutant", None))
    return int(meta["precision"]) if meta else 2


def formatted_value(row):
    """监测值: 固定小数位(不抹零), 保证各页面/导出显示完全一致。"""
    if row.value is None:
        return ""
    return ("%." + str(_precision(row)) + "f") % round_value(row.value, _precision(row))


def formatted_limit(row):
    """限值: 与监测值同精度同单位展示; 无值留空。"""
    if row.limit_value is None:
        return ""
    return ("%." + str(_precision(row)) + "f") % round_value(row.limit_value, _precision(row))


def formatted_ratio(row):
    """超标倍数: 固定 3 位小数, 无值留空。"""
    if row.exceed_ratio is None:
        return ""
    return "%.3f" % round_value(row.exceed_ratio, 3)
