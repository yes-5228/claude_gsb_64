/** Lightweight CSS bar chart used by the dashboard and statistics panel. */
export default function BarChart({ items = [], danger = false, precision = 1, valueSuffix = '' }) {
  if (items.length === 0) return <div className="empty">暂无统计数据</div>
  const comparableValues = items
    .filter((item) => item.comparable !== false && item.value !== null && item.value !== undefined)
    .map((item) => Number(item.value))
  // 跨单位的分组不参与统一柱高缩放, 避免不同量纲被画成"可比"
  const max = Math.max(...comparableValues, 1)

  return (
    <div className="bar-chart">
      {items.map((item) => {
        const incomparable = item.comparable === false || item.value === null || item.value === undefined
        const height = incomparable ? 2 : Math.max(((Number(item.value) || 0) / max) * 100, 2)
        const hot = danger || item.exceeded_count > 0
        const unitText = item.unit ? ` ${item.unit}` : valueSuffix ? ` ${valueSuffix}` : ''
        return (
          <div className="bar-item" key={item.key ?? item.label}>
            <div className="bar-value">
              {incomparable ? (
                <span className="muted small" title={`包含单位: ${(item.units || []).join('、')}`}>
                  不可混合平均
                </span>
              ) : (
                `${item.value}${unitText}`
              )}
            </div>
            <div className="bar-track">
              <div
                className={`bar-fill ${hot ? 'danger' : ''} ${incomparable ? 'incomparable' : ''}`}
                style={{ height: `${height}%` }}
                title={incomparable ? `${item.label}: 含多种单位, 不做跨单位聚合` : `${item.label}: ${item.value}${unitText}`}
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
