"""超标判定规则: 依据污染物限值计算超标倍数并分级.

判定口径见 :mod:`app.domain.quantize` 模块说明, 本模块只负责套用:
先按因子精度折算监测值, 再用折算值与限值严格比较, 超标倍数固定保留 4 位小数,
是否超标与等级都以这份舍入后的倍数为准, 避免同一数据出现不同结论。
"""
from decimal import Decimal

from .quantize import quantize_ratio, quantize_value
from .standards import get_limit, get_pollutant

# 超标倍数 -> 等级 (按固定 4 位舍入后的倍数判定)
LEVEL_THRESHOLDS = ((Decimal("2.0000"), "severe"), (Decimal("1.5000"), "moderate"), (Decimal("1.0000"), "light"))

LEVEL_ORDER = {"light": 1, "moderate": 2, "severe": 3}


def grade_ratio(ratio):
    """Map an exceedance ratio (value / limit) to a level code."""
    ratio = Decimal(str(ratio))
    for threshold, level in LEVEL_THRESHOLDS:
        if ratio >= threshold:
            return level
    return "light"


def evaluate(pollutant_code, period, value):
    """Evaluate a single reading.

    Returns a dict: {"applicable", "exceeded", "limit", "ratio", "level", "unit",
    "value", "precision", "message"}.
    ``applicable`` is False when the standard defines no limit for this period
    (e.g. PM2.5 has no 1-hour limit), in which case ``exceeded`` stays False.
    ``value`` is the reading rounded to the pollutant precision — the exact number
    that gets stored and compared, so displays and verdicts never diverge.
    """
    pollutant = get_pollutant(pollutant_code)
    if pollutant is None:
        raise ValueError("未知监测因子: %s" % pollutant_code)
    if period not in ("hourly", "daily"):
        raise ValueError("未知数据周期: %s" % period)
    if value is None:
        raise ValueError("监测数值不能为空")

    precision = pollutant["precision"]
    rounded_value = quantize_value(value, precision)
    limit = get_limit(pollutant_code, period)
    if limit is None:
        return {
            "applicable": False,
            "exceeded": False,
            "limit": None,
            "ratio": None,
            "level": None,
            "value": float(rounded_value),
            "precision": precision,
            "unit": pollutant["unit"],
            "message": "%s 未设定小时均值限值, 仅记录数值" % pollutant["label"],
        }

    limit_decimal = Decimal(str(limit))
    # 折算值 > 限值 才超标; 固定 4 位倍数同时用于超标结论与分级
    ratio = quantize_ratio(rounded_value / limit_decimal)
    exceeded = ratio > Decimal("1.0000")
    return {
        "applicable": True,
        "exceeded": exceeded,
        "limit": limit,
        "ratio": float(ratio),
        "value": float(rounded_value),
        "precision": precision,
        "level": grade_ratio(ratio) if exceeded else None,
        "unit": pollutant["unit"],
        "message": None,
    }


def summarize(results):
    """Aggregate evaluation results for the batch entry form."""
    exceeded = [item for item in results if item["exceeded"]]
    return {
        "total": len(results),
        "exceeded_count": len(exceeded),
        "exceeded_pollutants": [item["pollutant"] for item in exceeded],
    }
