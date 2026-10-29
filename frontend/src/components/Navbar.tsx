import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import './Navbar.css'

function Navbar() {
  const { user, logout } = useAuth()
  const [showDropdown, setShowDropdown] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const navItems = [
    { to: '/dashboard', label: 'Overview' },
    { to: '/projects', label: 'Projects' },
    { to: '/tasks', label: 'Tasks' },
    { to: '/admin', label: 'Admin' },
  ]

  return (
    <nav className="navbar" aria-label="Main navigation">
      <div className="navbar-brand">
        <Link to="/dashboard">
          <span className="brand-mark" aria-hidden="true">G</span>
          <span>Garcar Enterprise</span>
        </Link>
      </div>

      <div className="navbar-menu">
        {navItems.map((item) => (
          <Link
            key={item.to}
            to={item.to}
            className={`nav-link${location.pathname === item.to ? ' active' : ''}`}
            aria-current={location.pathname === item.to ? 'page' : undefined}
          >
            {item.label}
          </Link>
        ))}
      </div>

      <div className="navbar-end">
        <div className="user-menu">
          <button
            className="user-button"
            type="button"
            aria-label="Open account menu"
            aria-expanded={showDropdown}
            onClick={() => setShowDropdown(!showDropdown)}
          >
            {user?.avatar_url ? (
              <img src={user.avatar_url} alt="" />
            ) : (
              <span>{user?.username?.charAt(0)?.toUpperCase() || 'G'}</span>
            )}
          </button>
          {showDropdown && (
            <div className="dropdown-menu">
              <button type="button" onClick={handleLogout} className="dropdown-item logout">
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </nav>
  )
}

export default Navbar
