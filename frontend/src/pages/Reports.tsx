import { useQuery } from '@apollo/client'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts'
import { GET_CYCLE_TIME_REPORT, GET_CATEGORY_REPORT, GET_BOTTLENECK_REPORT } from '../graphql/queries'

const COLORS = ['#2563eb', '#16a34a', '#d97706', '#dc2626', '#7c3aed', '#0891b2']

const STATUS_LABELS: Record<string, string> = {
  submitted: 'Submitted',
  pending_approval: 'Pending',
  approved: 'Approved',
  rejected: 'Rejected',
}

export default function Reports() {
  const { data: cycleData, loading: loadingCycle } = useQuery(GET_CYCLE_TIME_REPORT)
  const { data: catData, loading: loadingCat } = useQuery(GET_CATEGORY_REPORT)
  const { data: bottleneckData, loading: loadingBottle } = useQuery(GET_BOTTLENECK_REPORT)

  const cycleTime = (cycleData?.cycleTimeReport || []).map((r: any) => ({
    ...r,
    label: STATUS_LABELS[r.status] || r.status,
  }))

  const categories = catData?.categoryReport || []
  const bottlenecks = bottleneckData?.bottleneckReport || []

  const formatCurrency = (a: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(a)

  const totalRequests = categories.reduce((s: number, c: any) => s + c.count, 0)
  const totalSpend = categories.reduce((s: number, c: any) => s + c.totalAmount, 0)

  return (
    <>
      <div className="page-header">
        <h2>Reporting Dashboard</h2>
      </div>

      <div className="stat-grid">
        <div className="card stat-card">
          <div className="stat-label">Total Requests</div>
          <div className="stat-value">{totalRequests}</div>
        </div>
        <div className="card stat-card">
          <div className="stat-label">Total Spend</div>
          <div className="stat-value">{formatCurrency(totalSpend)}</div>
        </div>
        <div className="card stat-card">
          <div className="stat-label">Categories</div>
          <div className="stat-value">{categories.length}</div>
        </div>
        <div className="card stat-card">
          <div className="stat-label">Pending Approvals</div>
          <div className="stat-value">{bottlenecks.reduce((s: number, b: any) => s + b.pendingCount, 0)}</div>
        </div>
      </div>

      <div className="chart-grid">
        <div className="card chart-card">
          <div className="card-header">Cycle Time by Status (hours from creation)</div>
          <div className="card-body">
            {loadingCycle ? (
              <div className="loading">Loading...</div>
            ) : cycleTime.length === 0 ? (
              <div className="empty-state"><p>No data yet.</p></div>
            ) : (
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={cycleTime}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="label" fontSize={12} />
                  <YAxis fontSize={12} />
                  <Tooltip />
                  <Bar dataKey="avgHours" fill="#2563eb" name="Avg Hours" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        <div className="card chart-card">
          <div className="card-header">Requests by Category</div>
          <div className="card-body">
            {loadingCat ? (
              <div className="loading">Loading...</div>
            ) : categories.length === 0 ? (
              <div className="empty-state"><p>No data yet.</p></div>
            ) : (
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={categories}
                    dataKey="count"
                    nameKey="category"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    label={({ category, count }: any) => `${category} (${count})`}
                  >
                    {categories.map((_: any, i: number) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value: any, name: any, props: any) => [value, props.payload.category]} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">Approval Bottleneck View</div>
        {loadingBottle ? (
          <div className="loading">Loading...</div>
        ) : bottlenecks.length === 0 ? (
          <div className="card-body"><div className="empty-state"><p>No pending approvals - no bottlenecks.</p></div></div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Approver</th>
                  <th>Pending Items</th>
                  <th>Avg Decision Time</th>
                </tr>
              </thead>
              <tbody>
                {bottlenecks.map((b: any) => (
                  <tr key={b.approverId}>
                    <td style={{ fontWeight: 500 }}>{b.approverName}</td>
                    <td>
                      <span style={{
                        color: b.pendingCount > 5 ? 'var(--danger)' : b.pendingCount > 2 ? 'var(--warning)' : 'var(--gray-700)',
                        fontWeight: 600,
                      }}>
                        {b.pendingCount}
                      </span>
                    </td>
                    <td>{b.avgDecisionHours != null ? `${b.avgDecisionHours}h` : 'N/A'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Category spend breakdown */}
      <div className="card" style={{ marginTop: '1.5rem' }}>
        <div className="card-header">Spend by Category</div>
        {loadingCat ? (
          <div className="loading">Loading...</div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Requests</th>
                  <th>Total Amount</th>
                  <th>% of Total</th>
                </tr>
              </thead>
              <tbody>
                {categories.map((c: any) => (
                  <tr key={c.category}>
                    <td style={{ fontWeight: 500 }}>{c.category}</td>
                    <td>{c.count}</td>
                    <td>{formatCurrency(c.totalAmount)}</td>
                    <td>{totalSpend > 0 ? `${((c.totalAmount / totalSpend) * 100).toFixed(1)}%` : '0%'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  )
}
