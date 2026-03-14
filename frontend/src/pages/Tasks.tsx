import { useEffect, useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { tasksApi } from '../services/api'
import toast from 'react-hot-toast'

interface Task {
  id: number
  title: string
  description?: string
  status: string
  priority: string
  project_id: number
  due_date?: string
}

function Tasks() {
  const { user: _user } = useAuth()
  const [tasks, setTasks] = useState<Task[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [projectId] = useState(0)

  useEffect(() => {
    const fetchTasks = async () => {
      const token = localStorage.getItem('access_token')
      if (!token) return
      try {
        const data = await tasksApi.list(token, projectId)
        setTasks(data)
      } catch (error) {
        console.error('Error fetching tasks:', error)
        toast.error('Failed to load tasks')
      } finally {
        setIsLoading(false)
      }
    }
    fetchTasks()
  }, [projectId])

  const handleStatusChange = async (taskId: number, newStatus: string) => {
    const token = localStorage.getItem('access_token')
    if (!token) return
    try {
      await tasksApi.update(token, taskId, { status: newStatus })
      setTasks((prev) =>
        prev.map((task) => (task.id === taskId ? { ...task, status: newStatus } : task))
      )
      toast.success('Task updated!')
    } catch (error) {
      console.error('Error updating task:', error)
      toast.error('Failed to update task')
    }
  }

  if (isLoading) {
    return <div className="loading">Loading tasks...</div>
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Tasks</h1>
      </div>

      {tasks.length === 0 ? (
        <div className="empty-state">
          <p>No tasks found. Tasks will appear here once they are created in a project.</p>
        </div>
      ) : (
        <div className="tasks-list">
          {tasks.map((task) => (
            <div key={task.id} className="task-card">
              <div className="task-card-header">
                <h3>{task.title}</h3>
                <span className={`priority-badge priority-${task.priority}`}>
                  {task.priority}
                </span>
              </div>
              {task.description && <p className="task-description">{task.description}</p>}
              <div className="task-footer">
                <select
                  value={task.status}
                  onChange={(e) => handleStatusChange(task.id, e.target.value)}
                  className="status-select"
                >
                  <option value="todo">To Do</option>
                  <option value="in_progress">In Progress</option>
                  <option value="done">Done</option>
                </select>
                {task.due_date && (
                  <span className="due-date">
                    Due: {new Date(task.due_date).toLocaleDateString()}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default Tasks
