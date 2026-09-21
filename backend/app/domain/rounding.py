"""数值取整规则 (全系统唯一口径).

监测浓度属于法定计量数据, 统一采用四舍五入(ROUND_HALF_UP), 与检测报告/Excel
的"保留 n 位小数"习惯一致; 不使用 Python 内置 ``round`` 的银行家舍入, 避免
2.675 这类输入在不同展示位上出现分歧。

取整必须在**超标判定之前**完成: 同一因子各处(录入预览、落库、列表、导出)
先按因子精度归一再比较限值, 保证"接近限值"时不会因为各自精度差异而给出
相互矛盾的超标结论。
"""
from decimal import Decimal, ROUND_HALF_UP, localcontext


def quantize_decimal(value, precision):
    """Round ``value`` to ``precision`` decimal places using ROUND_HALF_UP.

    ``precision`` 为小数位数(非负整数); 非有限输入抛出 ValueError 由上层处理。
    """
    precision = int(precision)
    if precision < 0:
        raise ValueError("精度不能为负数")
    with localcontext() as ctx:
        ctx.prec = 50
        return Decimal(str(value)).quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)


def round_value(value, precision):
    """Return a float rounded half-up to the pollutant's display precision."""
    return float(quantize_decimal(value, precision))


def round_ratio(ratio, precision=3):
    """超标倍数仅用于展示/存储, 保留 3 位小数(分级不使用该舍入值)."""
    return float(quantize_decimal(ratio, precision))
