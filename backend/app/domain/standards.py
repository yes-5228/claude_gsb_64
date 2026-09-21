"""污染物监测因子、单位与限值定义.

限值按"标准口径"(standards catalog)管理: 每条数据落库时记录当时使用的
``standard_key`` 与限值快照(measurement.limit_value / exceedance.limit_value),
日后标准修订只会改变新录入数据的判定, 历史记录展示的限值、超标结论与等级
始终以快照为准, 不被改写。

当前生效标准: GB 3095-2012《环境空气质量标准》二级浓度限值。
"""

# period 取值: hourly = 1 小时平均, daily = 24 小时平均
# precision = 监测浓度保留的小数位数, 取整方式见 domain/rounding.py(四舍五入)
POLLUTANTS = {
    "PM25": {
        "code": "PM25",
        "label": "PM2.5",
        "name": "细颗粒物",
        "unit": "μg/m³",
        "precision": 1,
    },
    "PM10": {
        "code": "PM10",
        "label": "PM10",
        "name": "可吸入颗粒物",
        "unit": "μg/m³",
        "precision": 1,
    },
    "SO2": {
        "code": "SO2",
        "label": "SO₂",
        "name": "二氧化硫",
        "unit": "μg/m³",
        "precision": 1,
    },
    "NO2": {
        "code": "NO2",
        "label": "NO₂",
        "name": "二氧化氮",
        "unit": "μg/m³",
        "precision": 1,
    },
    "CO": {
        "code": "CO",
        "label": "CO",
        "name": "一氧化碳",
        "unit": "mg/m³",
        "precision": 2,
    },
    "O3": {
        "code": "O3",
        "label": "O₃",
        "name": "臭氧",
        "unit": "μg/m³",
        "precision": 1,
    },
}

# ---------------------------------------------------------------------------
# 标准口径(限值表)
# ---------------------------------------------------------------------------
# key 一经发布即冻结, 限值修订时新增一个 key(version 递增)并把
# CURRENT_STANDARD_KEY 指向它; 旧 key 保留在目录中供历史记录回显与审计,
# 历史记录的判定结论永远不会被新标准改写。
# 限值 None 表示该因子在该周期不设限值(仅记录数值, 不参与超标判定)。
_STANDARD_LIMITS_V1 = {
    "PM25": {"daily": 75.0, "hourly": None},
    "PM10": {"daily": 150.0, "hourly": None},
    "SO2": {"daily": 150.0, "hourly": 500.0},
    "NO2": {"daily": 80.0, "hourly": 200.0},
    "CO": {"daily": 4.0, "hourly": 10.0},
    "O3": {"daily": 160.0, "hourly": 200.0},
}

STANDARDS = {
    "GB3095-2012:L2:v1": {
        "key": "GB3095-2012:L2:v1",
        "code": "GB 3095-2012",
        "name": "环境空气质量标准",
        "level": "二级",
        "version": 1,
        "label": "GB 3095-2012 环境空气质量标准(二级)",
        "limits": _STANDARD_LIMITS_V1,
    },
}

# 当前系统判定使用的标准口径; 切换后仅影响新录入/修正时的判定。
CURRENT_STANDARD_KEY = "GB3095-2012:L2:v1"

# 供录入表单/接口直接读取的"当前标准限值", 挂在因子定义上保持既有结构。
for _code, _item in POLLUTANTS.items():
    _item["limits"] = STANDARDS[CURRENT_STANDARD_KEY]["limits"][_code]

POLLUTANT_CODES = tuple(POLLUTANTS.keys())


def get_pollutant(code):
    """Return the pollutant definition or None when unknown."""
    return POLLUTANTS.get(str(code or "").upper())


def get_standard(key=None):
    """Return the standard descriptor (defaults to the active one)."""
    return STANDARDS.get(key or CURRENT_STANDARD_KEY)


def current_standard():
    return STANDARDS[CURRENT_STANDARD_KEY]


def get_limit(code, period, standard_key=None):
    """Return the concentration limit for pollutant/period under a standard.

    历史记录回显应直接使用记录上的 limit_value 快照; 本函数用于按指定标准
    口径取限值(默认当前标准)。未知因子/周期或已下架的标准返回 None。
    """
    pollutant = get_pollutant(code)
    standard = STANDARDS.get(standard_key or CURRENT_STANDARD_KEY)
    if not pollutant or not standard:
        return None
    return standard["limits"].get(pollutant["code"], {}).get(period)


def pollutant_options():
    """Serialisable list used by the frontend dropdowns."""
    return [dict(item) for item in POLLUTANTS.values()]
