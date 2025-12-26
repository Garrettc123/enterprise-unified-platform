import { useState, useEffect, useCallback } from 'react'
import { authApi } from '../services/api'

interface User {
  id: number
  username: string
  email: string
  full_name?: string
  avatar_url?: string
}

interface AuthContext {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  register: (userData: any) => Promise<void>
}

export function useAuth(): AuthContext {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isAuthenticated, setIsAuthenticated] = useState(false)

  useEffect(() => {
    // Check if user is already authenticated
    const checkAuth = async () => {
      const token = localStorage.getItem('access_token')
      if (token) {
        try {
          const userData = await authApi.getCurrentUser(token)
          setUser(userData)
          setIsAuthenticated(true)
        } catch (error) {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          setIsAuthenticated(false)
        }
      }
      setIsLoading(false)
    }

    checkAuth()
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const response = await authApi.login(username, password)
    localStorage.setItem('access_token', response.access_token)
    localStorage.setItem('refresh_token', response.refresh_token)
    
    const userData = await authApi.getCurrentUser(response.access_token)
    setUser(userData)
    setIsAuthenticated(true)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    setUser(null)
    setIsAuthenticated(false)
  }, [])

  const register = useCallback(async (userData: any) => {
    await authApi.register(userData)
  }, [])

  return {
    user,
    isAuthenticated,
    isLoading,
    login,
    logout,
    register,
  }
}
