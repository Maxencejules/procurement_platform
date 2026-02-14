import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import Layout from './components/Layout'
import Login from './pages/Login'
import RequestList from './pages/RequestList'
import CreateRequest from './pages/CreateRequest'
import RequestDetail from './pages/RequestDetail'
import ApproverInbox from './pages/ApproverInbox'
import PolicyEditor from './pages/PolicyEditor'
import Reports from './pages/Reports'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="loading">Loading...</div>
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuth()
  if (user?.role !== 'admin') return <Navigate to="/requests" replace />
  return <>{children}</>
}

export default function App() {
  const { user, loading } = useAuth()

  if (loading) return <div className="loading">Loading...</div>

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={user ? <Navigate to="/requests" replace /> : <Login />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/requests" replace />} />
          <Route path="requests" element={<RequestList />} />
          <Route path="requests/new" element={<CreateRequest />} />
          <Route path="requests/:id" element={<RequestDetail />} />
          <Route path="inbox" element={<ApproverInbox />} />
          <Route path="policies" element={<AdminRoute><PolicyEditor /></AdminRoute>} />
          <Route path="reports" element={<Reports />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
