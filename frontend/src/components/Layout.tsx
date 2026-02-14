import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Layout() {
  const { user, logout } = useAuth()

  const navItems = [
    { to: '/requests', label: 'Requests' },
    { to: '/requests/new', label: 'New Request' },
    { to: '/inbox', label: 'Approver Inbox', roles: ['approver', 'admin'] },
    { to: '/policies', label: 'Policies', roles: ['admin'] },
    { to: '/reports', label: 'Reports' },
  ]

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <h1>Procurement</h1>
          <span>Platform</span>
        </div>
        <nav className="sidebar-nav">
          {navItems
            .filter((item) => !item.roles || item.roles.includes(user?.role || ''))
            .map((item) => (
              <NavLink key={item.to} to={item.to} className={({ isActive }) => (isActive ? 'active' : '')}>
                {item.label}
              </NavLink>
            ))}
        </nav>
        <div className="sidebar-footer">
          <div className="user-info">{user?.fullName}</div>
          <div className="user-role">{user?.role}</div>
          <button className="btn btn-outline btn-sm" onClick={logout} style={{ marginTop: '0.75rem', width: '100%' }}>
            Sign Out
          </button>
        </div>
      </aside>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  )
}
