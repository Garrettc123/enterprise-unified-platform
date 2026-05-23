import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import DashboardCharts from '../components/DashboardCharts'

// Mock recharts ResponsiveContainer since it needs DOM dimensions
vi.mock('recharts', async () => {
  const actual = await vi.importActual<typeof import('recharts')>('recharts')
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="responsive-container" style={{ width: 500, height: 300 }}>
        {children}
      </div>
    ),
  }
})

const mockProjectStatus = [
  { status: 'active', count: 5 },
  { status: 'completed', count: 3 },
]

const mockTaskPriority = [
  { priority: 'high', count: 8 },
  { priority: 'medium', count: 12 },
  { priority: 'low', count: 4 },
]

const mockTaskTrend = [
  { date: '2025-01-01', completed_count: 3 },
  { date: '2025-01-02', completed_count: 5 },
]

const mockTeamWorkload = [
  { user: 'alice', assigned_tasks: 6 },
  { user: 'bob', assigned_tasks: 4 },
]

vi.mock('../services/api', () => ({
  analyticsApi: {
    getProjectStatusBreakdown: vi.fn(),
    getTaskPriorityDistribution: vi.fn(),
    getTaskStatusTrend: vi.fn(),
    getTeamWorkload: vi.fn(),
  },
}))

import { analyticsApi } from '../services/api'

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.setItem('access_token', 'test-token')
})

describe('DashboardCharts', () => {
  it('renders loading state initially', () => {
    vi.mocked(analyticsApi.getProjectStatusBreakdown).mockReturnValue(new Promise(() => {}))
    vi.mocked(analyticsApi.getTaskPriorityDistribution).mockReturnValue(new Promise(() => {}))
    vi.mocked(analyticsApi.getTaskStatusTrend).mockReturnValue(new Promise(() => {}))
    vi.mocked(analyticsApi.getTeamWorkload).mockReturnValue(new Promise(() => {}))

    render(<DashboardCharts organizationId={1} />)
    expect(screen.getByText('Loading charts...')).toBeInTheDocument()
  })

  it('renders all four chart sections with data', async () => {
    vi.mocked(analyticsApi.getProjectStatusBreakdown).mockResolvedValue(mockProjectStatus)
    vi.mocked(analyticsApi.getTaskPriorityDistribution).mockResolvedValue(mockTaskPriority)
    vi.mocked(analyticsApi.getTaskStatusTrend).mockResolvedValue(mockTaskTrend)
    vi.mocked(analyticsApi.getTeamWorkload).mockResolvedValue(mockTeamWorkload)

    render(<DashboardCharts organizationId={1} />)

    await waitFor(() => {
      expect(screen.getByText('Analytics')).toBeInTheDocument()
    })

    expect(screen.getByText('Project Status')).toBeInTheDocument()
    expect(screen.getByText('Task Priority Distribution')).toBeInTheDocument()
    expect(screen.getByText('Task Completion Trend')).toBeInTheDocument()
    expect(screen.getByText('Team Workload')).toBeInTheDocument()
  })

  it('renders empty state when no data is available', async () => {
    vi.mocked(analyticsApi.getProjectStatusBreakdown).mockResolvedValue([])
    vi.mocked(analyticsApi.getTaskPriorityDistribution).mockResolvedValue([])
    vi.mocked(analyticsApi.getTaskStatusTrend).mockResolvedValue([])
    vi.mocked(analyticsApi.getTeamWorkload).mockResolvedValue([])

    render(<DashboardCharts organizationId={1} />)

    await waitFor(() => {
      expect(screen.getByText('No project data available')).toBeInTheDocument()
    })

    expect(screen.getByText('No task data available')).toBeInTheDocument()
    expect(screen.getByText('No trend data available')).toBeInTheDocument()
    expect(screen.getByText('No workload data available')).toBeInTheDocument()
  })

  it('calls API with correct organization ID', async () => {
    vi.mocked(analyticsApi.getProjectStatusBreakdown).mockResolvedValue([])
    vi.mocked(analyticsApi.getTaskPriorityDistribution).mockResolvedValue([])
    vi.mocked(analyticsApi.getTaskStatusTrend).mockResolvedValue([])
    vi.mocked(analyticsApi.getTeamWorkload).mockResolvedValue([])

    render(<DashboardCharts organizationId={42} />)

    await waitFor(() => {
      expect(analyticsApi.getProjectStatusBreakdown).toHaveBeenCalledWith('test-token', 42)
    })

    expect(analyticsApi.getTaskPriorityDistribution).toHaveBeenCalledWith('test-token', 42)
    expect(analyticsApi.getTaskStatusTrend).toHaveBeenCalledWith('test-token', 42)
    expect(analyticsApi.getTeamWorkload).toHaveBeenCalledWith('test-token', 42)
  })

  it('handles API errors gracefully', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.mocked(analyticsApi.getProjectStatusBreakdown).mockRejectedValue(new Error('Network error'))
    vi.mocked(analyticsApi.getTaskPriorityDistribution).mockRejectedValue(new Error('Network error'))
    vi.mocked(analyticsApi.getTaskStatusTrend).mockRejectedValue(new Error('Network error'))
    vi.mocked(analyticsApi.getTeamWorkload).mockRejectedValue(new Error('Network error'))

    render(<DashboardCharts organizationId={1} />)

    await waitFor(() => {
      expect(screen.getByText('Analytics')).toBeInTheDocument()
    })

    expect(consoleSpy).toHaveBeenCalled()
    consoleSpy.mockRestore()
  })

  it('does not fetch data when no access token is present', async () => {
    localStorage.removeItem('access_token')

    render(<DashboardCharts organizationId={1} />)

    // Wait a tick for the useEffect to run
    await new Promise((resolve) => setTimeout(resolve, 50))

    expect(analyticsApi.getProjectStatusBreakdown).not.toHaveBeenCalled()
  })
})
