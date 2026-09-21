"""统一单位/限值/取整口径与历史判定不改写的回归测试."""
from decimal import Decimal

import app.domain.standards as standards_module
from app.domain import exceedance_rules
from app.domain.quantize import display_number, display_ratio, quantize_value
from app.models import Exceedance, Measurement


# ---------------------------------------------------------------------------
# 固定折算与取整规则
# ---------------------------------------------------------------------------

def test_value_equal_to_limit_is_not_exceeded():
    assert exceedance_rules.evaluate("PM25", "daily", "75.0")["exceeded"] is False
    assert exceedance_rules.evaluate("SO2", "hourly", 500.0)["exceeded"] is False
    assert exceedance_rules.evaluate("CO", "daily", "4.00")["exceeded"] is False


def test_half_up_rounding_uses_pollutant_precision():
    # 颗粒物精度 1 位: 75.05 -> 75.1 超标, 75.04 -> 75.0 达标
    assert quantize_value("75.05", 1) == Decimal("75.1")
    assert quantize_value("75.04", 1) == Decimal("75.0")
    # CO 精度 2 位: ROUND_HALF_UP (非银行家舍入) 4.005 -> 4.01 超标
    assert quantize_value("4.005", 2) == Decimal("4.01")
    assert exceedance_rules.evaluate("CO", "daily", "4.005")["exceeded"] is True
    assert exceedance_rules.evaluate("CO", "daily", "4.004")["exceeded"] is False


def test_stored_value_is_the_quantized_value_used_for_verdict():
    result = exceedance_rules.evaluate("PM25", "daily", "75.05")
    # 库里存的值、参与判定的值是同一个折算值
    assert result["value"] == 75.1
    assert result["exceeded"] is True


def test_ratio_is_fixed_at_four_decimals_and_grading_matches_verdict():
    tight = exceedance_rules.evaluate("SO2", "hourly", "500.1")
    assert tight["ratio"] == 1.0002
    assert tight["exceeded"] is True
    assert tight["level"] == "light"

    boundary_moderate = exceedance_rules.evaluate("PM25", "daily", "112.5")
    assert boundary_moderate["ratio"] == 1.5
    assert boundary_moderate["level"] == "moderate"

    severe = exceedance_rules.evaluate("O3", "daily", 320.0)
    assert severe["ratio"] == 2.0
    assert severe["level"] == "severe"


def test_display_helpers_keep_fixed_precision():
    assert display_number(75.0, 1) == "75.0"
    assert display_number(4.0, 2) == "4.00"
    assert display_ratio(1.2) == "1.2000"
    assert display_number(None, 1) == ""


# ---------------------------------------------------------------------------
# 同一份数据在 预览/写库/超标单 上结论一致
# ---------------------------------------------------------------------------

def test_preview_persist_and_exceedance_share_one_verdict(client, station, entry_payload):
    payload = entry_payload(
        station.id,
        entries=[{"pollutant": "CO", "value": "4.005"}],
        period="daily",
    )
    preview = client.post("/api/measurements/preview", json={**payload, "station_id": None}).get_json()
    preview_item = preview["results"][0]

    persisted = client.post("/api/measurements/entries", json=payload).get_json()
    stored = Measurement.query.filter_by(pollutant="CO").one()
    exceedance = Exceedance.query.filter_by(pollutant="CO").one()

    # 折算值 / 是否超标 / 倍数 / 等级 四处完全一致
    assert preview_item["value"] == stored.value == exceedance.value == 4.01
    assert preview_item["exceeded"] == stored.is_exceeded is True
    assert preview_item["ratio"] == stored.exceed_ratio == exceedance.exceed_ratio
    assert round(preview_item["ratio"], 4) == 1.0025
    assert preview_item["level"] == exceedance.level == "light"
    assert stored.to_dict()["precision"] == 2
    assert stored.unit == "mg/m³"


def test_api_payload_carries_unit_precision_and_policy(client, station, entry_payload):
    client.post("/api/measurements/entries", json=entry_payload(station.id))
    row = client.get("/api/measurements?pollutant=SO2").get_json()["items"][0]
    assert row["unit"] == "μg/m³"
    assert row["precision"] == 1
    assert row["limit_value"] == 500.0
    assert row["limit_policy"] == "GB 3095-2012 环境空气质量标准(二级)"


# ---------------------------------------------------------------------------
# 不同量级因子按各自单位参与比较, 不跨单位混算
# ---------------------------------------------------------------------------

def _daily_pair(client, station, entry_payload):
    client.post(
        "/api/measurements/entries",
        json=entry_payload(
            station.id,
            measured_at="2026-09-01 00:00",
            period="daily",
            entries=[{"pollutant": "CO", "value": 1.0}, {"pollutant": "PM25", "value": 60.0}],
        ),
    )


