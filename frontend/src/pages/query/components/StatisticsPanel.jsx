import { SectionCard } from '../../../components/common/Card.jsx'
import { Alert, EmptyState, Loading } from '../../../components/common/Feedback.jsx'
import BarChart from '../../../components/common/BarChart.jsx'
import { Field, Select } from '../../../components/common/FormField.jsx'
import { formatPercent } from '../../../utils/format.js'

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

function MetricValue({ item }) {
  // 后端已按因子精度取整, 这里直接展示; 不可比(跨单位)分组显示占位
  if (item.value === null || item.value === undefined) {
    return <span className="muted" title={`包含单位: ${(item.units || []).join('、')}`}>— 不可混算</span>
  }
  return (
    <>
      {item.value}
      {item.unit ? <span className="muted small"> {item.unit}</span> : null}
    </>
  )
}

export default function StatisticsPanel({ params, onChange, data, loading, error, onRun }) {
  const items = data?.items ?? []
  const isCount = params.metric === 'count'
  const hasIncomparable = items.some((item) => item.comparable === false)

  return (
    <SectionCard
      title="聚合统计"
      hint="统计基于上方筛选条件, 可与结果表交叉验证"
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
        {hasIncomparable && !isCount ? (
          <Alert tone="warning">
            部分分组同时包含 μg/m³ 与 mg/m³ 的因子, 浓度单位不同不能直接比较或平均,
            这些分组不输出统计值; 如需对比请按“监测因子”分组或在筛选中限定单一因子。
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
                      <td className="text-right strong">
                        <MetricValue item={item} />
                      </td>
                      <td className="text-right">{item.count}</td>
                      <td className="text-right danger-text">{item.exceeded_count}</td>
                      <td className="text-right">{formatPercent(item.exceed_rate)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!isCount ? (
              <p className="small muted">
                说明: 各因子按自身单位参与统计, μg/m³ 与 mg/m³ 不做跨单位换算;
                限值判定以记录保存时的标准口径与限值快照为准。
              </p>
            ) : null}
          </>
        ) : null}
      </div>
    </SectionCard>
  )
}
