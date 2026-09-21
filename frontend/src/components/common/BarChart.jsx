import { formatConcentration, formatNumber } from '../../utils/format.js'

/**
 * Lightweight CSS bar chart used by the dashboard and statistics panel.
 * 每个 item 可自带 precision/unit; 缺失时回退到 precision 参数。
 * value 为 null 表示该组口径不可比(如跨单位聚合), 不参与柱高与标注。
 */
export default function BarChart({ items = [], danger = false, precision = 1, unit = null }) {
  if (items.length === 0) return <div className="empty">暂无统计数据</div>
  const numeric = items
    .map((item) => Number(item.value))
    .filter((value) => Number.isFinite(value))
  if (numeric.length === 0) {
    return <div className="empty">所选口径下统计值不可比(因子单位不同), 请按单一因子筛选</div>
  }
  const max = Math.max(...numeric, 1)

  return (
    <div className="bar-chart">
      {items.map((item) => {
        const number = Number(item.value)
        const comparable = Number.isFinite(number)
        const height = comparable ? Math.max((number / max) * 100, 2) : 0
        const hot = danger || item.exceeded_count > 0
        const itemPrecision = item.precision ?? precision
        const valueText = comparable
          ? item.unit || unit
            ? `${formatConcentration(number, itemPrecision)} ${item.unit || unit}`
            : formatNumber(number, itemPrecision)
          : '不可比'
        return (
          <div className="bar-item" key={item.key ?? item.label}>
            <div className="bar-value">{valueText}</div>
            <div className="bar-track">
              <div
                className={`bar-fill ${hot ? 'danger' : ''}`}
                style={{ height: `${height}%` }}
                title={comparable ? `${item.label}: ${valueText}` : `${item.label}: 单位不同不可比`}
              />
            </div>
            <div className="bar-label" title={item.label}>
              {item.label}
            </div>
          </div>
        )
      })}
    </div>
  )
}
