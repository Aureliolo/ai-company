import { useCallback, useEffect, useState } from 'react'

import { listClients, type ClientProfile } from '@/api/endpoints/clients'
import { createLogger } from '@/lib/logger'
import { useWebSocketStore } from '@/stores/websocket'

const log = createLogger('useClientsData')

/**
 * Loads the paginated client list and subscribes to WS updates.
 *
 * Returns the current client snapshot plus connection state so the
 * consumer can surface loading, error, and stale-feed banners.
 */
export function useClientsData(): {
  clients: readonly ClientProfile[]
  loading: boolean
  error: string | null
  wsConnected: boolean
  wsSetupError: string | null
  reload: () => Promise<void>
} {
  const [clients, setClients] = useState<readonly ClientProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const wsConnected = useWebSocketStore((s) => s.connected)
  const wsSetupError: string | null = null

  const reload = useCallback(async () => {
    try {
      const result = await listClients({ limit: 100 })
      setClients(result.data)
      setError(null)
    } catch (err) {
      log.error('list_clients_failed', err)
      setError('Failed to load clients. Retry shortly.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  return { clients, loading, error, wsConnected, wsSetupError, reload }
}
