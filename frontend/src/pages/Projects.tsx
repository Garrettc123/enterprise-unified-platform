import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { projectsApi } from '../services/api'
import toast from 'react-hot-toast'

interface Project {
  id: number
  name: string
  description: string | null
  status: string
  priority: string
  created_at: string
  updated_at: string
}

function Projects() {
  const [projects, setProjects] = useState<Project[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newProject, setNewProject] = useState({ name: '', description: '', organization_id: 1 })

  useEffect(() => {
    fetchProjects()
  }, [])

  const fetchProjects = async () => {
    const token = localStorage.getItem('access_token')
    if (!token) return

    try {
      const data = await projectsApi.list(token, 1)
      setProjects(data)
    } catch (error) {
      console.error('Error fetching projects:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault()
    const token = localStorage.getItem('access_token')
    if (!token) return

    try {
      await projectsApi.create(token, newProject)
      toast.success('Project created successfully!')
      setShowCreateForm(false)
      setNewProject({ name: '', description: '', organization_id: 1 })
      fetchProjects()
    } catch (error) {
      toast.error('Failed to create project')
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return '#10b981'
      case 'completed': return '#3b82f6'
      case 'archived': return '#6b7280'
      default: return '#9ca3af'
    }
  }

  const getPriorityLabel = (priority: string) => {
    switch (priority) {
      case 'critical': return '🔴'
      case 'high': return '🟠'
      case 'medium': return '🟡'
      case 'low': return '🟢'
      default: return '⚪'
    }
  }

  if (isLoading) {
    return <div className="loading">Loading projects...</div>
  }

  return (
    <div className="projects-page">
      <div className="projects-header">
        <div>
          <h1>Projects</h1>
          <p>Manage your team's projects</p>
        </div>
        <button className="btn-primary" onClick={() => setShowCreateForm(!showCreateForm)}>
          + New Project
        </button>
      </div>

      {showCreateForm && (
        <div className="create-form">
          <h3>Create New Project</h3>
          <form onSubmit={handleCreateProject}>
            <div className="form-group">
              <label htmlFor="project-name">Project Name</label>
              <input
                id="project-name"
                type="text"
                value={newProject.name}
                onChange={(e) => setNewProject({ ...newProject, name: e.target.value })}
                placeholder="Enter project name"
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="project-desc">Description</label>
              <textarea
                id="project-desc"
                value={newProject.description}
                onChange={(e) => setNewProject({ ...newProject, description: e.target.value })}
                placeholder="Enter project description"
              />
            </div>
            <div className="form-actions">
              <button type="submit" className="btn-primary">Create</button>
              <button type="button" className="btn-secondary" onClick={() => setShowCreateForm(false)}>
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="projects-grid">
        {projects.length === 0 ? (
          <div className="empty-state">
            <p>No projects yet. Create your first project to get started!</p>
          </div>
        ) : (
          projects.map((project) => (
            <Link to={`/projects/${project.id}`} key={project.id} className="project-card">
              <div className="project-card-header">
                <h3>{project.name}</h3>
                <span className="priority-badge">{getPriorityLabel(project.priority)}</span>
              </div>
              <p className="project-description">{project.description || 'No description'}</p>
              <div className="project-card-footer">
                <span className="status-badge" style={{ color: getStatusColor(project.status) }}>
                  {project.status}
                </span>
                <span className="date">{new Date(project.created_at).toLocaleDateString()}</span>
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  )
}

export default Projects
