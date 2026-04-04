import { useEffect, useState } from 'react'
import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  LineChart, Line,
} from 'recharts'
import { analyticsApi } from '../services/api'
import './DashboardCharts.css'

interface ProjectStatus {
  status: string
  count: number
}

interface TaskPriority {
  priority: string
  count: number
}

interface TaskTrend {
  date: string
  completed_count: number
}

interface TeamWorkload {
  user: string
  assigned_tasks: number
}

const STATUS_COLORS: Record<string, string> = {
  active: '#3b82f6',
  completed: '#10b981',
  on_hold: '#f59e0b',
  cancelled: '#ef4444',
  planning: '#6366f1',
}

const PRIORITY_COLORS: Record<string, string> = {
  critical: '#ef4444',
  high: '#f59e0b',
  medium: '#3b82f6',
  low: '#10b981',
}

function DashboardCharts({ organizationId }: { organizationId: number }) {
  const [projectStatus, setProjectStatus] = useState<ProjectStatus[]>([])
  const [taskPriority, setTaskPriority] = useState<TaskPriority[]>([])
  const [taskTrend, setTaskTrend] = useState<TaskTrend[]>([])
  const [teamWorkload, setTeamWorkload] = useState<TeamWorkload[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchChartData = async () => {
      const token = localStorage.getItem('access_token')
      if (!token) return

      try {
        const [statusData, priorityData, trendData, workloadData] = await Promise.all([
          analyticsApi.getProjectStatusBreakdown(token, organizationId),
          analyticsApi.getTaskPriorityDistribution(token, organizationId),
          analyticsApi.getTaskStatusTrend(token, organizationId),
          analyticsApi.getTeamWorkload(token, organizationId),
        ])
        setProjectStatus(statusData)
        setTaskPriority(priorityData)
        setTaskTrend(trendData)
        setTeamWorkload(workloadData)
      } catch (error) {
        console.error('Error fetching chart data:', error)
      } finally {
        setIsLoading(false)
      }
    }

    fetchChartData()
  }, [organizationId])

  if (isLoading) {
    return <div className="charts-loading">Loading charts...</div>
  }

  return (
    <div className="dashboard-charts">
      <h2 className="charts-title">Analytics</h2>
      <div className="charts-grid">
        {/* Project Status Breakdown */}
        <div className="chart-card">
          <h3>Project Status</h3>
          {projectStatus.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie
                  data={projectStatus}
                  dataKey="count"
                  nameKey="status"
                  cx="50%"
                  cy="50%"
                  outerRadius={90}
                  label={({ status, count }) => `${status} (${count})`}
                >
                  {projectStatus.map((entry) => (
                    <Cell
                      key={entry.status}
                      fill={STATUS_COLORS[entry.status] || '#9ca3af'}
                    />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="chart-empty">No project data available</p>
          )}
        </div>

        {/* Task Priority Distribution */}
        <div className="chart-card">
          <h3>Task Priority Distribution</h3>
          {taskPriority.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={taskPriority}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="priority" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" name="Tasks">
                  {taskPriority.map((entry) => (
                    <Cell
                      key={entry.priority}
                      fill={PRIORITY_COLORS[entry.priority] || '#9ca3af'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="chart-empty">No task data available</p>
          )}
        </div>

        {/* Task Completion Trend */}
        <div className="chart-card">
          <h3>Task Completion Trend</h3>
          {taskTrend.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={taskTrend}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="completed_count"
                  name="Completed"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={{ r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="chart-empty">No trend data available</p>
          )}
        </div>

        {/* Team Workload */}
        <div className="chart-card">
          <h3>Team Workload</h3>
          {teamWorkload.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={teamWorkload} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" allowDecimals={false} />
                <YAxis type="category" dataKey="user" width={100} />
                <Tooltip />
                <Bar dataKey="assigned_tasks" name="Assigned Tasks" fill="#6366f1" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="chart-empty">No workload data available</p>
          )}
        </div>
      </div>
    </div>
  )
}

export default DashboardCharts
