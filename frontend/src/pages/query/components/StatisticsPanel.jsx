import { SectionCard } from '../../../components/common/Card.jsx'
import { Alert, EmptyState, Loading } from '../../../components/common/Feedback.jsx'
import BarChart from '../../../components/common/BarChart.jsx'
import { Field, Select } from '../../../components/common/FormField.jsx'
import { formatConcentration, formatNumber, formatPercent } from '../../../utils/format.js'

const GROUP_OPTIONS = [
  { value: 'pollutant', label: '按监测因子' },
  { value: 'station', label: '按监测点' },
  { value: 'area', label: '按区域' },
  { value: 'day', label: '按日' },
  { value: 'month', label: '按月' },
  { value: 'period', label: '按数据周期' },
  { value: 'data_source', label: '按数据来源' }
]

const METRIC_OPTIONS = [
  { value: 'avg', label: '平均值' },
  { value: 'max', label: '最大值' },
  { value: 'min', label: '最小值' },
  { value: 'count', label: '数据条数' },
  { value: 'sum', label: '合计' }
]

function formatStat(item, isCount) {
  if (item.value === null || item.value === undefined) return '不可比'
  if (isCount) return formatNumber(item.value, 0)
  return item.unit
    ? `${formatConcentration(item.value, item.precision ?? 2)} ${item.unit}`
    : formatConcentration(item.value, item.precision ?? 2)
}

export default function StatisticsPanel({ params, onChange, data, loading, error, onRun }) {
  const items = data?.items ?? []
  const isCount = params.metric === 'count'
  const mixedUnit = !isCount && data && data.value_comparable === false

  return (
    <SectionCard
      title="聚合统计"
      hint="统计基于上方筛选条件; 不同单位(μg/m³ 与 mg/m³)的因子不跨单位混算"
      actions={
        <>
          <div style={{ width: 160 }}>
            <Select
              value={params.group_by}
              onChange={(event) => onChange({ ...params, group_by: event.target.value })}
              options={GROUP_OPTIONS}
            />
          </div>
          <div style={{ width: 140 }}>
            <Select
              value={params.metric}
              onChange={(event) => onChange({ ...params, metric: event.target.value })}
              options={METRIC_OPTIONS}
            />
          </div>
          <button type="button" className="btn btn-sm btn-primary" onClick={() => onRun()} disabled={loading}>
            {loading ? '统计中...' : '执行统计'}
          </button>
        </>
      }
    >
      <div className="stack">
        {error ? <Alert tone="error">{error.message}</Alert> : null}
        {mixedUnit ? (
          <Alert tone="warning">
            当前筛选包含不同单位的因子(如 CO 为 mg/m³, 其余为 μg/m³), 平均值/极值/合计不做跨单位比较,
            显示“不可比”; 数据量与超标率仍可统计。请按单一因子筛选或选择“按监测因子”分组查看各自单位。
          </Alert>
        ) : null}
        {loading && items.length === 0 ? <Loading text="正在统计..." /> : null}
        {!loading && items.length === 0 && !error ? (
          <EmptyState text="点击“执行统计”查看聚合结果" icon="📈" />
        ) : null}
        {items.length > 0 ? (
          <>
            <BarChart items={items} danger />
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>分组</th>
                    <th className="text-right">{isCount ? '数据条数' : '统计值'}</th>
                    <th className="text-right">数据量</th>
                    <th className="text-right">超标数</th>
                    <th className="text-right">超标率</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.key}>
                      <td>{item.label}</td>
                      <td className={`text-right strong ${item.comparable === false ? 'muted' : ''}`}>
                        {formatStat(item, isCount)}
                      </td>
                      <td className="text-right">{item.count}</td>
                      <td className="text-right danger-text">{item.exceeded_count}</td>
                      <td className="text-right">{formatPercent(item.exceed_rate)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : null}
      </div>
    </SectionCard>
  )
}
