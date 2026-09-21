"""监测数据查询: 过滤条件解析, 统计聚合与导出数据准备."""
from datetime import datetime, time

from sqlalchemy import cast, func, or_

from ..domain.constants import (
    DATA_SOURCE_LABELS,
    EXCEEDANCE_STATUS_LABELS,
    PERIOD_LABELS,
    STATION_TYPE_LABELS,
)
from ..domain.rounding import round_value
from ..domain.standards import POLLUTANT_CODES, get_pollutant
from ..errors import ValidationError
from ..extensions import db
from ..models import Exceedance, Measurement, Station
from ..models.base import iso
from ..utils.validation import parse_date

GROUP_BY_CHOICES = ("station", "area", "pollutant", "period", "day", "month", "data_source")
# count 是"条数", 与量纲无关; 其余指标都是浓度, 只能在同一单位内聚合
CONCENTRATION_METRICS = ("avg", "max", "min", "sum")
METRIC_CHOICES = CONCENTRATION_METRICS + ("count",)
SORT_CHOICES = ("measured_at", "value", "exceed_ratio", "pollutant", "station_code", "created_at")


def _split(value):
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _int_list(args, name):
    values = []
    for item in _split(args.get(name)):
        try:
            values.append(int(item))
        except ValueError:
            raise ValidationError("%s 参数必须为整数" % name, fields={name: "invalid_integer"})
    return values


def _float_arg(args, name):
    raw = args.get(name)
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except ValueError:
        raise ValidationError("%s 参数必须为数字" % name, fields={name: "invalid_number"})


def _bool_arg(args, name):
    raw = args.get(name)
    if raw in (None, ""):
        return None
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _date_arg(args, name, end_of_day=False):
    raw = args.get(name)
    if raw in (None, ""):
        return None
    parsed = parse_date(raw, name)
    return datetime.combine(parsed, time.max if end_of_day else time.min)


def parse_filters(args):
    """Translate request args into a normalised filter dictionary."""
    pollutants = [item.upper() for item in _split(args.get("pollutant"))]
    unknown = [item for item in pollutants if item not in POLLUTANT_CODES]
    if unknown:
        raise ValidationError(
            "未知监测因子: %s" % ", ".join(unknown), fields={"pollutant": "unknown"}
        )

    periods = _split(args.get("period"))
    for period in periods:
        if period not in PERIOD_LABELS:
            raise ValidationError("未知数据周期: %s" % period, fields={"period": "unknown"})

    filters = {
        "station_ids": _int_list(args, "station_id"),
        "areas": _split(args.get("area")),
        "station_types": _split(args.get("station_type")),
        "pollutants": pollutants,
        "periods": periods,
        "data_sources": _split(args.get("data_source")),
        "is_exceeded": _bool_arg(args, "is_exceeded"),
        "exceedance_status": _split(args.get("exceedance_status")),
        "date_from": _date_arg(args, "date_from"),
        "date_to": _date_arg(args, "date_to", end_of_day=True),
        "min_value": _float_arg(args, "min_value"),
        "max_value": _float_arg(args, "max_value"),
        "keyword": (args.get("keyword") or "").strip(),
        "recorder": (args.get("recorder") or "").strip(),
    }
    if filters["date_from"] and filters["date_to"] and filters["date_from"] > filters["date_to"]:
        raise ValidationError(
            "开始时间不能晚于结束时间", fields={"date_from": "range_invalid"}
        )
    if (
        filters["min_value"] is not None
        and filters["max_value"] is not None
        and filters["min_value"] > filters["max_value"]
    ):
        raise ValidationError("最小值不能大于最大值", fields={"min_value": "range_invalid"})
    return filters


