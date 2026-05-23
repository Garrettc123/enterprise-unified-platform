import { useEffect, useState } from 'react'
import { analyticsApi } from '../services/api'
import './AdminDashboard.css'

interface StatusBreakdown {
  status: string
  count: number
}

interface PriorityBreakdown {
  priority: string
  count: number
}

interface RecentActivity {
  action: string
  entity_type: string
  entity_id: number | null
  created_at: string | null
  username: string | null
}

interface AdminMetrics {
  total_users: number
  active_users: number
  total_organizations: number
  total_projects: number
  total_tasks: number
  completed_tasks: number
  completion_rate: number
  new_users_last_week: number
  new_projects_last_week: number
  project_status_breakdown: StatusBreakdown[]
  task_priority_breakdown: PriorityBreakdown[]
  task_status_breakdown: StatusBreakdown[]
  recent_activity: RecentActivity[]
}

const PRIORITY_COLORS: Record<string, string> = {
  critical: '#dc2626',
  high: '#ea580c',
  medium: '#ca8a04',
  low: '#16a34a',
}

const STATUS_COLORS: Record<string, string> = {
  active: '#2563eb',
  completed: '#16a34a',
  archived: '#6b7280',
  todo: '#6b7280',
  in_progress: '#2563eb',
  in_review: '#ca8a04',
  blocked: '#dc2626',
}

