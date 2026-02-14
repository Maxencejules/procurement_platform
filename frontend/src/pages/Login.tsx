import { useState } from 'react'
import { useAuth } from '../context/AuthContext'

export default function Login() {
  const { login, error } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      await login(email, password)
    } catch {
      // error is set in context
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-wrapper">
      <div className="card login-card">
        <h1>Procurement Platform</h1>
        <p>Sign in to your account</p>
        {error && <div className="alert alert-error">{error}</div>}
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              className="form-control"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@acme.com"
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              className="form-control"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              required
            />
          </div>
          <button type="submit" className="btn btn-primary" disabled={loading} style={{ width: '100%' }}>
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
        <div style={{ marginTop: '1.5rem', fontSize: '0.8125rem', color: 'var(--gray-500)' }}>
          <strong>Demo accounts:</strong>
          <br />
          admin@acme.com / admin123
          <br />
          approver@acme.com / approver123
          <br />
          requester@acme.com / requester123
        </div>
      </div>
    </div>
  )
}
