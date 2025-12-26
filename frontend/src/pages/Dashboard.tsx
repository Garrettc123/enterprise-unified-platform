import { useEffect, useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { analyticsApi } from '../services/api'
import './Dashboard.css'

interface DashboardMetrics {
  total_projects: number
  active_projects: number
  total_tasks: number
  completed_tasks: number
  completion_rate: number
  team_size: number
}

function Dashboard() {
  const { user } = useAuth()
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [organizationId] = useState(1) // Default org ID

  useEffect(() => {
    const fetchMetrics = async () => {
      const token = localStorage.getItem('access_token')
      if (!token) return

      try {
        const data = await analyticsApi.getDashboardOverview(token, organizationId)
        setMetrics(data)
      } catch (error) {
        console.error('Error fetching dashboard:', error)
      } finally {
        setIsLoading(false)
      }
    }

    fetchMetrics()
  }, [organizationId])

  if (isLoading) {
    return <div className="loading">Loading dashboard...</div>
  }

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1>Welcome, {user?.full_name || user?.username}! 👋</h1>
        <p>Here's your project overview</p>
      </div>

      {metrics && (
        <div className="metrics-grid">
          <div className="metric-card">
            <div className="metric-icon">📊</div>
            <h3>Total Projects</h3>
            <p className="metric-value">{metrics.total_projects}</p>
            <p className="metric-label">{metrics.active_projects} active</p>
          </div>

          <div className="metric-card">
            <div className="metric-icon">✅</div>
            <h3>Tasks Completed</h3>
            <p className="metric-value">{metrics.completed_tasks}</p>
            <p className="metric-label">{metrics.completion_rate.toFixed(0)}% completion</p>
          </div>

          <div className="metric-card">
            <div className="metric-icon">👥</div>
            <h3>Team Members</h3>
            <p className="metric-value">{metrics.team_size}</p>
            <p className="metric-label">Active users</p>
          </div>

          <div className="metric-card">
            <div className="metric-icon">📋</div>
            <h3>Total Tasks</h3>
            <p className="metric-value">{metrics.total_tasks}</p>
            <p className="metric-label">Across all projects</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default Dashboard