def apply_filters(query, filters):
    query = query.join(Station, Measurement.station_id == Station.id)
    if filters["station_ids"]:
        query = query.filter(Measurement.station_id.in_(filters["station_ids"]))
    if filters["areas"]:
        query = query.filter(Station.area.in_(filters["areas"]))
    if filters["station_types"]:
        query = query.filter(Station.station_type.in_(filters["station_types"]))
    if filters["pollutants"]:
        query = query.filter(Measurement.pollutant.in_(filters["pollutants"]))
    if filters["periods"]:
        query = query.filter(Measurement.period.in_(filters["periods"]))
    if filters["data_sources"]:
        query = query.filter(Measurement.data_source.in_(filters["data_sources"]))
    if filters["is_exceeded"] is not None:
        query = query.filter(Measurement.is_exceeded.is_(filters["is_exceeded"]))
    if filters["date_from"]:
        query = query.filter(Measurement.measured_at >= filters["date_from"])
    if filters["date_to"]:
        query = query.filter(Measurement.measured_at <= filters["date_to"])
    if filters["min_value"] is not None:
        query = query.filter(Measurement.value >= filters["min_value"])
    if filters["max_value"] is not None:
        query = query.filter(Measurement.value <= filters["max_value"])
    if filters["recorder"]:
        query = query.filter(Measurement.recorder.like("%" + filters["recorder"] + "%"))
    if filters["keyword"]:
        like = "%" + filters["keyword"] + "%"
        query = query.filter(
            or_(Station.name.like(like), Station.code.like(like), Station.address.like(like))
        )
    if filters["exceedance_status"]:
        query = query.join(Exceedance, Exceedance.measurement_id == Measurement.id).filter(
            Exceedance.status.in_(filters["exceedance_status"])
        )
    return query


def apply_sort(query, sort=None, order="desc"):
    sort = sort if sort in SORT_CHOICES else "measured_at"
    column = {
        "measured_at": Measurement.measured_at,
        "value": Measurement.value,
        "exceed_ratio": Measurement.exceed_ratio,
        "pollutant": Measurement.pollutant,
        "station_code": Station.code,
        "created_at": Measurement.created_at,
    }[sort]
    primary = column.desc() if (order or "desc").lower() == "desc" else column.asc()
    return query.order_by(primary, Measurement.id.desc())


def measurement_query(args):
    filters = parse_filters(args)
    query = apply_filters(db.session.query(Measurement), filters)
    return apply_sort(query, args.get("sort"), args.get("order")), filters


def _distinct_units(filters):
    """Units covered by the current (fully applied) filter set."""
    rows = apply_filters(
        db.session.query(Measurement.unit).filter(Measurement.unit.isnot(None)).distinct(),
        filters,
    ).all()
    return {unit for (unit,) in rows if unit}


def _avg_over_mixed_units(filters):
    """Overall mean concentration; None when the filter mixes units.

    μg/m³ 与 mg/m³ 不能直接平均, 否则会得到一个没有物理意义的数, 还可能让
    "均值是否接近限值"的判断出错。单位唯一时按该单位的因子精度取整。
    """
    base = apply_filters(
        db.session.query(func.avg(Measurement.value)),
        filters,
    )
    avg_value = base.scalar()
    if avg_value is None:
        return None, None, False
    units = _distinct_units(filters)
    if len(units) > 1:
        return None, None, True
    unit = next(iter(units), None)
    precision = _precision_for_unit(unit)
    return round_value(float(avg_value), precision), unit, False


def _precision_for_unit(unit):
    """Display precision used by concentration aggregates: 同单位取最粗精度。"""
    precisions = [
        int(meta["precision"])
        for meta in (get_pollutant(code) for code in POLLUTANT_CODES)
        if meta and meta["unit"] == unit
    ]
    return max(precisions) if precisions else 2


def summary(filters):
    """Aggregate counters shown above the query result table."""
    query = apply_filters(
        db.session.query(
            func.count(Measurement.id),
            func.sum(cast(Measurement.is_exceeded, db.Integer)),
            func.count(func.distinct(Measurement.station_id)),
            func.min(Measurement.measured_at),
            func.max(Measurement.measured_at),
        ),
        filters,
    )
    total, exceeded, stations, first_at, last_at = query.one()
    total = int(total or 0)
    exceeded = int(exceeded or 0)
    avg_value, avg_unit, mixed_units = _avg_over_mixed_units(filters)
    return {
        "total": total,
        "exceeded_count": exceeded,
        "exceed_rate": round(exceeded / total, 4) if total else 0.0,
        "station_count": int(stations or 0),
        "first_measured_at": iso(first_at),
        "last_measured_at": iso(last_at),
        "avg_value": avg_value,
        "avg_unit": avg_unit,
        "mixed_units": mixed_units,
    }


