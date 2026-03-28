import { useMessagesStore, _resetRequestSeqs } from '@/stores/messages'
import { makeMessage, makeChannel } from '../helpers/factories'
import type { WsEvent } from '@/api/types'

vi.mock('@/api/endpoints/messages', () => ({
  listMessages: vi.fn(),
  listChannels: vi.fn(),
}))

const messagesApi = await import('@/api/endpoints/messages')

function resetStore() {
  _resetRequestSeqs()
  useMessagesStore.setState({
    channels: [],
    channelsLoading: false,
    channelsError: null,
    messages: [],
    total: 0,
    loading: false,
    loadingMore: false,
    error: null,
    unreadCounts: {},
    expandedThreads: new Set(),
  })
}

describe('messagesStore', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    resetStore()
  })

  describe('fetchChannels', () => {
    it('fetches and sets channels', async () => {
      const channels = [makeChannel('#engineering'), makeChannel('#product')]
      vi.mocked(messagesApi.listChannels).mockResolvedValue(channels)

      await useMessagesStore.getState().fetchChannels()

      expect(useMessagesStore.getState().channels).toHaveLength(2)
      expect(useMessagesStore.getState().channelsLoading).toBe(false)
    })

    it('sets channelsError on failure', async () => {
      vi.mocked(messagesApi.listChannels).mockRejectedValue(new Error('Network error'))

      await useMessagesStore.getState().fetchChannels()

      expect(useMessagesStore.getState().channelsError).toBe('Network error')
      expect(useMessagesStore.getState().channelsLoading).toBe(false)
    })
  })

  describe('fetchMessages', () => {
    it('fetches and sets messages for a channel', async () => {
      const msgs = [makeMessage('1'), makeMessage('2')]
      vi.mocked(messagesApi.listMessages).mockResolvedValue({ data: msgs, total: 10, offset: 0, limit: 50 })

      await useMessagesStore.getState().fetchMessages('#engineering')

      expect(useMessagesStore.getState().messages).toHaveLength(2)
      expect(useMessagesStore.getState().total).toBe(10)
      expect(useMessagesStore.getState().loading).toBe(false)
    })

    it('discards stale responses on rapid channel switching', async () => {
      const slowMsgs = [makeMessage('slow')]
      const fastMsgs = [makeMessage('fast')]

      let resolveFirst!: (value: unknown) => void
      const firstCall = new Promise((r) => { resolveFirst = r })
      vi.mocked(messagesApi.listMessages)
        .mockImplementationOnce(() => firstCall as ReturnType<typeof messagesApi.listMessages>)
        .mockResolvedValueOnce({ data: fastMsgs, total: 1, offset: 0, limit: 50 })

      // Start first fetch (slow)
      const p1 = useMessagesStore.getState().fetchMessages('#old-channel')
      // Start second fetch immediately (fast)
      const p2 = useMessagesStore.getState().fetchMessages('#new-channel')
      await p2

      // Resolve the slow one after the fast one completed
      resolveFirst({ data: slowMsgs, total: 1, offset: 0, limit: 50 })
      await p1

      // Store should have the fast response, not the slow one
      expect(useMessagesStore.getState().messages[0]!.id).toBe('fast')
    })

    it('sets error on failure', async () => {
      vi.mocked(messagesApi.listMessages).mockRejectedValue(new Error('Server error'))

      await useMessagesStore.getState().fetchMessages('#engineering')

      expect(useMessagesStore.getState().error).toBe('Server error')
    })
  })

  describe('fetchMoreMessages', () => {
    it('appends messages to existing list', async () => {
      useMessagesStore.setState({ messages: [makeMessage('1')], total: 5 })
      vi.mocked(messagesApi.listMessages).mockResolvedValue({
        data: [makeMessage('2'), makeMessage('3')],
        total: 5,
        offset: 1,
        limit: 50,
      })

      await useMessagesStore.getState().fetchMoreMessages('#engineering')

      expect(useMessagesStore.getState().messages).toHaveLength(3)
      expect(useMessagesStore.getState().loadingMore).toBe(false)
    })

    it('skips if already loading more', async () => {
      useMessagesStore.setState({ loadingMore: true })

      await useMessagesStore.getState().fetchMoreMessages('#engineering')

      expect(messagesApi.listMessages).not.toHaveBeenCalled()
    })
  })

  describe('handleWsEvent', () => {
    const makeWsEvent = (message: Record<string, unknown>): WsEvent => ({
      event_type: 'message.sent',
      channel: 'messages',
      timestamp: new Date().toISOString(),
      payload: { message },
    })

    it('prepends message to active channel list', () => {
      useMessagesStore.setState({ messages: [makeMessage('existing')], total: 1 })
      const newMsg = makeMessage('new', { channel: '#engineering' })

      useMessagesStore.getState().handleWsEvent(makeWsEvent(newMsg as unknown as Record<string, unknown>), '#engineering')

      const { messages, total } = useMessagesStore.getState()
      expect(messages).toHaveLength(2)
      expect(messages[0]!.id).toBe('new')
      expect(total).toBe(2)
    })

    it('increments unread for inactive channel', () => {
      const newMsg = makeMessage('new', { channel: '#product' })

      useMessagesStore.getState().handleWsEvent(makeWsEvent(newMsg as unknown as Record<string, unknown>), '#engineering')

      expect(useMessagesStore.getState().unreadCounts['#product']).toBe(1)
      expect(useMessagesStore.getState().messages).toHaveLength(0)
    })

    it('skips malformed payloads', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      useMessagesStore.getState().handleWsEvent(makeWsEvent({ bad: true }), '#engineering')

      expect(useMessagesStore.getState().messages).toHaveLength(0)
      consoleSpy.mockRestore()
    })

    it('skips when payload has no message', () => {
      const event: WsEvent = {
        event_type: 'message.sent',
        channel: 'messages',
        timestamp: new Date().toISOString(),
        payload: {},
      }

      useMessagesStore.getState().handleWsEvent(event, '#engineering')

      expect(useMessagesStore.getState().messages).toHaveLength(0)
    })
  })

  describe('toggleThread', () => {
    it('adds task_id to expanded set', () => {
      useMessagesStore.getState().toggleThread('task-1')
      expect(useMessagesStore.getState().expandedThreads.has('task-1')).toBe(true)
    })

    it('removes task_id from expanded set on second toggle', () => {
      useMessagesStore.getState().toggleThread('task-1')
      useMessagesStore.getState().toggleThread('task-1')
      expect(useMessagesStore.getState().expandedThreads.has('task-1')).toBe(false)
    })
  })

  describe('resetUnread', () => {
    it('clears unread count for a channel', () => {
      useMessagesStore.setState({ unreadCounts: { '#engineering': 5, '#product': 3 } })

      useMessagesStore.getState().resetUnread('#engineering')

      expect(useMessagesStore.getState().unreadCounts['#engineering']).toBeUndefined()
      expect(useMessagesStore.getState().unreadCounts['#product']).toBe(3)
    })

    it('is no-op for channels without unread counts', () => {
      const before = useMessagesStore.getState().unreadCounts

      useMessagesStore.getState().resetUnread('#nonexistent')

      expect(useMessagesStore.getState().unreadCounts).toBe(before)
    })
  })
})
