import DataTable from '../../../components/common/DataTable.jsx'
import Tag from '../../../components/common/Tag.jsx'
import { DATA_SOURCE_TONE } from '../../../constants/index.js'
import { formatDateTime, formatRatio } from '../../../utils/format.js'
import { formatFixed, rowPrecision, usePollutantItems } from '../../../utils/pollutants.js'

function ValueWithUnit({ row }) {
  const items = usePollutantItems()
  const precision = rowPrecision(row, items)
  return (
    <span className={row.is_exceeded ? 'danger-text strong' : ''}>
      {formatFixed(row.value, precision)}{' '}
      <span className="muted small">{row.unit}</span>
    </span>
  )
}

function LimitCell({ row }) {
  const items = usePollutantItems()
  if (row.limit_value === null || row.limit_value === undefined) {
    return <span className="muted small">无限值</span>
  }
  // 限值与监测值使用同一因子精度与单位, 保证两个数可以直接对齐比较
  return (
    <span>
      {formatFixed(row.limit_value, rowPrecision(row, items))}{' '}
      <span className="muted small">{row.unit}</span>
    </span>
  )
}

export default function MeasurementTable({ rows, loading, onDelete }) {
  const columns = [
    { key: 'measured_at', title: '监测时间', className: 'cell-nowrap', render: (row) => formatDateTime(row.measured_at) },
    {
      key: 'station',
      title: '监测点',
      render: (row) => (
        <div>
          <div>{row.station?.name || '-'}</div>
          <div className="small muted mono">{row.station?.code || ''}</div>
        </div>
      )
    },
    { key: 'pollutant_label', title: '监测因子', className: 'cell-nowrap' },
    { key: 'period_label', title: '周期', className: 'cell-nowrap' },
    { key: 'value', title: '监测值', align: 'right', className: 'cell-nowrap', render: (row) => <ValueWithUnit row={row} /> },
    { key: 'limit_value', title: '限值', align: 'right', className: 'cell-nowrap', render: (row) => <LimitCell row={row} /> },
    {
      key: 'is_exceeded',
      title: '超标判定',
      className: 'cell-nowrap',
      render: (row) =>
        row.is_exceeded ? <Tag tone="danger">{formatRatio(row.exceed_ratio)}</Tag> : <Tag tone="success">达标</Tag>
    },
    {
      key: 'data_source',
      title: '来源',
      render: (row) => <Tag tone={DATA_SOURCE_TONE[row.data_source]}>{row.data_source_label}</Tag>
    },
    { key: 'recorder', title: '录入人', render: (row) => row.recorder || '-' },
    {
      key: 'actions',
      title: '操作',
      align: 'right',
      render: (row) => (
        <button type="button" className="btn btn-sm btn-danger" onClick={() => onDelete(row)}>
          删除
        </button>
      )
    }
  ]

  return (
    <DataTable
      columns={columns}
      rows={rows}
      loading={loading}
      emptyText="暂无监测数据, 请先在上方录入"
      emptyIcon="✍️"
    />
  )
}