def _metric_expressions(metric):
    """浓度类指标按"分组+单位"分别取值; 合并阶段处理跨单位情况。"""
    return {
        "avg": (func.avg(Measurement.value), None),
        "max": (func.max(Measurement.value), None),
        "min": (func.min(Measurement.value), None),
        "sum": (func.sum(Measurement.value), None),
        "count": (func.count(Measurement.id), None),
    }[metric]


def _metric_expression(metric):
    return _metric_expressions(metric)[0]


def statistics(args):
    """Grouped aggregation used by the query page statistics panel.

    浓度类指标按"分组 + 单位"分别计算: 同一分组若包含多种单位(例如按站点
    同时统计 μg/m³ 的 SO₂ 与 mg/m³ 的 CO), 不再输出一个跨单位的均值/合计,
    而是置空 value 并给出 ``units``/``mixed_units``, 由前端明确提示。按因子
    分组时每个分组天然只有一个单位, 直接按该因子精度取整。
    """
    filters = parse_filters(args)
    group_by = args.get("group_by") or "pollutant"
    metric = args.get("metric") or "avg"
    if group_by not in GROUP_BY_CHOICES:
        raise ValidationError(
            "group_by 仅支持: %s" % ", ".join(GROUP_BY_CHOICES), fields={"group_by": "unknown"}
        )
    if metric not in METRIC_CHOICES:
        raise ValidationError(
            "metric 仅支持: %s" % ", ".join(METRIC_CHOICES), fields={"metric": "unknown"}
        )

    value_expr = _metric_expression(metric)
    count_expr = func.count(Measurement.id).label("row_count")
    exceeded_expr = func.sum(cast(Measurement.is_exceeded, db.Integer)).label("exceeded_count")
    unit_expr = Measurement.unit.label("unit")

    if group_by == "station":
        query = db.session.query(
            Station.id.label("station_id"),
            Station.code.label("station_code"),
            Station.name.label("station_name"),
            Station.area.label("area"),
            value_expr.label("metric_value"),
            count_expr,
            exceeded_expr,
            unit_expr,
        ).group_by(Station.id, Station.code, Station.name, Station.area, Measurement.unit)
        is_time_group = False
    elif group_by == "area":
        query = db.session.query(
            Station.area.label("area"),
            value_expr.label("metric_value"),
            count_expr,
            exceeded_expr,
            unit_expr,
        ).group_by(Station.area, Measurement.unit)
        is_time_group = False
    elif group_by == "day":
        bucket = func.date(Measurement.measured_at).label("bucket")
        query = db.session.query(
            bucket,
            value_expr.label("metric_value"),
            count_expr,
            exceeded_expr,
            unit_expr,
        ).group_by(bucket, Measurement.unit)
        is_time_group = True
    elif group_by == "month":
        year = func.extract("year", Measurement.measured_at).label("year")
        month = func.extract("month", Measurement.measured_at).label("month")
        query = db.session.query(
            year, month,
            value_expr.label("metric_value"),
            count_expr,
            exceeded_expr,
            unit_expr,
        ).group_by(year, month, Measurement.unit)
        is_time_group = True
    else:
        column = {
            "pollutant": Measurement.pollutant,
            "period": Measurement.period,
            "data_source": Measurement.data_source,
        }[group_by]
        query = db.session.query(
            column.label("bucket"),
            value_expr.label("metric_value"),
            count_expr,
            exceeded_expr,
            unit_expr,
        ).group_by(column, Measurement.unit)
        is_time_group = False

    query = apply_filters(query, filters)
    rows = query.all()

    # 先把"分组 + 单位"行合并回每个业务分组
    merged = {}
    order = []
    for row in rows:
        data = dict(row._mapping)
        key, label = _group_label(group_by, data)
        if key not in merged:
            merged[key] = {
                "key": key,
                "label": label,
                "count": 0,
                "exceeded": 0,
                "units": [],
                "parts": [],
            }
            order.append(key)
        bucket = merged[key]
        part_count = int(data.get("row_count") or 0)
        bucket["count"] += part_count
        bucket["exceeded"] += int(data.get("exceeded_count") or 0)
        unit = data.get("unit")
        if unit and unit not in bucket["units"]:
            bucket["units"].append(unit)
        bucket["parts"].append(
            {
                "unit": unit,
                "metric_value": data.get("metric_value"),
                "count": part_count,
            }
        )

    items = []
    for key in order:
        bucket = merged[key]
        count = bucket["count"]
        exceeded = bucket["exceeded"]
        units = bucket["units"]
        mixed_units = len(units) > 1

        if metric == "count":
            # 条数与量纲无关, 多单位行直接相加
            value = float(count)
            unit_out = None
            comparable = True
        elif group_by == "pollutant" and not mixed_units:
            meta = get_pollutant(key)
            precision = int(meta["precision"]) if meta else 2
            part = bucket["parts"][0]
            value = round_value(float(part["metric_value"]), precision)
            unit_out = units[0] if units else None
            comparable = True
        elif not mixed_units:
            part = bucket["parts"][0]
            precision = _precision_for_unit(units[0] if units else None)
            if metric == "avg":
                # 单单位下各分段 avg 按行数加权(实际单单位通常只有一段)
                weighted = sum(float(p["metric_value"]) * p["count"] for p in bucket["parts"])
                value = round_value(weighted / count, precision)
            else:
                value = round_value(float(part["metric_value"]), precision)
            unit_out = units[0] if units else None
            comparable = True
        else:
            # 同一分组跨越 μg/m³ 与 mg/m³, 浓度指标不做跨单位聚合
            value = None
            unit_out = None
            comparable = False

        items.append(
            {
                "key": bucket["key"],
                "label": bucket["label"],
                "value": value,
                "unit": unit_out,
                "units": units,
                "mixed_units": mixed_units,
                "comparable": comparable,
                "metric": metric,
                "count": count,
                "exceeded_count": exceeded,
                "exceed_rate": round(exceeded / count, 4) if count else 0.0,
            }
        )

    if is_time_group:
        items.sort(key=lambda item: item["key"])
    elif metric == "count":
        items.sort(key=lambda item: -(item["value"] or 0))
    else:
        # 跨单位分组不可比, 排在可比较分组之后, 避免误导排序
        items.sort(key=lambda item: (not item["comparable"], -(item["value"] or 0)))

    return {
        "group_by": group_by,
        "metric": metric,
        "items": items,
        "mixed_units": len({u for item in items for u in item["units"]}) > 1,
        "totals": {
            "count": sum(item["count"] for item in items),
            "exceeded_count": sum(item["exceeded_count"] for item in items),
        },
    }


def _group_label(group_by, data):
    if group_by == "station":
        key = data.get("station_code")
        return key, "%s %s" % (data.get("station_code"), data.get("station_name"))
    if group_by == "area":
        key = label = data.get("area")
        return key, label
    if group_by == "day":
        key = str(data.get("bucket"))
        return key, key
    if group_by == "month":
        key = "%04d-%02d" % (int(data.get("year")), int(data.get("month")))
        return key, key
    if group_by == "pollutant":
        key = data.get("bucket")
        meta = get_pollutant(key)
        return key, meta["label"] if meta else key
    if group_by == "period":
        key = data.get("bucket")
        return key, PERIOD_LABELS.get(key, key)
    key = data.get("bucket")
    return key, DATA_SOURCE_LABELS.get(key, key)


def option_payload():
    return {
        "group_by": list(GROUP_BY_CHOICES),
        "metric": list(METRIC_CHOICES),
        "sort": list(SORT_CHOICES),
        "exceedance_status": [
            {"value": key, "label": label} for key, label in EXCEEDANCE_STATUS_LABELS.items()
        ],
        "station_type": [
            {"value": key, "label": label} for key, label in STATION_TYPE_LABELS.items()
        ],
    }