def test_pollutant_grouped_stats_keep_own_unit_and_precision(client, station, entry_payload):
    _daily_pair(client, station, entry_payload)
    body = client.get("/api/query/statistics?group_by=pollutant&metric=avg").get_json()
    by_key = {item["key"]: item for item in body["items"]}
    assert by_key["CO"]["unit"] == "mg/m³"
    assert by_key["CO"]["precision"] == 2
    assert by_key["CO"]["comparable"] is True
    assert by_key["PM25"]["unit"] == "μg/m³"
    assert by_key["PM25"]["precision"] == 1


def test_cross_unit_day_group_marks_value_not_comparable(client, station, entry_payload):
    _daily_pair(client, station, entry_payload)
    body = client.get("/api/query/statistics?group_by=day&metric=avg").get_json()
    assert body["value_comparable"] is False
    (item,) = body["items"]
    assert item["comparable"] is False
    assert item["value"] is None  # 不把 mg/m³ 与 μg/m³ 平均成一个数
    # 数据量/超标率仍可统计
    assert item["count"] == 2


def test_single_pollutant_filter_is_comparable_even_for_day_group(client, station, entry_payload):
    _daily_pair(client, station, entry_payload)
    body = client.get("/api/query/statistics?group_by=day&metric=avg&pollutant=CO").get_json()
    assert body["value_comparable"] is True
    assert body["items"][0]["unit"] == "mg/m³"


def test_summary_avg_is_suppressed_for_mixed_units(client, station, entry_payload):
    _daily_pair(client, station, entry_payload)
    mixed = client.get("/api/query/measurements").get_json()["summary"]
    assert mixed["value_comparable"] is False
    assert mixed["avg_value"] is None
    assert mixed["unit"] is None

    single = client.get("/api/query/measurements?pollutant=CO").get_json()["summary"]
    assert single["value_comparable"] is True
    assert single["avg_value"] == 1.0
    assert single["unit"] == "mg/m³"
    assert single["precision"] == 2


# ---------------------------------------------------------------------------
# 限值口径调整后, 历史判定不被改写
# ---------------------------------------------------------------------------

def test_changing_standard_does_not_rewrite_historical_verdict(client, station, entry_payload, monkeypatch):
    # 旧口径: CO 日限值 4, 4.50 超标, 固化快照
    client.post(
        "/api/measurements/entries",
        json=entry_payload(
            station.id,
            measured_at="2026-09-01 00:00",
            period="daily",
            entries=[{"pollutant": "CO", "value": 4.5}],
        ),
    )
    old = Measurement.query.filter_by(pollutant="CO").one()
    old_exceedance = Exceedance.query.filter_by(pollutant="CO").one()
    assert old.is_exceeded is True
    assert old.limit_value == 4.0
    assert old.limit_policy == "GB 3095-2012 环境空气质量标准(二级)"
    assert old_exceedance.level == "light"

    # 模拟限值口径收紧到 5 (仅影响之后的新判定)
    co = standards_module.POLLUTANTS["CO"]
    monkeypatch.setitem(co["limits"], "daily", 5.0)
    monkeypatch.setitem(client.application.config, "LIMIT_POLICY", "GB 3095-2099 (虚构)")
    client.post(
        "/api/measurements/entries",
        json=entry_payload(
            station.id,
            measured_at="2026-09-02 00:00",
            period="daily",
            entries=[{"pollutant": "CO", "value": 4.5}],
        ),
    )

    # 历史记录维持当时判定, 不被新标准改写
    from datetime import datetime as _dt

    db_session = old.query.session
    db_session.expire_all()
    old_fresh = Measurement.query.filter_by(
        pollutant="CO", measured_at=_dt(2026, 9, 1, 0, 0)
    ).one()
    assert old_fresh.is_exceeded is True
    assert old_fresh.limit_value == 4.0
    assert old_fresh.limit_policy == "GB 3095-2012 环境空气质量标准(二级)"
    assert Exceedance.query.filter_by(measurement_id=old_fresh.id).count() == 1

    # 新数据按新口径判定: 4.5 <= 5 达标
    new = Measurement.query.filter_by(
        pollutant="CO", measured_at=_dt(2026, 9, 2, 0, 0)
    ).one()
    assert new.is_exceeded is False
    assert new.limit_value == 5.0
    assert new.limit_policy == "GB 3095-2099 (虚构)"


def test_export_uses_fixed_precision_and_policy_column(client, station, entry_payload):
    client.post(
        "/api/measurements/entries",
        json=entry_payload(
            station.id,
            period="daily",
            entries=[{"pollutant": "CO", "value": 4.5}, {"pollutant": "PM25", "value": 60.0}],
        ),
    )
    text = client.get("/api/query/export?pollutant=CO").get_data(as_text=True)
    assert "4.50" in text          # CO 固定 2 位
    assert "4.00" in text          # 限值同样 2 位
    assert "1.1250" in text        # 超标倍数固定 4 位
    assert "GB 3095-2012" in text  # 限值口径列
    assert "mg/m³" in text         # 单位列
