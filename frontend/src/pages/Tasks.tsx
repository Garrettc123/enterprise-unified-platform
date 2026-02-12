import { useEffect, useState } from 'react'
import { tasksApi } from '../services/api'
import toast from 'react-hot-toast'

interface Task {
  id: number
  title: string
  description: string | null
  status: string
  priority: string
  project_id: number
  assigned_to: number | null
  due_date: string | null
  created_at: string
}

function Tasks() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [filterStatus, setFilterStatus] = useState<string>('')

  useEffect(() => {
    fetchTasks()
  }, [])

  const fetchTasks = async () => {
    const token = localStorage.getItem('access_token')
    if (!token) return

    try {
      const data = await tasksApi.list(token, 1)
      setTasks(data)
    } catch (error) {
      console.error('Error fetching tasks:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleStatusChange = async (taskId: number, newStatus: string) => {
    const token = localStorage.getItem('access_token')
    if (!token) return

    try {
      await tasksApi.update(token, taskId, { status: newStatus })
      toast.success('Task updated!')
      fetchTasks()
    } catch (error) {
      toast.error('Failed to update task')
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'var(--success)'
      case 'in_progress': return 'var(--primary)'
      case 'in_review': return 'var(--warning)'
      case 'blocked': return 'var(--danger)'
      default: return 'var(--gray-500)'
    }
  }

  const getPriorityLabel = (priority: string) => {
    switch (priority) {
      case 'critical': return '🔴 Critical'
      case 'high': return '🟠 High'
      case 'medium': return '🟡 Medium'
      case 'low': return '🟢 Low'
      default: return '⚪ None'
    }
  }

  const filteredTasks = filterStatus
    ? tasks.filter((t) => t.status === filterStatus)
    : tasks

  if (isLoading) {
    return <div className="loading">Loading tasks...</div>
  }

  return (
    <div className="tasks-page">
      <div className="tasks-header">
        <div>
          <h1>Tasks</h1>
          <p>Track and manage all your tasks</p>
        </div>
      </div>

      <div className="tasks-filters">
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="filter-select"
        >
          <option value="">All Statuses</option>
          <option value="todo">To Do</option>
          <option value="in_progress">In Progress</option>
          <option value="in_review">In Review</option>
          <option value="completed">Completed</option>
          <option value="blocked">Blocked</option>
        </select>
      </div>

      <div className="tasks-list">
        {filteredTasks.length === 0 ? (
          <div className="empty-state">
            <p>No tasks found.</p>
          </div>
        ) : (
          filteredTasks.map((task) => (
            <div key={task.id} className="task-row">
              <div className="task-info">
                <h3>{task.title}</h3>
                <p>{task.description || 'No description'}</p>
              </div>
              <div className="task-meta">
                <span className="priority">{getPriorityLabel(task.priority)}</span>
                <select
                  value={task.status}
                  onChange={(e) => handleStatusChange(task.id, e.target.value)}
                  className="status-select"
                  style={{ color: getStatusColor(task.status) }}
                >
                  <option value="todo">To Do</option>
                  <option value="in_progress">In Progress</option>
                  <option value="in_review">In Review</option>
                  <option value="completed">Completed</option>
                  <option value="blocked">Blocked</option>
                </select>
                {task.due_date && (
                  <span className="due-date">
                    Due: {new Date(task.due_date).toLocaleDateString()}
                  </span>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default Tasks
