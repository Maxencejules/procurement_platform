import { useState } from 'react'
import { useQuery, useMutation } from '@apollo/client'
import {
  GET_APPROVAL_POLICIES, GET_USERS, CREATE_APPROVAL_POLICY,
  UPDATE_APPROVAL_POLICY, DELETE_APPROVAL_POLICY,
} from '../graphql/queries'

interface RuleForm {
  field: string
  operator: string
  value: string
}

interface PolicyForm {
  name: string
  description: string
  approverId: string
  priority: number
  rules: RuleForm[]
}

const EMPTY_POLICY: PolicyForm = {
  name: '', description: '', approverId: '', priority: 0, rules: [],
}

export default function PolicyEditor() {
  const { data, loading, refetch } = useQuery(GET_APPROVAL_POLICIES)
  const { data: usersData } = useQuery(GET_USERS)
  const [createPolicy] = useMutation(CREATE_APPROVAL_POLICY)
  const [updatePolicy] = useMutation(UPDATE_APPROVAL_POLICY)
  const [deletePolicy] = useMutation(DELETE_APPROVAL_POLICY)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<PolicyForm>(EMPTY_POLICY)
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)

  const policies = data?.approvalPolicies || []
  const approvers = (usersData?.users || []).filter((u: any) => u.role === 'approver' || u.role === 'admin')

  const openCreate = () => {
    setEditingId(null)
    setForm(EMPTY_POLICY)
    setShowForm(true)
  }

  const openEdit = (p: any) => {
    setEditingId(p.id)
    setForm({
      name: p.name,
      description: p.description || '',
      approverId: p.approverId,
      priority: p.priority,
      rules: p.rules.map((r: any) => ({ field: r.field, operator: r.operator, value: r.value })),
    })
    setShowForm(true)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      if (editingId) {
        await updatePolicy({
          variables: {
            id: editingId,
            input: {
              name: form.name,
              description: form.description || null,
              approverId: form.approverId,
              priority: form.priority,
              rules: form.rules,
            },
          },
        })
      } else {
        await createPolicy({
          variables: {
            input: {
              name: form.name,
              description: form.description || null,
              approverId: form.approverId,
              priority: form.priority,
              rules: form.rules,
            },
          },
        })
      }
      setShowForm(false)
      refetch()
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this policy?')) return
    await deletePolicy({ variables: { id } })
    refetch()
  }

  const addRule = () => {
    setForm({ ...form, rules: [...form.rules, { field: 'amount', operator: 'gte', value: '' }] })
  }

  const removeRule = (i: number) => {
    setForm({ ...form, rules: form.rules.filter((_, idx) => idx !== i) })
  }

  const updateRule = (i: number, key: keyof RuleForm, value: string) => {
    const rules = [...form.rules]
    rules[i] = { ...rules[i], [key]: value }
    setForm({ ...form, rules })
  }

  return (
    <>
      <div className="page-header">
        <h2>Approval Policies</h2>
        <button className="btn btn-primary" onClick={openCreate}>New Policy</button>
      </div>

      <div className="card">
        {loading ? (
          <div className="loading">Loading...</div>
        ) : policies.length === 0 ? (
          <div className="empty-state"><p>No policies configured.</p></div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Approver</th>
                  <th>Priority</th>
                  <th>Rules</th>
                  <th>Active</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {policies.map((p: any) => (
                  <tr key={p.id}>
                    <td style={{ fontWeight: 500 }}>{p.name}</td>
                    <td>{p.approver?.fullName}</td>
                    <td>{p.priority}</td>
                    <td>
                      {p.rules.map((r: any, i: number) => (
                        <span key={i} className="badge badge-draft" style={{ marginRight: '0.25rem' }}>
                          {r.field} {r.operator} {r.value}
                        </span>
                      ))}
                      {p.rules.length === 0 && <span style={{ color: 'var(--gray-400)' }}>No rules (matches all)</span>}
                    </td>
                    <td>{p.isActive ? 'Yes' : 'No'}</td>
                    <td>
                      <div className="btn-group">
                        <button className="btn btn-outline btn-sm" onClick={() => openEdit(p)}>Edit</button>
                        <button className="btn btn-danger btn-sm" onClick={() => handleDelete(p.id)}>Delete</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showForm && (
        <div className="modal-overlay" onClick={() => setShowForm(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{editingId ? 'Edit' : 'Create'} Policy</h3>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>Name</label>
                <input className="form-control" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </div>
              <div className="form-group">
                <label>Description</label>
                <textarea className="form-control" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Approver</label>
                  <select className="form-control" value={form.approverId} onChange={(e) => setForm({ ...form, approverId: e.target.value })}>
                    <option value="">Select approver</option>
                    {approvers.map((u: any) => <option key={u.id} value={u.id}>{u.fullName}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label>Priority</label>
                  <input type="number" className="form-control" value={form.priority} onChange={(e) => setForm({ ...form, priority: parseInt(e.target.value) || 0 })} />
                </div>
              </div>

              <div style={{ marginTop: '1rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <label style={{ fontWeight: 600, fontSize: '0.875rem' }}>Rules (all must match)</label>
                  <button className="btn btn-outline btn-sm" onClick={addRule}>Add Rule</button>
                </div>
                {form.rules.map((rule, i) => (
                  <div key={i} className="rule-row">
                    <select className="form-control" value={rule.field} onChange={(e) => updateRule(i, 'field', e.target.value)}>
                      <option value="amount">Amount</option>
                      <option value="category">Category</option>
                      <option value="cost_center">Cost Center</option>
                    </select>
                    <select className="form-control" value={rule.operator} onChange={(e) => updateRule(i, 'operator', e.target.value)}>
                      <option value="gt">Greater than</option>
                      <option value="gte">Greater or equal</option>
                      <option value="lt">Less than</option>
                      <option value="lte">Less or equal</option>
                      <option value="eq">Equals</option>
                      <option value="in">In (comma-separated)</option>
                    </select>
                    <input className="form-control" value={rule.value} onChange={(e) => updateRule(i, 'value', e.target.value)} placeholder="Value" />
                    <button className="btn btn-danger btn-sm" onClick={() => removeRule(i)}>X</button>
                  </div>
                ))}
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setShowForm(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleSave} disabled={saving || !form.name || !form.approverId}>
                {saving ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
