import { useEffect, useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { analyticsApi, organizationsApi } from '../services/api'
import DashboardCharts from '../components/DashboardCharts'
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
  const [organizationId, setOrganizationId] = useState<number | null>(null)
  const [organizations, setOrganizations] = useState<Array<{ id: number; name: string }>>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    const loadOrganizations = async () => {
      const token = localStorage.getItem('access_token')
      if (!token) {
        if (active) {
          setError('Authentication required')
          setIsLoading(false)
        }
        return
      }
      try {
        const available = await organizationsApi.list(token)
        if (active) {
          setOrganizations(available)
          setOrganizationId(available.length > 0 ? available[0].id : null)
          if (available.length === 0) setIsLoading(false)
        }
      } catch {
        if (active) {
          setError('Unable to verify your organization access')
          setIsLoading(false)
        }
      }
    }
    void loadOrganizations()
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (organizationId === null) return
    let active = true
    const fetchMetrics = async () => {
      setIsLoading(true)
      const token = localStorage.getItem('access_token')
      if (!token) {
        if (active) {
          setError('Authentication required')
          setIsLoading(false)
        }
        return
      }

      try {
        const data = await analyticsApi.getDashboardOverview(token, organizationId)
        if (active) {
          setMetrics(data)
          setError(null)
        }
      } catch {
        if (active) {
          setMetrics(null)
          setError('Verified dashboard data is unavailable for this organization')
        }
      } finally {
        if (active) setIsLoading(false)
      }
    }
    void fetchMetrics()
    return () => { active = false }
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

      <div className="organization-picker">
        <label htmlFor="organization">Organization: </label>
        <select
          id="organization"
          value={organizationId ?? ''}
          onChange={(event) => setOrganizationId(Number(event.target.value))}
          disabled={organizations.length === 0}
        >
          {organizations.map((organization) => (
            <option key={organization.id} value={organization.id}>{organization.name}</option>
          ))}
        </select>
      </div>
      {error && <p role="alert">{error}</p>}
      {organizations.length === 0 && !error && <p>No authorized organizations found.</p>}

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

      {metrics && organizationId !== null && <DashboardCharts organizationId={organizationId} />}
    </div>
  )
}

export default Dashboard
