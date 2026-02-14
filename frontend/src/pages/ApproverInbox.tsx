import { useState } from 'react'
import { useQuery, useMutation } from '@apollo/client'
import { useNavigate } from 'react-router-dom'
import { GET_APPROVAL_INBOX, APPROVE_STEP, REJECT_STEP } from '../graphql/queries'
import StatusBadge from '../components/StatusBadge'

export default function ApproverInbox() {
  const navigate = useNavigate()
  const { data, loading, refetch } = useQuery(GET_APPROVAL_INBOX, { fetchPolicy: 'cache-and-network' })
  const [approveStep] = useMutation(APPROVE_STEP)
  const [rejectStep] = useMutation(REJECT_STEP)
  const [activeModal, setActiveModal] = useState<{ stepId: string; action: 'approve' | 'reject' } | null>(null)
  const [comments, setComments] = useState('')
  const [processing, setProcessing] = useState(false)

  const steps = data?.approvalInbox || []

  const formatCurrency = (a: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(a)

  const handleDecision = async () => {
    if (!activeModal) return
    setProcessing(true)
    try {
      const mutation = activeModal.action === 'approve' ? approveStep : rejectStep
      await mutation({ variables: { stepId: activeModal.stepId, comments: comments || null } })
      setActiveModal(null)
      setComments('')
      refetch()
    } finally {
      setProcessing(false)
    }
  }

  return (
    <>
      <div className="page-header">
        <h2>Approver Inbox</h2>
        <span style={{ color: 'var(--gray-500)', fontSize: '0.875rem' }}>{steps.length} pending</span>
      </div>

      <div className="card">
        {loading && steps.length === 0 ? (
          <div className="loading">Loading...</div>
        ) : steps.length === 0 ? (
          <div className="empty-state"><p>No pending approvals. You're all caught up!</p></div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Request</th>
                  <th>Vendor</th>
                  <th>Amount</th>
                  <th>Category</th>
                  <th>Requester</th>
                  <th>Policy</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {steps.map((step: any) => {
                  const pr = step.purchaseRequest
                  return (
                    <tr key={step.id}>
                      <td>
                        <a
                          href="#"
                          onClick={(e) => { e.preventDefault(); navigate(`/requests/${pr.id}`) }}
                          style={{ fontWeight: 500, color: 'var(--primary)', textDecoration: 'none' }}
                        >
                          {pr.title}
                        </a>
                      </td>
                      <td>{pr.vendor}</td>
                      <td>{formatCurrency(pr.amount)}</td>
                      <td>{pr.category}</td>
                      <td>{pr.requester?.fullName}</td>
                      <td>{step.policy?.name}</td>
                      <td>
                        <div className="btn-group">
                          <button
                            className="btn btn-success btn-sm"
                            onClick={() => setActiveModal({ stepId: step.id, action: 'approve' })}
                          >
                            Approve
                          </button>
                          <button
                            className="btn btn-danger btn-sm"
                            onClick={() => setActiveModal({ stepId: step.id, action: 'reject' })}
                          >
                            Reject
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {activeModal && (
        <div className="modal-overlay" onClick={() => setActiveModal(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{activeModal.action === 'approve' ? 'Approve' : 'Reject'} Request</h3>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label htmlFor="comments">Comments (optional)</label>
                <textarea
                  id="comments"
                  className="form-control"
                  value={comments}
                  onChange={(e) => setComments(e.target.value)}
                  placeholder="Add your comments..."
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => { setActiveModal(null); setComments('') }}>
                Cancel
              </button>
              <button
                className={`btn ${activeModal.action === 'approve' ? 'btn-success' : 'btn-danger'}`}
                onClick={handleDecision}
                disabled={processing}
              >
                {processing ? 'Processing...' : activeModal.action === 'approve' ? 'Confirm Approve' : 'Confirm Reject'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
