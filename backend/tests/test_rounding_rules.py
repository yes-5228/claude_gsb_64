"""取整口径与超标判定一致性的单元测试."""
import pytest

from app.domain import exceedance_rules
from app.domain.rounding import round_ratio, round_value
from app.domain.standards import CURRENT_STANDARD_KEY, STANDARDS, get_limit


def test_round_value_is_half_up_not_banker_rounding():
    # 内置 round(2.675, 2) 因二进制浮点会得到 2.67; 固定口径必须为 2.68
    assert round_value(2.675, 2) == 2.68
    assert round_value(75.05, 1) == 75.1
    assert round_value(75.04, 1) == 75.0
    assert round_value(4.005, 2) == 4.01
    assert round_value(4.004, 2) == 4.0


def test_ratio_is_rounded_to_three_decimals():
    assert round_ratio(1 / 3, 3) == 0.333
    assert round_ratio(640 / 500, 3) == 1.28


def test_value_is_normalised_before_comparison_so_conclusions_agree():
    # 75.04 按 1 位精度四舍五入为 75.0, 等于限值 -> 达标(各处结论一致)
    near_below = exceedance_rules.evaluate("PM25", "daily", 75.04)
    assert near_below["value"] == 75.0
    assert near_below["exceeded"] is False
    assert near_below["limit"] == 75.0
    # 75.05 -> 75.1 严格大于限值 -> 超标
    near_above = exceedance_rules.evaluate("PM25", "daily", 75.05)
    assert near_above["value"] == 75.1
    assert near_above["exceeded"] is True


def test_co_uses_its_own_two_digit_precision():
    # CO 为 mg/m³, 精度 2 位; 4.004 -> 4.00 达标, 4.005 -> 4.01 超标
    assert exceedance_rules.evaluate("CO", "daily", 4.004)["exceeded"] is False
    result = exceedance_rules.evaluate("CO", "daily", 4.005)
    assert result["value"] == 4.01
    assert result["unit"] == "mg/m³"
    assert result["exceeded"] is True


def test_equal_to_limit_is_compliant_and_level_boundaries_are_inclusive():
    assert exceedance_rules.evaluate("PM25", "daily", 75.0)["exceeded"] is False
    # 分级边界含等号, 且在未舍入倍数上判定: 1.5 倍中度, 2.0 倍重度
    assert exceedance_rules.evaluate("PM25", "daily", 75.0 * 1.5)["level"] == "moderate"
    assert exceedance_rules.evaluate("PM25", "daily", 112.5)["level"] == "moderate"
    assert exceedance_rules.evaluate("PM25", "daily", 150.0)["level"] == "severe"
    assert exceedance_rules.evaluate("PM25", "daily", 149.9)["level"] == "moderate"


def test_evaluation_carries_standard_snapshot():
    result = exceedance_rules.evaluate("SO2", "hourly", 640)
    assert result["standard_key"] == CURRENT_STANDARD_KEY
    assert result["standard_label"] == STANDARDS[CURRENT_STANDARD_KEY]["label"]
    assert result["precision"] == 1
    assert result["ratio"] == 1.28
    assert result["level"] == "light"


def test_stored_precision_does_not_change_stored_limit_lookup():
    assert get_limit("CO", "daily") == 4.0
    assert get_limit("CO", "hourly") == 10.0
    assert get_limit("PM25", "hourly") is None


def test_unknown_standard_key_means_limits_cannot_be_recomputed():
    # 已下架/未知的历史标准口径不能用当前限值重算历史记录
    assert get_limit("PM25", "daily", standard_key="NO-SUCH-STANDARD") is None


def test_non_finite_value_raises():
    with pytest.raises(ValueError):
        exceedance_rules.evaluate("PM25", "daily", float("nan"))
    with pytest.raises(ValueError):
        exceedance_rules.evaluate("PM25", "daily", float("inf"))
