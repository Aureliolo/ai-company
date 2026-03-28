import { create } from 'zustand'
import * as messagesApi from '@/api/endpoints/messages'
import { getErrorMessage } from '@/utils/errors'
import { sanitizeForLog } from '@/utils/logging'
import type { Channel, Message, WsEvent } from '@/api/types'

const MESSAGES_FETCH_LIMIT = 50

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

  // Actions
  fetchChannels: () => Promise<void>
  fetchMessages: (channel: string, limit?: number) => Promise<void>
  fetchMoreMessages: (channel: string) => Promise<void>
  handleWsEvent: (event: WsEvent, activeChannel: string | null) => void
  toggleThread: (taskId: string) => void
  resetUnread: (channel: string) => void
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
    set({ loading: true, error: null })
    try {
      const result = await messagesApi.listMessages({ channel, limit })
      if (seq !== messageRequestSeq) return
      set({ messages: result.data, total: result.total, loading: false })
    } catch (err) {
      if (seq !== messageRequestSeq) return
      set({ loading: false, error: getErrorMessage(err) })
    }
  },

  fetchMoreMessages: async (channel) => {
    const { messages: existing, loadingMore } = get()
    if (loadingMore) return
    set({ loadingMore: true })
    try {
      const result = await messagesApi.listMessages({
        channel,
        limit: MESSAGES_FETCH_LIMIT,
        offset: existing.length,
      })
      set((s) => ({
        messages: [...s.messages, ...result.data],
        total: result.total,
        loadingMore: false,
      }))
    } catch (err) {
      set({ loadingMore: false, error: getErrorMessage(err) })
    }
  },

  handleWsEvent: (event, activeChannel) => {
    const { payload } = event
    if (!payload.message || typeof payload.message !== 'object' || Array.isArray(payload.message)) return

    const candidate = payload.message as Record<string, unknown>
    if (
      typeof candidate.id !== 'string' ||
      typeof candidate.timestamp !== 'string' ||
      typeof candidate.sender !== 'string' ||
      typeof candidate.channel !== 'string' ||
      typeof candidate.content !== 'string'
    ) {
      console.error('[messages/ws] Received malformed message payload, skipping', {
        id: sanitizeForLog(candidate.id),
        hasSender: typeof candidate.sender === 'string',
        hasChannel: typeof candidate.channel === 'string',
      })
      return
    }

    const message = candidate as unknown as Message
    if (message.channel === activeChannel) {
      // Prepend to active channel's message list
      set((s) => ({
        messages: [message, ...s.messages],
        total: s.total + 1,
      }))
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
}))
