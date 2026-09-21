"""监测数据记录."""
from ..domain.constants import DATA_SOURCE_LABELS, PERIOD_LABELS, label_of
from ..domain.standards import get_pollutant
from ..extensions import db
from .base import TimestampMixin, iso


class Measurement(TimestampMixin, db.Model):
    __tablename__ = "measurements"
    __table_args__ = (
        db.UniqueConstraint(
            "station_id", "pollutant", "period", "measured_at",
            name="uq_measurement_point_factor_time",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(
        db.Integer, db.ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pollutant = db.Column(db.String(16), nullable=False, index=True)
    period = db.Column(db.String(16), nullable=False, default="hourly")
    value = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(16))
    precision = db.Column(db.Integer)
    limit_value = db.Column(db.Float)
    # 判定时使用的标准口径与限值快照: 标准修订后历史记录仍按当时口径展示/解释
    standard_key = db.Column(db.String(48))
    standard_label = db.Column(db.String(96))
    exceed_ratio = db.Column(db.Float)
    is_exceeded = db.Column(db.Boolean, nullable=False, default=False, index=True)
    measured_at = db.Column(db.DateTime, nullable=False, index=True)
    data_source = db.Column(db.String(16), nullable=False, default="manual")
    recorder = db.Column(db.String(64))
    remark = db.Column(db.Text)

    station = db.relationship("Station", back_populates="measurements")
    exceedance = db.relationship(
        "Exceedance",
        back_populates="measurement",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def pollutant_label(self):
        meta = get_pollutant(self.pollutant)
        return meta["label"] if meta else self.pollutant

    def to_dict(self, include_station=False):
        payload = {
            "id": self.id,
            "station_id": self.station_id,
            "pollutant": self.pollutant,
            "pollutant_label": self.pollutant_label(),
            "period": self.period,
            "period_label": label_of(PERIOD_LABELS, self.period),
            "value": self.value,
            "unit": self.unit,
            "precision": self.precision,
            "limit_value": self.limit_value,
            "standard_key": self.standard_key,
            "standard_label": self.standard_label,
            "exceed_ratio": self.exceed_ratio,
            "is_exceeded": bool(self.is_exceeded),
            "measured_at": iso(self.measured_at),
            "data_source": self.data_source,
            "data_source_label": label_of(DATA_SOURCE_LABELS, self.data_source),
            "recorder": self.recorder,
            "remark": self.remark,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
            "exceedance_id": self.exceedance.id if self.exceedance else None,
            "exceedance_status": self.exceedance.status if self.exceedance else None,
        }
        if include_station and self.station:
            payload["station"] = {
                "id": self.station.id,
                "code": self.station.code,
                "name": self.station.name,
                "area": self.station.area,
                "station_type_label": self.station.to_dict()["station_type_label"],
            }
        return payload

    def __repr__(self):
        return "<Measurement %s %s %s>" % (self.station_id, self.pollutant, self.measured_at)

    @classmethod
    def unique_key(cls, station_id, pollutant, period, measured_at):
        return "%s|%s|%s|%s" % (station_id, pollutant, period, iso(measured_at))
