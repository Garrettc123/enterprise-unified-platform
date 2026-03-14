import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { projectsApi } from '../services/api'
import toast from 'react-hot-toast'

interface Project {
  id: number
  name: string
  description?: string
  status: string
  created_at: string
}

function Projects() {
  const { user: _user } = useAuth()
  const [projects, setProjects] = useState<Project[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')
  const [newProjectDescription, setNewProjectDescription] = useState('')
  const [organizationId] = useState(1)

  useEffect(() => {
    const fetchProjects = async () => {
      const token = localStorage.getItem('access_token')
      if (!token) return
      try {
        const data = await projectsApi.list(token, organizationId)
        setProjects(data)
      } catch (error) {
        console.error('Error fetching projects:', error)
        toast.error('Failed to load projects')
      } finally {
        setIsLoading(false)
      }
    }
    fetchProjects()
  }, [organizationId])

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault()
    const token = localStorage.getItem('access_token')
    if (!token) return
    try {
      const created = await projectsApi.create(token, {
        name: newProjectName,
        description: newProjectDescription,
        organization_id: organizationId,
      })
      setProjects((prev) => [...prev, created])
      setNewProjectName('')
      setNewProjectDescription('')
      setShowCreateForm(false)
      toast.success('Project created!')
    } catch (error) {
      console.error('Error creating project:', error)
      toast.error('Failed to create project')
    }
  }

  if (isLoading) {
    return <div className="loading">Loading projects...</div>
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Projects</h1>
        <button className="btn-primary" onClick={() => setShowCreateForm(!showCreateForm)}>
          + New Project
        </button>
      </div>

      {showCreateForm && (
        <div className="create-form">
          <h2>Create New Project</h2>
          <form onSubmit={handleCreateProject}>
            <div className="form-group">
              <label htmlFor="project-name">Project Name</label>
              <input
                id="project-name"
                type="text"
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                placeholder="Enter project name"
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="project-description">Description</label>
              <textarea
                id="project-description"
                value={newProjectDescription}
                onChange={(e) => setNewProjectDescription(e.target.value)}
                placeholder="Enter project description"
                rows={3}
              />
            </div>
            <div className="form-actions">
              <button type="submit" className="btn-primary">Create Project</button>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setShowCreateForm(false)}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {projects.length === 0 ? (
        <div className="empty-state">
          <p>No projects yet. Create your first project to get started.</p>
        </div>
      ) : (
        <div className="projects-grid">
          {projects.map((project) => (
            <Link key={project.id} to={`/projects/${project.id}`} className="project-card">
              <div className="project-card-header">
                <h3>{project.name}</h3>
                <span className={`status-badge status-${project.status}`}>{project.status}</span>
              </div>
              {project.description && (
                <p className="project-description">{project.description}</p>
              )}
              <p className="project-date">
                Created: {new Date(project.created_at).toLocaleDateString()}
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

export default Projects
