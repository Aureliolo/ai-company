import { useEffect, useMemo, useReducer } from 'react'
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

interface FetchState {
  messages: Array<{ sender: string; to: string }>
  loading: boolean
  error: string | null
}

type FetchAction =
  | { type: 'reset' }
  | { type: 'loading' }
  | { type: 'success'; messages: Array<{ sender: string; to: string }> }
  | { type: 'error'; error: string }

function fetchReducer(_state: FetchState, action: FetchAction): FetchState {
  switch (action.type) {
    case 'reset':
      return { messages: [], loading: false, error: null }
    case 'loading':
      return { messages: [], loading: true, error: null }
    case 'success':
      return { messages: action.messages, loading: false, error: null }
    case 'error':
      return { messages: [], loading: false, error: action.error }
  }
}

/**
 * Fetch inter-agent messages and aggregate into communication links.
 *
 * Fetches up to MAX_PAGES pages of messages, aggregates sender/receiver pairs,
 * and returns communication links with volume and frequency data.
 */
export function useCommunicationEdges(enabled = true): UseCommunicationEdgesReturn {
  const [state, dispatch] = useReducer(fetchReducer, {
    messages: [],
    loading: false,
    error: null,
  })

  useEffect(() => {
    if (!enabled) {
      dispatch({ type: 'reset' })
      return
    }

    const controller = new AbortController()
    dispatch({ type: 'loading' })

    async function fetchAll() {
      try {
        const allMessages: Array<{ sender: string; to: string }> = []
        let offset = 0

        for (let page = 0; page < MAX_PAGES; page++) {
          if (controller.signal.aborted) return
          const result = await listMessages({ offset, limit: PAGE_LIMIT })
          for (const msg of result.data) {
            allMessages.push({ sender: msg.sender, to: msg.to })
          }
          offset += result.data.length
          if (offset >= result.total || result.data.length === 0) break
        }

        if (!controller.signal.aborted) {
          dispatch({ type: 'success', messages: allMessages })
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          dispatch({ type: 'error', error: err instanceof Error ? err.message : 'Failed to fetch messages' })
        }
      }
    }

    fetchAll()
    return () => { controller.abort() }
  }, [enabled])

  const links = useMemo(
    () => (state.messages.length > 0 ? aggregateMessages(state.messages, DEFAULT_TIME_WINDOW_MS) : []),
    [state.messages],
  )

  return { links, loading: state.loading, error: state.error }
}
