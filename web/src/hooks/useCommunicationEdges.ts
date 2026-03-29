import { useEffect, useMemo, useState } from 'react'
import { listMessages } from '@/api/endpoints/messages'
import { aggregateMessages, type CommunicationLink } from '@/pages/org/aggregate-messages'

/** Default time window for frequency calculation: 24 hours. */
const DEFAULT_TIME_WINDOW_MS = 24 * 60 * 60 * 1000

/** Maximum number of pages to fetch to avoid runaway pagination. */
const MAX_PAGES = 10

/** Page size for each API call. */
const PAGE_LIMIT = 100

export interface UseCommunicationEdgesReturn {
  links: CommunicationLink[]
  loading: boolean
  error: string | null
}

/**
 * Fetch inter-agent messages and aggregate into communication links.
 *
 * Fetches up to MAX_PAGES pages of messages, aggregates sender/receiver pairs,
 * and returns communication links with volume and frequency data.
 */
export function useCommunicationEdges(enabled = true): UseCommunicationEdgesReturn {
  const [messages, setMessages] = useState<Array<{ sender: string; to: string }>>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!enabled) return

    let cancelled = false

    async function fetchAll() {
      setLoading(true)
      setError(null)
      try {
        const allMessages: Array<{ sender: string; to: string }> = []
        let offset = 0

        for (let page = 0; page < MAX_PAGES; page++) {
          const result = await listMessages({ offset, limit: PAGE_LIMIT })
          for (const msg of result.data) {
            allMessages.push({ sender: msg.sender, to: msg.to })
          }
          offset += result.limit
          if (offset >= result.total) break
        }

        if (!cancelled) {
          setMessages(allMessages)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to fetch messages')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    fetchAll()
    return () => { cancelled = true }
  }, [enabled])

  const links = useMemo(
    () => (messages.length > 0 ? aggregateMessages(messages, DEFAULT_TIME_WINDOW_MS) : []),
    [messages],
  )

  return { links, loading, error }
}
