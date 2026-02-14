import { useState } from 'react'
import { useMutation } from '@apollo/client'
import { useNavigate } from 'react-router-dom'
import { CREATE_PURCHASE_REQUEST, SUBMIT_REQUEST } from '../graphql/queries'

const CATEGORIES = ['IT', 'Office Supplies', 'Marketing', 'Facilities', 'Professional Services']
const COST_CENTERS = ['ENG-001', 'MKT-002', 'OPS-003', 'HR-004']

export default function CreateRequest() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    title: '',
    description: '',
    vendor: '',
    amount: '',
    category: CATEGORIES[0],
    costCenter: COST_CENTERS[0],
  })
  const [error, setError] = useState('')

  const [createRequest, { loading: creating }] = useMutation(CREATE_PURCHASE_REQUEST)
  const [submitRequest, { loading: submitting }] = useMutation(SUBMIT_REQUEST)

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value })
  }

  const handleSave = async (andSubmit: boolean) => {
    setError('')
    try {
      const { data } = await createRequest({
        variables: {
          input: {
            title: form.title,
            description: form.description || null,
            vendor: form.vendor,
            amount: parseFloat(form.amount),
            category: form.category,
            costCenter: form.costCenter,
          },
        },
      })
      const id = data.createPurchaseRequest.id
      if (andSubmit) {
        await submitRequest({ variables: { id } })
      }
      navigate(`/requests/${id}`)
    } catch (e: any) {
      setError(e.message)
    }
  }

  const valid = form.title && form.vendor && form.amount && parseFloat(form.amount) > 0

  return (
    <>
      <div className="page-header">
        <h2>Create Purchase Request</h2>
      </div>

      <div className="card">
        <div className="card-body">
          {error && <div className="alert alert-error">{error}</div>}

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="title">Title</label>
              <input id="title" name="title" className="form-control" value={form.title} onChange={handleChange} placeholder="e.g., New Laptops" required />
            </div>
            <div className="form-group">
              <label htmlFor="vendor">Vendor</label>
              <input id="vendor" name="vendor" className="form-control" value={form.vendor} onChange={handleChange} placeholder="e.g., Dell" required />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="amount">Amount (USD)</label>
              <input id="amount" name="amount" type="number" step="0.01" min="0" className="form-control" value={form.amount} onChange={handleChange} placeholder="0.00" required />
            </div>
            <div className="form-group">
              <label htmlFor="category">Category</label>
              <select id="category" name="category" className="form-control" value={form.category} onChange={handleChange}>
                {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="costCenter">Cost Center</label>
            <select id="costCenter" name="costCenter" className="form-control" value={form.costCenter} onChange={handleChange}>
              {COST_CENTERS.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="description">Description</label>
            <textarea id="description" name="description" className="form-control" value={form.description} onChange={handleChange} placeholder="Additional details..." />
          </div>

          <div className="btn-group" style={{ marginTop: '1rem' }}>
            <button className="btn btn-outline" disabled={!valid || creating || submitting} onClick={() => handleSave(false)}>
              {creating ? 'Saving...' : 'Save as Draft'}
            </button>
            <button className="btn btn-primary" disabled={!valid || creating || submitting} onClick={() => handleSave(true)}>
              {submitting ? 'Submitting...' : 'Save & Submit'}
            </button>
          </div>
        </div>
      </div>
    </>
  )
}
