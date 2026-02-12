import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { projectsApi, tasksApi } from '../services/api'

interface Project {
  id: number
  name: string
  description: string | null
  status: string
  priority: string
  budget: number | null
  created_at: string
  updated_at: string
}

interface Task {
  id: number
  title: string
  description: string | null
  status: string
  priority: string
  assigned_to: number | null
  created_at: string
}

function ProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const [project, setProject] = useState<Project | null>(null)
  const [tasks, setTasks] = useState<Task[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      const token = localStorage.getItem('access_token')
      if (!token || !id) return

      try {
        const [projectData, tasksData] = await Promise.all([
          projectsApi.get(token, parseInt(id)),
          tasksApi.list(token, parseInt(id)),
        ])
        setProject(projectData)
        setTasks(tasksData)
      } catch (error) {
        console.error('Error fetching project details:', error)
      } finally {
        setIsLoading(false)
      }
    }

    fetchData()
  }, [id])

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'var(--success)'
      case 'in_progress': return 'var(--primary)'
      case 'in_review': return 'var(--warning)'
      case 'blocked': return 'var(--danger)'
      default: return 'var(--gray-500)'
    }
  }

  if (isLoading) {
    return <div className="loading">Loading project...</div>
  }

  if (!project) {
    return (
      <div className="not-found">
        <h2>Project not found</h2>
        <Link to="/projects">Back to Projects</Link>
      </div>
    )
  }

  const tasksByStatus = {
    todo: tasks.filter((t) => t.status === 'todo'),
    in_progress: tasks.filter((t) => t.status === 'in_progress'),
    in_review: tasks.filter((t) => t.status === 'in_review'),
    completed: tasks.filter((t) => t.status === 'completed'),
  }

  return (
    <div className="project-detail">
      <div className="project-detail-header">
        <Link to="/projects" className="back-link">← Back to Projects</Link>
        <h1>{project.name}</h1>
        <p>{project.description || 'No description'}</p>
        <div className="project-meta">
          <span className="meta-item">Status: {project.status}</span>
          <span className="meta-item">Priority: {project.priority}</span>
          {project.budget && <span className="meta-item">Budget: ${project.budget.toLocaleString()}</span>}
        </div>
      </div>

      <div className="task-board">
        {Object.entries(tasksByStatus).map(([status, statusTasks]) => (
          <div key={status} className="task-column">
            <h3 className="column-header">
              {status.replace('_', ' ').toUpperCase()} ({statusTasks.length})
            </h3>
            {statusTasks.map((task) => (
              <div key={task.id} className="task-card">
                <h4>{task.title}</h4>
                <p>{task.description || 'No description'}</p>
                <div className="task-card-footer">
                  <span className="task-status" style={{ color: getStatusColor(task.status) }}>
                    {task.status}
                  </span>
                  <span className="task-priority">{task.priority}</span>
                </div>
              </div>
            ))}
            {statusTasks.length === 0 && (
              <div className="empty-column">No tasks</div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export default ProjectDetail
