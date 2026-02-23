/**
 * API Client Wrapper - Eliminates duplicated fetch patterns
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'

interface RequestOptions {
  method?: HttpMethod
  body?: any
  headers?: Record<string, string>
  queryParams?: Record<string, any>
}

/**
 * Base API client that handles common request patterns
 */
class ApiClient {
  private baseUrl: string

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
  }

  /**
   * Build URL with query parameters
   */
  private buildUrl(endpoint: string, queryParams?: Record<string, any>): string {
    const url = `${this.baseUrl}${endpoint}`
    if (!queryParams) return url

    const params = new URLSearchParams()
    Object.entries(queryParams).forEach(([key, value]) => {
      if (value !== null && value !== undefined) {
        params.append(key, String(value))
      }
    })

    const queryString = params.toString()
    return queryString ? `${url}?${queryString}` : url
  }

  /**
   * Make authenticated GET request
   */
  async get<T>(endpoint: string, token: string, queryParams?: Record<string, any>): Promise<T> {
    const url = this.buildUrl(endpoint, queryParams)
    const response = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    })

    if (!response.ok) {
      throw new Error(`Failed to fetch: ${endpoint}`)
    }

    return response.json()
  }

  /**
   * Make authenticated POST request
   */
  async post<T>(endpoint: string, token: string, data: any): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(data),
    })

    if (!response.ok) {
      throw new Error(`Failed to post: ${endpoint}`)
    }

    return response.json()
  }

  /**
   * Make authenticated PATCH request
   */
  async patch<T>(endpoint: string, token: string, data: any): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(data),
    })

    if (!response.ok) {
      throw new Error(`Failed to patch: ${endpoint}`)
    }

    return response.json()
  }

  /**
   * Make authenticated DELETE request
   */
  async delete(endpoint: string, token: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    })

    if (!response.ok) {
      throw new Error(`Failed to delete: ${endpoint}`)
    }
  }

  /**
   * Make unauthenticated request (for login, register)
   */
  async request<T>(
    endpoint: string,
    options: RequestOptions = {}
  ): Promise<T> {
    const { method = 'GET', body, headers = {}, queryParams } = options
    const url = this.buildUrl(endpoint, queryParams)

    const fetchOptions: RequestInit = {
      method,
      headers,
    }

    if (body) {
      if (headers['Content-Type'] === 'application/x-www-form-urlencoded') {
        fetchOptions.body = body
      } else {
        fetchOptions.body = JSON.stringify(body)
      }
    }

    const response = await fetch(url, fetchOptions)

    if (!response.ok) {
      throw new Error(`Request failed: ${endpoint}`)
    }

    return response.json()
  }
}

// Export singleton instance
export const apiClient = new ApiClient(API_BASE_URL)
