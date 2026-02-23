import { apiClient } from './apiClient'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

// Auth API
export const authApi = {
  login: async (username: string, password: string) => {
    return apiClient.request('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ username, password }),
    })
  },

  register: async (data: any) => {
    return apiClient.request('/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: data,
    })
  },

  getCurrentUser: async (token: string) => {
    return apiClient.get('/auth/me', token)
  },
}

// Projects API
export const projectsApi = {
  list: async (token: string, organizationId: number) => {
    return apiClient.get('/projects', token, { organization_id: organizationId })
  },

  get: async (token: string, projectId: number) => {
    return apiClient.get(`/projects/${projectId}`, token)
  },

  create: async (token: string, data: any) => {
    return apiClient.post('/projects', token, data)
  },
}

// Tasks API
export const tasksApi = {
  list: async (token: string, projectId: number) => {
    return apiClient.get('/tasks', token, { project_id: projectId })
  },

  get: async (token: string, taskId: number) => {
    return apiClient.get(`/tasks/${taskId}`, token)
  },

  create: async (token: string, data: any) => {
    return apiClient.post('/tasks', token, data)
  },

  update: async (token: string, taskId: number, data: any) => {
    return apiClient.patch(`/tasks/${taskId}`, token, data)
  },
}

// Analytics API
export const analyticsApi = {
  getDashboardOverview: async (token: string, organizationId: number) => {
    return apiClient.get('/analytics/dashboard/overview', token, { organization_id: organizationId })
  },
}

// Notifications API
export const notificationsApi = {
  getNotifications: async (token: string) => {
    return apiClient.get('/notifications', token)
  },

  markAsRead: async (token: string, notificationId: number) => {
    return apiClient.post(`/notifications/${notificationId}/read`, token, {})
  },
}
