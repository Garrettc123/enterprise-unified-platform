import { useCallback, useEffect, useRef, useState } from 'react'

export interface WebSocketMessage {
  type: string
  client_id?: string
  data?: string
  room_id?: string
  event?: string
  target_client_id?: string
  timestamp?: string
}

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected'

interface UseWebSocketOptions {
  /** WebSocket server URL. Defaults to ws://localhost:8000/ws/{clientId} */
  url?: string
  /** Automatically reconnect on disconnect */
  reconnect?: boolean
  /** Delay between reconnection attempts in ms (default 3000) */
  reconnectDelay?: number
  /** Maximum reconnection attempts (default 10) */
  maxReconnectAttempts?: number
  /** Maximum number of messages to keep in history (default 500) */
  maxMessages?: number
  /** Callback invoked for every incoming message */
  onMessage?: (message: WebSocketMessage) => void
}

export function useWebSocket(clientId: string, options: UseWebSocketOptions = {}) {
  const {
    url,
    reconnect = true,
    reconnectDelay = 3000,
    maxReconnectAttempts = 10,
    maxMessages = 500,
    onMessage,
  } = options

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const [status, setStatus] = useState<ConnectionStatus>('disconnected')
  const [messages, setMessages] = useState<WebSocketMessage[]>([])
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null)

  const getWsUrl = useCallback(() => {
    if (url) return url
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = import.meta.env.VITE_WS_URL || `${protocol}//${window.location.hostname}:8000`
    return `${host}/ws/${clientId}`
  }, [url, clientId])

  const connect = useCallback(() => {
    // Avoid duplicate connections
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return

    setStatus('connecting')
    const ws = new WebSocket(getWsUrl())

    ws.onopen = () => {
      setStatus('connected')
      reconnectAttemptsRef.current = 0
    }

    ws.onmessage = (event) => {
      try {
        const msg: WebSocketMessage = JSON.parse(event.data)
        setMessages((prev) => {
          const next = [...prev, msg]
          return next.length > maxMessages ? next.slice(-maxMessages) : next
        })
        setLastMessage(msg)
        onMessage?.(msg)
      } catch {
        // Non-JSON payload — wrap it
        const msg: WebSocketMessage = { type: 'raw', data: event.data }
        setMessages((prev) => {
          const next = [...prev, msg]
          return next.length > maxMessages ? next.slice(-maxMessages) : next
        })
        setLastMessage(msg)
        onMessage?.(msg)
      }
    }

    ws.onclose = () => {
      setStatus('disconnected')
      wsRef.current = null
      if (reconnect && reconnectAttemptsRef.current < maxReconnectAttempts) {
        reconnectAttemptsRef.current += 1
        reconnectTimerRef.current = setTimeout(connect, reconnectDelay)
      }
    }

    ws.onerror = () => {
      // onclose will fire after onerror — reconnect logic lives there
    }

    wsRef.current = ws
  }, [getWsUrl, reconnect, reconnectDelay, maxReconnectAttempts, onMessage])

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
    reconnectAttemptsRef.current = maxReconnectAttempts // prevent auto-reconnect
    wsRef.current?.close()
    wsRef.current = null
    setStatus('disconnected')
  }, [maxReconnectAttempts])

  /** Send a structured JSON message */
  const sendMessage = useCallback((message: WebSocketMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }, [])

  /** Broadcast a text message to all clients */
  const broadcast = useCallback((data: string) => {
    sendMessage({ type: 'message', data })
  }, [sendMessage])

  /** Send a direct message to a specific client */
  const sendDirect = useCallback((targetClientId: string, data: string) => {
    sendMessage({ type: 'direct', target_client_id: targetClientId, data })
  }, [sendMessage])

  /** Join a room/channel */
  const joinRoom = useCallback((roomId: string) => {
    sendMessage({ type: 'join_room', room_id: roomId })
  }, [sendMessage])

  /** Leave a room/channel */
  const leaveRoom = useCallback((roomId: string) => {
    sendMessage({ type: 'leave_room', room_id: roomId })
  }, [sendMessage])

  /** Send a message to a specific room */
  const sendToRoom = useCallback((roomId: string, data: string) => {
    sendMessage({ type: 'room_message', room_id: roomId, data })
  }, [sendMessage])

  /** Clear message history */
  const clearMessages = useCallback(() => {
    setMessages([])
    setLastMessage(null)
  }, [])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
      }
      wsRef.current?.close()
      wsRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId])

  return {
    status,
    messages,
    lastMessage,
    sendMessage,
    broadcast,
    sendDirect,
    joinRoom,
    leaveRoom,
    sendToRoom,
    connect,
    disconnect,
    clearMessages,
  }
}