function AdminDashboard() {
  const [metrics, setMetrics] = useState<AdminMetrics | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchAdminData = async () => {
      const token = localStorage.getItem('access_token')
      if (!token) {
        setError('Authentication required')
        setIsLoading(false)
        return
      }

      try {
        const data = await analyticsApi.getAdminOverview(token)
        setMetrics(data)
      } catch (err) {
        setError('Failed to load admin analytics')
        console.error('Error fetching admin analytics:', err)
      } finally {
        setIsLoading(false)
      }
    }

    fetchAdminData()
  }, [])

  if (isLoading) {
    return <div className="loading">Loading admin dashboard...</div>
  }

  if (error) {
    return <div className="admin-error">{error}</div>
  }

  if (!metrics) {
    return <div className="admin-error">No data available</div>
  }

  const maxTaskStatus = Math.max(
    ...metrics.task_status_breakdown.map((s) => s.count),
    1
  )
  const maxProjectStatus = Math.max(
    ...metrics.project_status_breakdown.map((s) => s.count),
    1
  )
  const maxPriority = Math.max(
    ...metrics.task_priority_breakdown.map((p) => p.count),
    1
  )

  return (
    <div className="admin-dashboard">
      <div className="admin-header">
        <h1>⚙️ Admin Dashboard</h1>
        <p>System-wide analytics and management overview</p>
      </div>

      {/* Summary Metrics */}
      <div className="admin-metrics-grid">
        <div className="admin-metric-card">
          <div className="admin-metric-icon">👥</div>
          <div className="admin-metric-info">
            <h3>Total Users</h3>
            <p className="admin-metric-value">{metrics.total_users}</p>
            <p className="admin-metric-sub">
              {metrics.active_users} active · {metrics.new_users_last_week} new this week
            </p>
          </div>
        </div>

        <div className="admin-metric-card">
          <div className="admin-metric-icon">🏢</div>
          <div className="admin-metric-info">
            <h3>Organizations</h3>
            <p className="admin-metric-value">{metrics.total_organizations}</p>
            <p className="admin-metric-sub">Registered organizations</p>
          </div>
        </div>

        <div className="admin-metric-card">
          <div className="admin-metric-icon">📊</div>
          <div className="admin-metric-info">
            <h3>Projects</h3>
            <p className="admin-metric-value">{metrics.total_projects}</p>
            <p className="admin-metric-sub">{metrics.new_projects_last_week} new this week</p>
          </div>
        </div>

        <div className="admin-metric-card">
          <div className="admin-metric-icon">✅</div>
          <div className="admin-metric-info">
            <h3>Tasks</h3>
            <p className="admin-metric-value">{metrics.total_tasks}</p>
            <p className="admin-metric-sub">
              {metrics.completed_tasks} completed · {metrics.completion_rate}% rate
            </p>
          </div>
        </div>
      </div>

      {/* Completion Rate */}
      <div className="admin-section">
        <h2>Task Completion Rate</h2>
        <div className="completion-bar-container">
          <div className="completion-bar-bg">
            <div
              className="completion-bar-fill"
              style={{ width: `${metrics.completion_rate}%` }}
            />
          </div>
          <span className="completion-bar-label">{metrics.completion_rate}%</span>
        </div>
      </div>

      <div className="admin-charts-grid">
        {/* Project Status Breakdown */}
        <div className="admin-chart-card">
          <h2>Project Status</h2>
          <div className="chart-bars">
            {metrics.project_status_breakdown.length > 0 ? (
              metrics.project_status_breakdown.map((item) => (
                <div key={item.status} className="chart-bar-row">
                  <span className="chart-bar-label">{item.status}</span>
                  <div className="chart-bar-track">
                    <div
                      className="chart-bar-fill"
                      style={{
                        width: `${(item.count / maxProjectStatus) * 100}%`,
                        backgroundColor: STATUS_COLORS[item.status] || '#6b7280',
                      }}
                    />
                  </div>
                  <span className="chart-bar-value">{item.count}</span>
                </div>
              ))
            ) : (
              <p className="no-data">No project data available</p>
            )}
          </div>
        </div>

        {/* Task Status Breakdown */}
        <div className="admin-chart-card">
          <h2>Task Status</h2>
          <div className="chart-bars">
            {metrics.task_status_breakdown.length > 0 ? (
              metrics.task_status_breakdown.map((item) => (
                <div key={item.status} className="chart-bar-row">
                  <span className="chart-bar-label">{item.status}</span>
                  <div className="chart-bar-track">
                    <div
                      className="chart-bar-fill"
                      style={{
                        width: `${(item.count / maxTaskStatus) * 100}%`,
                        backgroundColor: STATUS_COLORS[item.status] || '#6b7280',
                      }}
                    />
                  </div>
                  <span className="chart-bar-value">{item.count}</span>
                </div>
              ))
            ) : (
              <p className="no-data">No task data available</p>
            )}
          </div>
        </div>

        {/* Task Priority Distribution */}
        <div className="admin-chart-card">
          <h2>Task Priority Distribution</h2>
          <div className="chart-bars">
            {metrics.task_priority_breakdown.length > 0 ? (
              metrics.task_priority_breakdown.map((item) => (
                <div key={item.priority} className="chart-bar-row">
                  <span className="chart-bar-label">{item.priority}</span>
                  <div className="chart-bar-track">
                    <div
                      className="chart-bar-fill"
                      style={{
                        width: `${(item.count / maxPriority) * 100}%`,
                        backgroundColor: PRIORITY_COLORS[item.priority] || '#6b7280',
                      }}
                    />
                  </div>
                  <span className="chart-bar-value">{item.count}</span>
                </div>
              ))
            ) : (
              <p className="no-data">No task data available</p>
            )}
          </div>
        </div>

        {/* Recent Activity */}
        <div className="admin-chart-card admin-activity-card">
          <h2>Recent Activity</h2>
          {metrics.recent_activity.length > 0 ? (
            <div className="activity-list">
              {metrics.recent_activity.map((activity, index) => (
                <div key={`${activity.action}-${activity.entity_type}-${activity.entity_id}-${activity.created_at || index}`} className="activity-item">
                  <div className="activity-details">
                    <span className="activity-user">{activity.username || 'System'}</span>
                    <span className="activity-action">{activity.action}</span>
                    <span className="activity-entity">
                      {activity.entity_type}
                      {activity.entity_id ? ` #${activity.entity_id}` : ''}
                    </span>
                  </div>
                  <span className="activity-time">
                    {activity.created_at
                      ? new Date(activity.created_at).toLocaleString()
                      : ''}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="no-data">No recent activity</p>
          )}
        </div>
      </div>
    </div>
  )
}

export default AdminDashboard
