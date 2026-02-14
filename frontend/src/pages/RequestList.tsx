import { useState } from 'react'
import { useQuery } from '@apollo/client'
import { useNavigate } from 'react-router-dom'
import { GET_PURCHASE_REQUESTS } from '../graphql/queries'
import StatusBadge from '../components/StatusBadge'

const CATEGORIES = ['IT', 'Office Supplies', 'Marketing', 'Facilities', 'Professional Services']
const STATUSES = ['draft', 'submitted', 'pending_approval', 'approved', 'rejected', 'cancelled']

export default function RequestList() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')

  const { data, loading } = useQuery(GET_PURCHASE_REQUESTS, {
    variables: {
      page,
      pageSize: 20,
      status: statusFilter || undefined,
      category: categoryFilter || undefined,
    },
    fetchPolicy: 'cache-and-network',
  })

  const requests = data?.purchaseRequests?.items || []
  const total = data?.purchaseRequests?.total || 0
  const pageSize = data?.purchaseRequests?.pageSize || 20
  const totalPages = Math.ceil(total / pageSize)

  const formatCurrency = (amount: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount)

  const formatDate = (d: string) =>
    new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })

  return (
    <>
      <div className="page-header">
        <h2>Purchase Requests</h2>
        <button className="btn btn-primary" onClick={() => navigate('/requests/new')}>
          New Request
        </button>
      </div>

      <div className="filters-bar">
        <select className="form-control" value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}>
          <option value="">All Statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>{s.replace('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase())}</option>
          ))}
        </select>
        <select className="form-control" value={categoryFilter} onChange={(e) => { setCategoryFilter(e.target.value); setPage(1) }}>
          <option value="">All Categories</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <span style={{ color: 'var(--gray-500)', fontSize: '0.875rem' }}>{total} results</span>
      </div>

      <div className="card">
        {loading && !data ? (
          <div className="loading">Loading...</div>
        ) : requests.length === 0 ? (
          <div className="empty-state">
            <p>No purchase requests found.</p>
            <button className="btn btn-primary" onClick={() => navigate('/requests/new')}>Create your first request</button>
          </div>
        ) : (
          <>
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Vendor</th>
                    <th>Amount</th>
                    <th>Category</th>
                    <th>Status</th>
                    <th>Requester</th>
                    <th>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {requests.map((r: any) => (
                    <tr key={r.id} className="clickable" onClick={() => navigate(`/requests/${r.id}`)}>
                      <td style={{ fontWeight: 500 }}>{r.title}</td>
                      <td>{r.vendor}</td>
                      <td>{formatCurrency(r.amount)}</td>
                      <td>{r.category}</td>
                      <td><StatusBadge status={r.status} /></td>
                      <td>{r.requester?.fullName}</td>
                      <td>{formatDate(r.createdAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {totalPages > 1 && (
              <div className="pagination">
                <span>Page {page} of {totalPages}</span>
                <div className="btn-group">
                  <button className="btn btn-outline btn-sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
                  <button className="btn btn-outline btn-sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Next</button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </>
  )
}
