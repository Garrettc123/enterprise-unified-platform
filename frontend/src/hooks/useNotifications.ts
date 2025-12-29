import { useState, useEffect, useCallback } from 'react'
import { notificationsApi } from '../services/api'

interface Notification {
  id: number
  title: string
  message: string
  notification_type: string
  is_read: boolean
  created_at: string
}

export function useNotifications() {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)

  const fetchNotifications = useCallback(async () => {
    const token = localStorage.getItem('access_token')
    if (!token) return

    try {
      const data = await notificationsApi.getNotifications(token)
      setNotifications(data)
      setUnreadCount(data.filter((n: Notification) => !n.is_read).length)
    } catch (error) {
      console.error('Error fetching notifications:', error)
    }
  }, [])

  useEffect(() => {
    fetchNotifications()
    const interval = setInterval(fetchNotifications, 30000) // Poll every 30 seconds
    return () => clearInterval(interval)
  }, [fetchNotifications])

  const markAsRead = useCallback(
    async (notificationId: number) => {
      const token = localStorage.getItem('access_token')
      if (!token) return

      await notificationsApi.markAsRead(token, notificationId)
      setNotifications((prev) =>
        prev.map((n) =>
          n.id === notificationId ? { ...n, is_read: true } : n
        )
      )
      setUnreadCount((prev) => Math.max(0, prev - 1))
    },
    []
  )

  return {
    notifications,
    unreadCount,
    markAsRead,
    refetch: fetchNotifications,
  }
}
