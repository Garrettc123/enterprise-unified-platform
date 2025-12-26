import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useNotifications } from '../hooks/useNotifications'
import './Navbar.css'

function Navbar() {
  const { user, logout } = useAuth()
  const { unreadCount } = useNotifications()
  const [showDropdown, setShowDropdown] = useState(false)
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <Link to="/dashboard">🚀 Enterprise Platform</Link>
      </div>
      <div className="navbar-menu">
        <Link to="/dashboard" className="nav-link">Dashboard</Link>
        <Link to="/projects" className="nav-link">Projects</Link>
        <Link to="/tasks" className="nav-link">Tasks</Link>
      </div>
      <div className="navbar-end">
        <Link to="/notifications" className="nav-link notification-link">
          🔔 {unreadCount > 0 && <span className="badge">{unreadCount}</span>}
        </Link>
        <div className="user-menu">
          <button
            className="user-button"
            onClick={() => setShowDropdown(!showDropdown)}
          >
            {user?.avatar_url ? (
              <img src={user.avatar_url} alt={user.username} />
            ) : (
              <span>{user?.username?.charAt(0)?.toUpperCase()}</span>
            )}
          </button>
          {showDropdown && (
            <div className="dropdown-menu">
              <Link to="/profile" className="dropdown-item">Profile</Link>
              <Link to="/settings" className="dropdown-item">Settings</Link>
              <hr />
              <button onClick={handleLogout} className="dropdown-item logout">
                Logout
              </button>
            </div>
          )}
        </div>
      </div>
    </nav>
  )
}

export default Navbar
