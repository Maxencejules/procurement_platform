import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@apollo/client'
import { GET_PURCHASE_REQUEST, GET_AUDIT_LOGS, SUBMIT_REQUEST, CANCEL_REQUEST } from '../graphql/queries'
import { useAuth } from '../context/AuthContext'
import StatusBadge from '../components/StatusBadge'

export default function RequestDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()
  const { data, loading, refetch } = useQuery(GET_PURCHASE_REQUEST, { variables: { id } })
  const { data: auditData } = useQuery(GET_AUDIT_LOGS, { variables: { entityId: id, pageSize: 50 } })
  const [submitRequest] = useMutation(SUBMIT_REQUEST)
  const [cancelRequest] = useMutation(CANCEL_REQUEST)

  if (loading) return <div className="loading">Loading...</div>
  const pr = data?.purchaseRequest
  if (!pr) return <div className="empty-state"><p>Request not found.</p></div>

  const logs = auditData?.auditLogs?.items || []
  const isOwner = pr.requesterId === user?.id
  const canSubmit = pr.status === 'draft' && isOwner
  const canCancel = ['draft', 'submitted', 'pending_approval'].includes(pr.status) && isOwner

  const formatCurrency = (a: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(a)
  const formatDateTime = (d: string) => new Date(d).toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' })

  const handleSubmit = async () => {
    await submitRequest({ variables: { id } })
    refetch()
  }

  const handleCancel = async () => {
    await cancelRequest({ variables: { id } })
    refetch()
  }

  return (
    <>
      <div className="page-header">
        <h2>{pr.title}</h2>
        <div className="btn-group">
          {canSubmit && <button className="btn btn-primary" onClick={handleSubmit}>Submit for Approval</button>}
          {canCancel && <button className="btn btn-danger" onClick={handleCancel}>Cancel Request</button>}
          <button className="btn btn-outline" onClick={() => navigate('/requests')}>Back to List</button>
        </div>
      </div>

      <div className="detail-grid">
        <div>
          <div className="card" style={{ marginBottom: '1.5rem' }}>
            <div className="card-header">Request Details</div>
            <div className="card-body">
              <div className="detail-field">
                <div className="field-label">Status</div>
                <div className="field-value"><StatusBadge status={pr.status} /></div>
              </div>
              <div className="form-row">
                <div className="detail-field">
                  <div className="field-label">Vendor</div>
                  <div className="field-value">{pr.vendor}</div>
                </div>
                <div className="detail-field">
                  <div className="field-label">Amount</div>
                  <div className="field-value">{formatCurrency(pr.amount)}</div>
                </div>
              </div>
              <div className="form-row">
                <div className="detail-field">
                  <div className="field-label">Category</div>
                  <div className="field-value">{pr.category}</div>
                </div>
                <div className="detail-field">
                  <div className="field-label">Cost Center</div>
                  <div className="field-value">{pr.costCenter}</div>
                </div>
              </div>
              <div className="detail-field">
                <div className="field-label">Requester</div>
                <div className="field-value">{pr.requester?.fullName} ({pr.requester?.email})</div>
              </div>
              {pr.description && (
                <div className="detail-field">
                  <div className="field-label">Description</div>
                  <div className="field-value">{pr.description}</div>
                </div>
              )}
              <div className="form-row">
                <div className="detail-field">
                  <div className="field-label">Created</div>
                  <div className="field-value">{formatDateTime(pr.createdAt)}</div>
                </div>
                {pr.submittedAt && (
                  <div className="detail-field">
                    <div className="field-label">Submitted</div>
                    <div className="field-value">{formatDateTime(pr.submittedAt)}</div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        <div>
          {/* Approval Steps */}
          {pr.approvalSteps.length > 0 && (
            <div className="card" style={{ marginBottom: '1.5rem' }}>
              <div className="card-header">Approval Steps</div>
              <div className="card-body">
                <div className="timeline">
                  {pr.approvalSteps.map((step: any) => (
                    <div
                      key={step.id}
                      className={`timeline-item ${
                        step.status === 'approved' ? 'success' : step.status === 'rejected' ? 'danger' : step.status === 'pending' ? 'active' : ''
                      }`}
                    >
                      <div className="timeline-label">
                        Step {step.stepOrder}: {step.policy?.name || 'Review'}
                      </div>
                      <div className="timeline-detail">
                        Approver: {step.approver?.fullName} &middot; <StatusBadge status={step.status} />
                      </div>
                      {step.decision && (
                        <div className="timeline-detail">
                          {step.decision.decider?.fullName} {step.decision.decision} on {formatDateTime(step.decision.decidedAt)}
                          {step.decision.comments && <div style={{ marginTop: '0.25rem', fontStyle: 'italic' }}>"{step.decision.comments}"</div>}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Audit Log */}
          <div className="card">
            <div className="card-header">Audit Trail</div>
            <div className="card-body">
              {logs.length === 0 ? (
                <div className="empty-state"><p>No audit entries.</p></div>
              ) : (
                <div className="timeline">
                  {logs.map((log: any) => (
                    <div key={log.id} className="timeline-item">
                      <div className="timeline-label">{log.action.replace('_', ' ')}</div>
                      <div className="timeline-detail">
                        {log.performer?.fullName} &middot; {formatDateTime(log.createdAt)}
                        {log.oldValue && log.newValue && (
                          <span> &middot; {log.oldValue} → {log.newValue}</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
