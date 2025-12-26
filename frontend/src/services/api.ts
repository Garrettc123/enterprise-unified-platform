const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

// Auth API
export const authApi = {
  login: async (username: string, password: string) => {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ username, password }),
    })
    if (!response.ok) throw new Error('Login failed')
    return response.json()
  },

  register: async (data: any) => {
    const response = await fetch(`${API_BASE_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    if (!response.ok) throw new Error('Registration failed')
    return response.json()
  },

  getCurrentUser: async (token: string) => {
    const response = await fetch(`${API_BASE_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) throw new Error('Failed to fetch user')
    return response.json()
  },
}

// Projects API
export const projectsApi = {
  list: async (token: string, organizationId: number) => {
    const response = await fetch(
      `${API_BASE_URL}/projects?organization_id=${organizationId}`,
      { headers: { Authorization: `Bearer ${token}` } }
    )
    if (!response.ok) throw new Error('Failed to fetch projects')
    return response.json()
  },

  get: async (token: string, projectId: number) => {
    const response = await fetch(`${API_BASE_URL}/projects/${projectId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) throw new Error('Failed to fetch project')
    return response.json()
  },

  create: async (token: string, data: any) => {
    const response = await fetch(`${API_BASE_URL}/projects`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(data),
    })
    if (!response.ok) throw new Error('Failed to create project')
    return response.json()
  },
}

// Tasks API
export const tasksApi = {
  list: async (token: string, projectId: number) => {
    const response = await fetch(
      `${API_BASE_URL}/tasks?project_id=${projectId}`,
      { headers: { Authorization: `Bearer ${token}` } }
    )
    if (!response.ok) throw new Error('Failed to fetch tasks')
    return response.json()
  },

  get: async (token: string, taskId: number) => {
    const response = await fetch(`${API_BASE_URL}/tasks/${taskId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) throw new Error('Failed to fetch task')
    return response.json()
  },

  create: async (token: string, data: any) => {
    const response = await fetch(`${API_BASE_URL}/tasks`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(data),
    })
    if (!response.ok) throw new Error('Failed to create task')
    return response.json()
  },

  update: async (token: string, taskId: number, data: any) => {
    const response = await fetch(`${API_BASE_URL}/tasks/${taskId}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(data),
    })
    if (!response.ok) throw new Error('Failed to update task')
    return response.json()
  },
}

// Analytics API
export const analyticsApi = {
  getDashboardOverview: async (token: string, organizationId: number) => {
    const response = await fetch(
      `${API_BASE_URL}/analytics/dashboard/overview?organization_id=${organizationId}`,
      { headers: { Authorization: `Bearer ${token}` } }
    )
    if (!response.ok) throw new Error('Failed to fetch analytics')
    return response.json()
  },
}

// Notifications API
export const notificationsApi = {
  getNotifications: async (token: string) => {
    const response = await fetch(`${API_BASE_URL}/notifications`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) throw new Error('Failed to fetch notifications')
    return response.json()
  },

  markAsRead: async (token: string, notificationId: number) => {
    const response = await fetch(
      `${API_BASE_URL}/notifications/${notificationId}/read`,
      {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      }
    )
    if (!response.ok) throw new Error('Failed to mark notification as read')
  },
}
