import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { projectsApi, tasksApi } from '../services/api'
import toast from 'react-hot-toast'

interface Project {
  id: number
  name: string
  description?: string
  status: string
  created_at: string
}

interface Task {
  id: number
  title: string
  description?: string
  status: string
  priority: string
  due_date?: string
}

function ProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const [project, setProject] = useState<Project | null>(null)
  const [tasks, setTasks] = useState<Task[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showCreateTask, setShowCreateTask] = useState(false)
  const [newTaskTitle, setNewTaskTitle] = useState('')
  const [newTaskDescription, setNewTaskDescription] = useState('')

  useEffect(() => {
    const fetchData = async () => {
      const token = localStorage.getItem('access_token')
      if (!token || !id) return
      try {
        const [projectData, tasksData] = await Promise.all([
          projectsApi.get(token, Number(id)),
          tasksApi.list(token, Number(id)),
        ])
        setProject(projectData)
        setTasks(tasksData)
      } catch (error) {
        console.error('Error fetching project:', error)
        toast.error('Failed to load project')
      } finally {
        setIsLoading(false)
      }
    }
    fetchData()
  }, [id])

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault()
    const token = localStorage.getItem('access_token')
    if (!token || !id) return
    try {
      const created = await tasksApi.create(token, {
        title: newTaskTitle,
        description: newTaskDescription,
        project_id: Number(id),
        status: 'todo',
        priority: 'medium',
      })
      setTasks((prev) => [...prev, created])
      setNewTaskTitle('')
      setNewTaskDescription('')
      setShowCreateTask(false)
      toast.success('Task created!')
    } catch (error) {
      console.error('Error creating task:', error)
      toast.error('Failed to create task')
    }
  }

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
    return <div className="loading">Loading project...</div>
  }

  if (!project) {
    return (
      <div className="page-container">
        <p>Project not found.</p>
        <Link to="/projects" className="btn-secondary">
          Back to Projects
        </Link>
      </div>
    )
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <Link to="/projects" className="back-link">
            ← Back to Projects
          </Link>
          <h1>{project.name}</h1>
          {project.description && <p className="project-description">{project.description}</p>}
          <span className={`status-badge status-${project.status}`}>{project.status}</span>
        </div>
        <button className="btn-primary" onClick={() => setShowCreateTask(!showCreateTask)}>
          + New Task
        </button>
      </div>

      {showCreateTask && (
        <div className="create-form">
          <h2>Create New Task</h2>
          <form onSubmit={handleCreateTask}>
            <div className="form-group">
              <label htmlFor="task-title">Task Title</label>
              <input
                id="task-title"
                type="text"
                value={newTaskTitle}
                onChange={(e) => setNewTaskTitle(e.target.value)}
                placeholder="Enter task title"
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="task-description">Description</label>
              <textarea
                id="task-description"
                value={newTaskDescription}
                onChange={(e) => setNewTaskDescription(e.target.value)}
                placeholder="Enter task description"
                rows={3}
              />
            </div>
            <div className="form-actions">
              <button type="submit" className="btn-primary">Create Task</button>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setShowCreateTask(false)}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="tasks-section">
        <h2>Tasks ({tasks.length})</h2>
        {tasks.length === 0 ? (
          <div className="empty-state">
            <p>No tasks yet. Add your first task above.</p>
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
    </div>
  )
}

export default ProjectDetail
