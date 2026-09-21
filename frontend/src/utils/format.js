/** Formatting helpers that keep local (server) wall-clock time intact.
 *
 * 展示口径与后端 app/domain/quantize.py 完全一致:
 * - 浓度按各因子 precision 定长保留小数(颗粒物 1 位, CO 2 位), 不去尾零,
 *   页面看到的数就是参与超标判定的数;
 * - 超标倍数以后端固化的 4 位小数值为准, 展示最多 4 位并去尾零,
 *   超标与否/等级一律信任后端 is_exceeded / level, 前端不再自行按倍数推断。
 */

export function formatDateTime(value, fallback = '-') {
  if (!value) return fallback
  return String(value).replace('T', ' ').slice(0, 16)
}

export function formatDate(value, fallback = '-') {
  if (!value) return fallback
  return String(value).slice(0, 10)
}

/**
 * 浓度值: 按因子精度定长展示 (保留尾零, 如 75.0 / 4.00)。
 * precision 缺省 2 仅用于未知因子的兜底, 正常数据都带后端下发的 precision。
 */
export function formatConcentration(value, precision = 2, fallback = '-') {
  if (value === null || value === undefined || value === '') return fallback
  const number = Number(value)
  if (Number.isNaN(number)) return fallback
  return number.toFixed(Math.max(0, Number(precision) || 0))
}

/**
 * 从行数据上取精度: 行带 precision 用行的, 否则用因子元数据, 最后兜底 2。
 */
export function precisionOf(row, pollutantMeta) {
  if (row?.precision !== undefined && row.precision !== null) return row.precision
  const code = row?.pollutant
  const meta = code && pollutantMeta?.[code]
  return meta?.precision ?? 2
}

/**
 * 兼容旧调用: 通用数字(非浓度)保留指定小数位。浓度展示请改用 formatConcentration。
 */
export function formatNumber(value, precision = 2) {
  if (value === null || value === undefined || value === '') return '-'
  const number = Number(value)
  if (Number.isNaN(number)) return '-'
  const fixed = number.toFixed(precision)
  return fixed.includes('.') ? fixed.replace(/0+$/, '').replace(/\.$/, '') : fixed
}

/** 超标倍数: 后端按 4 位舍入固化, 这里在 4 位内去尾零展示, 结论与后端一致。 */
export function formatRatio(ratio) {
  if (ratio === null || ratio === undefined) return '-'
  const number = Number(ratio)
  if (Number.isNaN(number)) return '-'
  const text = number.toFixed(4).replace(/0+$/, '').replace(/\.$/, '')
  return `${text} 倍`
}

export function formatPercent(rate, digits = 1) {
  if (rate === null || rate === undefined) return '-'
  return `${(Number(rate) * 100).toFixed(digits)}%`
}

/** yyyy-MM-ddTHH:mm for <input type="datetime-local"> */
export function toDateTimeInput(date = new Date()) {
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}
