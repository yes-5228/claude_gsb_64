/**
 * 监测因子元数据与单位/精度的唯一口径来源。
 *
 * 后端 /api/meta/pollutants 下发每个因子的 unit 与 precision;
 * 列表、图表、导出、标注页面一律通过这里的 helper 取精度与单位,
 * 避免同一因子在不同页面出现不同小数位或漏掉单位。
 */
import { usePollutantMeta } from '../hooks/useOptions.js'

/** 不依赖接口数据时的兜底(与后端 standards.py 保持一致)。 */
export const FALLBACK_PRECISION = 2

/** @type {Record<string, {label: string, unit: string, precision: number}>} */
const POLLUTANT_FALLBACK = {
  PM25: { label: 'PM2.5', unit: 'μg/m³', precision: 1 },
  PM10: { label: 'PM10', unit: 'μg/m³', precision: 1 },
  SO2: { label: 'SO₂', unit: 'μg/m³', precision: 1 },
  NO2: { label: 'NO₂', unit: 'μg/m³', precision: 1 },
  CO: { label: 'CO', unit: 'mg/m³', precision: 2 },
  O3: { label: 'O₃', unit: 'μg/m³', precision: 1 }
}

/** 返回因子在元数据中的精度(小数位), 缺省回退 2 位。 */
export function precisionOf(code, pollutantItems) {
  const fromApi = (pollutantItems || []).find((item) => item.code === code)
  if (fromApi && Number.isInteger(fromApi.precision)) return fromApi.precision
  return POLLUTANT_FALLBACK[code]?.precision ?? FALLBACK_PRECISION
}

/** 返回因子单位。 */
export function unitOf(code, pollutantItems) {
  const fromApi = (pollutantItems || []).find((item) => item.code === code)
  return fromApi?.unit || POLLUTANT_FALLBACK[code]?.unit || ''
}

/**
 * 行级精度: 优先使用后端记录上的快照精度(历史记录可能按旧口径取整),
 * 其次因子元数据, 最后兜底。
 */
export function rowPrecision(row, pollutantItems) {
  if (row && Number.isInteger(row.precision)) return row.precision
  return precisionOf(row?.pollutant, pollutantItems)
}

/**
 * 按固定精度四舍五入(与后端 ROUND_HALF_UP 对齐), 不抹零:
 * 80.0 在 1 位精度下显示 "80.0", CO 1.4 在 2 位精度下显示 "1.40"。
 */
export function formatFixed(value, precision = FALLBACK_PRECISION, fallback = '-') {
  if (value === null || value === undefined || value === '') return fallback
  const number = Number(value)
  if (Number.isNaN(number)) return fallback
  return halfUp(number, precision).toFixed(precision)
}

/** 浏览器 toFixed 对负数等边界为银行家舍入, 数值为正浓度时影响极小; 这里显式半入保证一致。 */
export function halfUp(number, precision) {
  if (!Number.isFinite(number)) return number
  const factor = 10 ** precision
  const sign = number < 0 ? -1 : 1
  return (Math.round(Math.abs(number) * factor) / factor) * sign
}

/** Hook: 直接拿到因子元数据数组。 */
export function usePollutantItems() {
  const { data } = usePollutantMeta()
  return data?.items ?? []
}

/** Hook: 返回 code -> meta 的格式化辅助函数集合。 */
export function usePollutantFormat() {
  const items = usePollutantItems()
  return {
    items,
    precision: (code) => precisionOf(code, items),
    unit: (code) => unitOf(code, items),
    /** 按因子精度格式化监测值/限值。 */
    formatValue: (row) => formatFixed(row?.value, rowPrecision(row, items)),
    formatLimit: (row) =>
      row?.limit_value === null || row?.limit_value === undefined
        ? null
        : formatFixed(row.limit_value, rowPrecision(row, items)),
    formatValueByCode: (code, value) => formatFixed(value, precisionOf(code, items))
  }
}
