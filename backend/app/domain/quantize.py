"""统一的折算与取整规则 (唯一口径, 列表/图表/导出/标注共用).

规则固定如下, 不再随页面或精度设置变化:

1. 监测值先按因子精度 ``precision`` 做 **四舍五入(ROUND_HALF_UP)** 折算后再参与
   判定与存储; 颗粒物等为 1 位小数, CO 为 2 位小数。因此"页面上看到的值"与
   "参与超标的值"永远是同一个数, 不会出现看到 75.0 却判超标的情况。
2. 限值比较采用严格大于: ``折算值 > 限值`` 才判超标, 等于限值为达标。
3. 超标倍数 = 折算值 / 限值, 统一按 **4 位小数、四舍五入(ROUND_HALF_UP)** 记录与
   展示; 分级与是否超标都以这份舍入后的倍数为准
   (轻度 [1.0000, 1.5000) / 中度 [1.5000, 2.0000) / 重度 ≥ 2.0000)。
   4 位是按因子精度反推的安全位数: 即使最严格的组合(限值 500、精度 0.1),
   相邻合法读数的倍数增量也有约 0.0002 > 0.00005 的舍入半区,
   故"舍入后是否超 1 / 是否跨级"与"折算值是否真超限值"结论恒一致,
   保证同一份数据在任何页面得到的结论一致。展示时可在该固定值上去尾零,
   但超标与否、等级一律以 4 位舍入倍数(库内已固化)为准。

全程使用 Decimal 运算, 避免二进制浮点造成的边界抖动。
"""
from decimal import Decimal, ROUND_HALF_UP

# 超标倍数的统一保留位数 (判定/存储/展示共用)
RATIO_PRECISION = 4


def quantize_value(value, precision):
    """Round a reading to the pollutant precision using ROUND_HALF_UP; returns Decimal."""
    quantum = Decimal(1).scaleb(-int(precision))
    return Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP)


def quantize_ratio(ratio):
    """Round the exceedance ratio to the fixed 3-digit precision; returns Decimal."""
    quantum = Decimal(1).scaleb(-RATIO_PRECISION)
    return Decimal(str(ratio)).quantize(quantum, rounding=ROUND_HALF_UP)


def display_number(value, precision):
    """Fixed-precision display string (trailing zeros kept), e.g. 75.0 / 4.00."""
    if value is None:
        return ""
    return format(quantize_value(value, precision), "f")


def display_ratio(ratio):
    """Fixed 4-digit display string for exceedance ratios."""
    if ratio is None:
        return ""
    return format(quantize_ratio(ratio), "f")
