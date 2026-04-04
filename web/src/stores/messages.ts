import { create } from 'zustand'
import * as messagesApi from '@/api/endpoints/messages'
import { getErrorMessage } from '@/utils/errors'
import { sanitizeForLog } from '@/utils/logging'
import { createLogger } from '@/lib/logger'
import type { Channel, Message, WsEvent } from '@/api/types'

const log = createLogger('messages')

const MESSAGES_FETCH_LIMIT = 50

/** Validate a WS payload and return a typed Message, or null if malformed. */
function parseWsMessage(
  payload: WsEvent['payload'],
): Message | null {
  if (
    !payload.message ||
    typeof payload.message !== 'object' ||
    Array.isArray(payload.message)
  ) return null

  const c = payload.message as Record<string, unknown>
  if (
    typeof c.id !== 'string' ||
    typeof c.timestamp !== 'string' ||
    typeof c.sender !== 'string' ||
    typeof c.to !== 'string' ||
    typeof c.channel !== 'string' ||
    typeof c.content !== 'string' ||
    typeof c.type !== 'string' ||
    typeof c.priority !== 'string' ||
    !Array.isArray(c.attachments) ||
    !c.metadata ||
    typeof c.metadata !== 'object' ||
    Array.isArray(c.metadata)
  ) {
    log.error(
      'Malformed WS payload, skipping',
      {
        id: sanitizeForLog(c.id),
        hasSender: typeof c.sender === 'string',
        hasChannel: typeof c.channel === 'string',
      },
    )
    return null
  }

  return c as unknown as Message
}

interface MessagesState {
  // Channels
  channels: Channel[]
  channelsLoading: boolean
  channelsError: string | null

  // Messages (for active channel)
  messages: Message[]
  total: number
  loading: boolean
  loadingMore: boolean
  error: string | null

  // Unread tracking: channel name -> count
  unreadCounts: Record<string, number>

  // Thread expansion: Set of task_id values
  expandedThreads: Set<string>

  // New-message flash tracking (WS-delivered IDs)
  newMessageIds: Set<string>

  // Actions
  fetchChannels: () => Promise<void>
  fetchMessages: (channel: string, limit?: number) => Promise<void>
  fetchMoreMessages: (channel: string) => Promise<void>
  handleWsEvent: (event: WsEvent, activeChannel: string | null) => void
  toggleThread: (taskId: string) => void
  resetUnread: (channel: string) => void
  clearNewMessageIds: () => void
}

let channelRequestSeq = 0
let messageRequestSeq = 0

/** Reset module-level sequence counters -- test-only. */
export function _resetRequestSeqs(): void {
  channelRequestSeq = 0
  messageRequestSeq = 0
}

export const useMessagesStore = create<MessagesState>()((set, get) => ({
  channels: [],
  channelsLoading: false,
  channelsError: null,

  messages: [],
  total: 0,
  loading: false,
  loadingMore: false,
  error: null,

  unreadCounts: {},
  expandedThreads: new Set<string>(),
  newMessageIds: new Set<string>(),

  fetchChannels: async () => {
    const seq = ++channelRequestSeq
    set({ channelsLoading: true, channelsError: null })
    try {
      const channels = await messagesApi.listChannels()
      if (seq !== channelRequestSeq) return
      set({ channels, channelsLoading: false })
    } catch (err) {
      if (seq !== channelRequestSeq) return
      set({ channelsLoading: false, channelsError: getErrorMessage(err) })
    }
  },

  fetchMessages: async (channel, limit = MESSAGES_FETCH_LIMIT) => {
    const seq = ++messageRequestSeq
    set({ loading: true, error: null, loadingMore: false })
    try {
      const result = await messagesApi.listMessages({ channel, limit })
      if (seq !== messageRequestSeq) return
      set({
        messages: result.data,
        total: result.total,
        loading: false,
        newMessageIds: new Set<string>(),
      })
    } catch (err) {
      if (seq !== messageRequestSeq) return
      set({ loading: false, error: getErrorMessage(err) })
    }
  },

  fetchMoreMessages: async (channel) => {
    const { messages: existing, loadingMore } = get()
    if (loadingMore) return
    const seq = messageRequestSeq
    set({ loadingMore: true, error: null })
    try {
      const result = await messagesApi.listMessages({
        channel,
        limit: MESSAGES_FETCH_LIMIT,
        offset: existing.length,
      })
      if (seq !== messageRequestSeq) return
      set((s) => {
        const existingIds = new Set(
          s.messages.map((m) => m.id),
        )
        const deduped = result.data.filter(
          (m) => !existingIds.has(m.id),
        )
        return {
          messages: [...s.messages, ...deduped],
          total: result.total,
          loadingMore: false,
        }
      })
    } catch (err) {
      if (seq !== messageRequestSeq) return
      set({ loadingMore: false, error: getErrorMessage(err) })
    }
  },

  handleWsEvent: (event, activeChannel) => {
    const message = parseWsMessage(event.payload)
    if (!message) return

    if (message.channel === activeChannel) {
      // Prepend to active channel (with dedup)
      set((s) => {
        if (s.messages.some((m) => m.id === message.id)) {
          return s
        }
        return {
          messages: [message, ...s.messages],
          total: s.total + 1,
          newMessageIds: new Set([
            ...s.newMessageIds,
            message.id,
          ]),
        }
      })
    } else {
      // Increment unread count for inactive channel
      set((s) => ({
        unreadCounts: {
          ...s.unreadCounts,
          [message.channel]: (s.unreadCounts[message.channel] ?? 0) + 1,
        },
      }))
    }
  },

  toggleThread: (taskId) => {
    set((s) => {
      const next = new Set(s.expandedThreads)
      if (next.has(taskId)) {
        next.delete(taskId)
      } else {
        next.add(taskId)
      }
      return { expandedThreads: next }
    })
  },

  resetUnread: (channel) => {
    set((s) => {
      if (!s.unreadCounts[channel]) return s
      const next = { ...s.unreadCounts }
      delete next[channel]
      return { unreadCounts: next }
    })
  },

  clearNewMessageIds: () => {
    set({ newMessageIds: new Set<string>() })
  },
}))
