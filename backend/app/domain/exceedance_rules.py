"""超标判定规则: 固定的取整、比较与分级口径.

口径说明 (与 README 保持一致):

1. **先取整, 再判定**。监测值先按因子精度四舍五入(ROUND_HALF_UP, 见
   ``domain/rounding.py``)归一为"记录值", 再与限值比较。因此录入值、列表、
   图表、导出、标注页面看到的是同一个数; 接近限值时各处结论必然一致。
2. **判定用严格大于**: ``记录值 > 限值`` 才判超标, 恰好等于限值为达标。
   限值数值本身按各因子自身单位解释, μg/m³ 与 mg/m³ 不做跨单位换算比较。
3. **超标倍数** = 记录值 / 限值; 分级在未舍入的倍数上进行, 边界含下限
   (≥1.5 为中度, ≥2.0 为重度), 避免展示精度(3 位小数)反过来影响等级。
4. 每次判定携带标准口径 key, 与限值快照一起落库; 标准修订后历史记录的
   结论不被改写。
"""
from decimal import Decimal, localcontext

from .rounding import quantize_decimal, round_ratio
from .standards import current_standard, get_limit, get_pollutant, get_standard

# 超标倍数 -> 等级 (按阈值从高到低匹配, 边界含等号)
LEVEL_THRESHOLDS = ((2.0, "severe"), (1.5, "moderate"), (1.0, "light"))

LEVEL_ORDER = {"light": 1, "moderate": 2, "severe": 3}


def grade_ratio(ratio):
    """Map an exceedance ratio (value / limit) to a level code."""
    for threshold, level in LEVEL_THRESHOLDS:
        if ratio >= threshold:
            return level
    return "light"


def _is_finite(value):
    return value == value and value not in (Decimal("Infinity"), Decimal("-Infinity"))


def evaluate(pollutant_code, period, value, standard_key=None):
    """Evaluate a single reading.

    Returns a dict: {"applicable", "exceeded", "limit", "ratio", "level",
    "unit", "value", "precision", "standard_key", "standard_label", "message"}.
    ``applicable`` is False when the standard defines no limit for this period
    (e.g. PM2.5 has no 1-hour limit), in which case ``exceeded`` stays False.

    ``value`` 始终返回按因子精度取整后的"记录值"(float), 调用方应原样落库,
    保证存储与展示、判定使用同一个数。
    """
    pollutant = get_pollutant(pollutant_code)
    if pollutant is None:
        raise ValueError("未知监测因子: %s" % pollutant_code)
    if period not in ("hourly", "daily"):
        raise ValueError("未知数据周期: %s" % period)
    if value is None:
        raise ValueError("监测数值不能为空")

    try:
        raw = Decimal(str(value))
    except Exception:
        raise ValueError("监测数值必须为有限数字: %r" % value)
    if not _is_finite(raw):
        raise ValueError("监测数值必须为有限数字")

    precision = int(pollutant["precision"])
    normalized = quantize_decimal(raw, precision)
    standard = get_standard(standard_key) or current_standard()
    limit = get_limit(pollutant_code, period, standard["key"])

    if limit is None:
        return {
            "applicable": False,
            "exceeded": False,
            "limit": None,
            "ratio": None,
            "level": None,
            "unit": pollutant["unit"],
            "value": float(normalized),
            "precision": precision,
            "standard_key": standard["key"],
            "standard_label": standard["label"],
            "message": "%s 未设定小时均值限值, 仅记录数值" % pollutant["label"],
        }

    limit_decimal = Decimal(str(limit))
    with localcontext() as ctx:
        ctx.prec = 50
        exact_ratio = normalized / limit_decimal
    exceeded = normalized > limit_decimal
    ratio = round_ratio(exact_ratio, 3)
    return {
        "applicable": True,
        "exceeded": exceeded,
        "limit": limit,
        "ratio": ratio,
        "level": grade_ratio(float(exact_ratio)) if exceeded else None,
        "unit": pollutant["unit"],
        "value": float(normalized),
        "precision": precision,
        "standard_key": standard["key"],
        "standard_label": standard["label"],
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
