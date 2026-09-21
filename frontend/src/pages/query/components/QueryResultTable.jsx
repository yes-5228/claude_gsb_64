import DataTable from '../../../components/common/DataTable.jsx'
import Tag from '../../../components/common/Tag.jsx'
import { DATA_SOURCE_TONE, EXCEEDANCE_STATUS_TONE } from '../../../constants/index.js'
import { formatDateTime } from '../../../utils/format.js'
import { formatFixed, rowPrecision, usePollutantItems } from '../../../utils/pollutants.js'

function ValueWithUnit({ row }) {
  const items = usePollutantItems()
  return (
    <span className={row.is_exceeded ? 'danger-text strong' : ''}>
      {formatFixed(row.value, rowPrecision(row, items))} <span className="muted small">{row.unit}</span>
    </span>
  )
}

function LimitCell({ row }) {
  const items = usePollutantItems()
  if (row.limit_value === null || row.limit_value === undefined) return <span className="muted">无限值</span>
  return (
    <span>
      {formatFixed(row.limit_value, rowPrecision(row, items))} <span className="muted small">{row.unit}</span>
    </span>
  )
}

export default function QueryResultTable({ rows, loading }) {
  const columns = [
    { key: 'measured_at', title: '监测时间', className: 'cell-nowrap', render: (row) => formatDateTime(row.measured_at) },
    { key: 'station', title: '监测点', render: (row) => `${row.station?.code || ''} ${row.station?.name || ''}` },
    { key: 'station_area', title: '区域', render: (row) => row.station?.area || '-' },
    { key: 'pollutant_label', title: '因子', className: 'cell-nowrap' },
    { key: 'period_label', title: '周期', className: 'cell-nowrap' },
    { key: 'value', title: '监测值', align: 'right', className: 'cell-nowrap', render: (row) => <ValueWithUnit row={row} /> },
    { key: 'limit_value', title: '限值', align: 'right', className: 'cell-nowrap', render: (row) => <LimitCell row={row} /> },
    {
      key: 'is_exceeded',
      title: '超标',
      render: (row) => (row.is_exceeded ? <Tag tone="danger">是</Tag> : <Tag tone="success">否</Tag>)
    },
    {
      key: 'exceedance_status',
      title: '标注状态',
      render: (row) =>
        row.exceedance_status ? (
          <Tag tone={EXCEEDANCE_STATUS_TONE[row.exceedance_status]}>
            {row.exceedance_status === 'pending' ? '待标注' : row.exceedance_status === 'confirmed' ? '已确认' : '已忽略'}
          </Tag>
        ) : (
          <span className="muted">-</span>
        )
    },
    {
      key: 'data_source_label',
      title: '来源',
      render: (row) => <Tag tone={DATA_SOURCE_TONE[row.data_source]}>{row.data_source_label}</Tag>
    },
    { key: 'recorder', title: '录入人', render: (row) => row.recorder || '-' }
  ]

  return (
    <DataTable
      columns={columns}
      rows={rows}
      loading={loading}
      emptyText="没有符合条件的数据, 请调整筛选条件"
      emptyIcon="🔍"
    />
  )
}
