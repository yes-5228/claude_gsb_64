"""标准口径快照与跨单位聚合的接口测试."""
from app.domain import standards
from app.models import Measurement
from app.services import query_service


def test_entry_persists_standard_snapshot_and_normalised_value(client, station, entry_payload):
    payload = entry_payload(
        station.id,
        entries=[{"pollutant": "SO2", "value": 640.04}, {"pollutant": "CO", "value": 1.405}],
    )
    body = client.post("/api/measurements/entries", json=payload).get_json()

    so2 = Measurement.query.filter_by(pollutant="SO2").one()
    # 640.04 按 1 位精度取整为 640.0 后再判定
    assert so2.value == 640.0
    assert so2.precision == 1
    assert so2.unit == "μg/m³"
    assert so2.limit_value == 500.0
    assert so2.standard_key == standards.CURRENT_STANDARD_KEY
    assert so2.standard_label
    assert so2.exceedance.standard_key == standards.CURRENT_STANDARD_KEY

    co = Measurement.query.filter_by(pollutant="CO").one()
    # 1.405 按 2 位精度四舍五入为 1.41
    assert co.value == 1.41
    assert co.precision == 2
    assert co.unit == "mg/m³"

    item = next(i for i in body["evaluations"] if i["pollutant"] == "CO")
    assert item["value"] == 1.41


def test_changing_standard_does_not_rewrite_historical_records(client, station, entry_payload,
                                                               monkeypatch):
    client.post(
        "/api/measurements/entries",
        json=entry_payload(
            station.id,
            measured_at="2026-09-01 00:00",
            period="daily",
            entries=[{"pollutant": "PM25", "value": 80.0}],
        ),
    )
    historical = Measurement.query.filter_by(pollutant="PM25").one()
    assert historical.is_exceeded is True
    assert historical.limit_value == 75.0
    old_key = historical.standard_key

    # 模拟限值口径修订: PM2.5 日均值放宽到 85, 启用新标准版本
    new_limits = {
        code: dict(limits) for code, limits in standards.STANDARDS[old_key]["limits"].items()
    }
    new_limits["PM25"] = {"daily": 85.0, "hourly": None}
    monkeypatch.setitem(
        standards.STANDARDS,
        "GB3095-2012:L2:v2",
        {
            "key": "GB3095-2012:L2:v2",
            "code": "GB 3095-2012",
            "name": "环境空气质量标准",
            "level": "二级",
            "version": 2,
            "label": "GB 3095-2012 环境空气质量标准(二级, 修订版)",
            "limits": new_limits,
        },
    )
    monkeypatch.setattr(standards, "CURRENT_STANDARD_KEY", "GB3095-2012:L2:v2")

    # 历史记录原样读出, 判定结论/限值/标准口径都不被改写
    body = client.get("/api/measurements?pollutant=PM25").get_json()
    row = body["items"][0]
    assert row["is_exceeded"] is True
    assert row["limit_value"] == 75.0
    assert row["standard_key"] == old_key

    # 同一数值在新标准下是达标, 且记录新标准口径
    client.post(
        "/api/measurements/entries",
        json=entry_payload(
            station.id,
            measured_at="2026-09-02 00:00",
            period="daily",
            entries=[{"pollutant": "PM25", "value": 80.0}],
        ),
    )
    new_record = Measurement.query.filter(
        Measurement.pollutant == "PM25", Measurement.measured_at.like("2026-09-02%")
    ).one()
    assert new_record.is_exceeded is False
    assert new_record.limit_value == 85.0
    assert new_record.standard_key == "GB3095-2012:L2:v2"


def _seed_mixed_units(client, station, entry_payload):
    client.post(
        "/api/measurements/entries",
        json=entry_payload(
            station.id,
            measured_at="2026-09-01 00:00",
            period="daily",
            entries=[
                {"pollutant": "PM25", "value": 60.0},   # μg/m³
                {"pollutant": "CO", "value": 1.2},      # mg/m³
            ],
        ),
    )


def test_summary_refuses_mixed_unit_average(client, station, entry_payload):
    _seed_mixed_units(client, station, entry_payload)
    body = client.get("/api/query/measurements").get_json()
    summary = body["summary"]
    assert summary["total"] == 2
    assert summary["mixed_units"] is True
    assert summary["avg_value"] is None
    assert summary["avg_unit"] is None

    # 限定单一单位/因子时仍给出均值与单位
    only_pm = client.get("/api/query/measurements?pollutant=PM25").get_json()["summary"]
    assert only_pm["mixed_units"] is False
    assert only_pm["avg_value"] == 60.0
    assert only_pm["avg_unit"] == "μg/m³"


def test_statistics_keep_units_per_pollutant(client, station, entry_payload):
    _seed_mixed_units(client, station, entry_payload)
    body = client.get("/api/query/statistics?group_by=pollutant&metric=avg").get_json()
    by_key = {item["key"]: item for item in body["items"]}
    assert by_key["PM25"]["value"] == 60.0
    assert by_key["PM25"]["unit"] == "μg/m³"
    assert by_key["CO"]["value"] == 1.2
    assert by_key["CO"]["unit"] == "mg/m³"
    assert body["mixed_units"] is True


def test_statistics_mark_day_group_as_incomparable_across_units(client, station, entry_payload):
    _seed_mixed_units(client, station, entry_payload)
    body = client.get("/api/query/statistics?group_by=day&metric=avg").get_json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["mixed_units"] is True
    assert item["comparable"] is False
    assert item["value"] is None
    assert set(item["units"]) == {"μg/m³", "mg/m³"}

    # 条数与量纲无关, 仍然可聚合
    counts = client.get("/api/query/statistics?group_by=day&metric=count").get_json()
    assert counts["items"][0]["value"] == 2.0
    assert counts["items"][0]["comparable"] is True


def test_station_detail_stats_carry_unit_and_precision(client, station, entry_payload):
    client.post(
        "/api/measurements/entries",
        json=entry_payload(
            station.id,
            entries=[{"pollutant": "CO", "value": 1.234}],
        ),
    )
    body = client.get("/api/stations/%d" % station.id).get_json()
    co = next(item for item in body["stats"]["pollutants"] if item["pollutant"] == "CO")
    assert co["unit"] == "mg/m³"
    assert co["precision"] == 2
    assert co["avg_value"] == 1.23
    assert co["max_value"] == 1.23


def test_export_csv_formats_with_pollutant_precision_and_standard(client, station, entry_payload):
    client.post(
        "/api/measurements/entries",
        json=entry_payload(
            station.id,
            entries=[{"pollutant": "CO", "value": 1.2}, {"pollutant": "SO2", "value": 640.0}],
        ),
    )
    text = client.get("/api/measurements/export").get_data(as_text=True)
    lines = text.strip().splitlines()
    header = lines[0].lstrip("﻿").split(",")
    assert "判定标准" in header

    co_row = next(line for line in lines[1:] if line.startswith('"') is False and "CO" in line and "mg" in line)
    # CO 固定 2 位小数
    assert "1.20" in co_row
    so2_row = next(line for line in lines[1:] if "SO₂" in line)
    assert "640.0" in so2_row
