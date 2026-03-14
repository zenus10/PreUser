import { useEffect, useRef } from 'react'
import { useProjectStore } from '../store/useProjectStore'
import type { ProgressData } from '../api/types'

/**
 * Hook that connects to the WebSocket for real-time progress,
 * with a polling fallback if WebSocket is unavailable.
 */
export function useProgress() {
  const projectId = useProjectStore((s) => s.projectId)
  const setProgress = useProjectStore((s) => s.setProgress)
  const fetchProgress = useProjectStore((s) => s.fetchProgress)
  const status = useProjectStore((s) => s.status)
  const wsRef = useRef<WebSocket | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!projectId || status === 'completed' || status === 'failed') return

    // Try WebSocket first
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/progress/${projectId}`

    let wsConnected = false

    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        wsConnected = true
        // Stop polling if WS connected
        if (pollRef.current) {
          clearInterval(pollRef.current)
          pollRef.current = null
        }
      }

      ws.onmessage = (event) => {
        try {
          const data: ProgressData = JSON.parse(event.data)
          setProgress(data)
        } catch { /* ignore bad messages */ }
      }

      ws.onclose = () => {
        wsConnected = false
        // Fall back to polling
        startPolling()
      }

      ws.onerror = () => {
        wsConnected = false
        ws.close()
      }
    } catch {
      // WebSocket not available, use polling
    }

    // Start polling as initial fallback (WS may take time to connect)
    function startPolling() {
      if (pollRef.current) return
      pollRef.current = setInterval(() => {
        fetchProgress()
      }, 2000)
    }

    // Start polling immediately as fallback
    startPolling()
    fetchProgress()

    return () => {
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
  }, [projectId, status, setProgress, fetchProgress])
}
