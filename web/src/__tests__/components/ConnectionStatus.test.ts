import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { ref } from 'vue'
import { useWebSocketStore } from '@/stores/websocket'
import ConnectionStatus from '@/components/layout/ConnectionStatus.vue'

vi.mock('@/api/endpoints/auth', () => ({
  getWsTicket: vi.fn().mockResolvedValue({ ticket: 'test-ticket', expires_in: 30 }),
}))

import { getHealth } from '@/api/endpoints/health'

vi.mock('@/api/endpoints/health', () => ({
  getHealth: vi.fn().mockResolvedValue({ status: 'ok', persistence: true, message_bus: true, version: '0.1.0', uptime_seconds: 100 }),
}))

// Let usePolling invoke the callback immediately on start() so health checks run
vi.mock('@/composables/usePolling', () => ({
  usePolling: (fn: () => Promise<void>) => ({
    active: ref(false),
    start: () => { fn() },
    stop: vi.fn(),
  }),
}))

describe('ConnectionStatus', () => {
  let wrapper: ReturnType<typeof mount> | undefined

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    vi.restoreAllMocks()
  })

  function getWsGroup(w: ReturnType<typeof mount>) {
    return w.find('[aria-label^="WebSocket:"]')
  }

  function getWsDot(w: ReturnType<typeof mount>) {
    return getWsGroup(w).find('span[aria-hidden="true"]')
  }

  function getApiGroup(w: ReturnType<typeof mount>) {
    return w.find('[aria-label^="API:"]')
  }

  function getApiDot(w: ReturnType<typeof mount>) {
    return getApiGroup(w).find('span[aria-hidden="true"]')
  }

  describe('WebSocket status', () => {
    it('shows green dot when connected', () => {
      const wsStore = useWebSocketStore()
      wsStore.$patch({ connected: true })

      wrapper = mount(ConnectionStatus)
      const dot = getWsDot(wrapper)
      expect(dot.classes()).toContain('bg-green-500')
    })

    it('shows yellow dot when disconnected but not exhausted', () => {
      const wsStore = useWebSocketStore()
      wsStore.$patch({ connected: false, reconnectExhausted: false })

      wrapper = mount(ConnectionStatus)
      const dot = getWsDot(wrapper)
      expect(dot.classes()).toContain('bg-yellow-500')
    })

    it('shows red dot when reconnect exhausted', () => {
      const wsStore = useWebSocketStore()
      wsStore.$patch({ connected: false, reconnectExhausted: true })

      wrapper = mount(ConnectionStatus)
      const dot = getWsDot(wrapper)
      expect(dot.classes()).toContain('bg-red-500')
    })

    it('has correct aria-label for connected state', () => {
      const wsStore = useWebSocketStore()
      wsStore.$patch({ connected: true })

      wrapper = mount(ConnectionStatus)
      expect(getWsGroup(wrapper).attributes('aria-label')).toBe('WebSocket: connected')
    })

    it('has correct aria-label for reconnecting state', () => {
      const wsStore = useWebSocketStore()
      wsStore.$patch({ connected: false, reconnectExhausted: false })

      wrapper = mount(ConnectionStatus)
      expect(getWsGroup(wrapper).attributes('aria-label')).toBe('WebSocket: reconnecting')
    })

    it('has correct aria-label for connection lost state', () => {
      const wsStore = useWebSocketStore()
      wsStore.$patch({ connected: false, reconnectExhausted: true })

      wrapper = mount(ConnectionStatus)
      expect(getWsGroup(wrapper).attributes('aria-label')).toBe('WebSocket: connection lost')
    })
  })

  describe('API health status', () => {
    it('shows green dot when health status is ok', async () => {
      vi.mocked(getHealth).mockResolvedValue({ status: 'ok', persistence: true, message_bus: true, version: '0.1.0', uptime_seconds: 100 })

      wrapper = mount(ConnectionStatus)
      await flushPromises()

      const dot = getApiDot(wrapper)
      expect(dot.classes()).toContain('bg-green-500')
    })

    it('shows yellow dot when health status is degraded', async () => {
      vi.mocked(getHealth).mockResolvedValue({ status: 'degraded', persistence: true, message_bus: false, version: '0.1.0', uptime_seconds: 100 })

      wrapper = mount(ConnectionStatus)
      await flushPromises()

      const dot = getApiDot(wrapper)
      expect(dot.classes()).toContain('bg-yellow-500')
    })

    it('shows red dot when health check fails', async () => {
      vi.mocked(getHealth).mockRejectedValue(new Error('Network error'))
      vi.spyOn(console, 'error').mockImplementation(() => {})

      wrapper = mount(ConnectionStatus)
      await flushPromises()

      const dot = getApiDot(wrapper)
      expect(dot.classes()).toContain('bg-red-500')
    })

    it('shows gray dot when health status is down', async () => {
      vi.mocked(getHealth).mockResolvedValue({ status: 'down', persistence: false, message_bus: false, version: '0.1.0', uptime_seconds: 0 })

      wrapper = mount(ConnectionStatus)
      await flushPromises()

      // 'down' falls through to the else branch (gray), same as unknown/pending
      const dot = getApiDot(wrapper)
      expect(dot.classes()).toContain('bg-gray-500')
    })

    it('shows gray dot before health is fetched', () => {
      // Make getHealth never resolve during this test
      vi.mocked(getHealth).mockReturnValue(new Promise(() => {}))

      wrapper = mount(ConnectionStatus)
      // Don't flush -- health hasn't resolved yet
      const dot = getApiDot(wrapper)
      expect(dot.classes()).toContain('bg-gray-500')
    })

    it('has correct aria-label for ok status', async () => {
      vi.mocked(getHealth).mockResolvedValue({ status: 'ok', persistence: true, message_bus: true, version: '0.1.0', uptime_seconds: 100 })

      wrapper = mount(ConnectionStatus)
      await flushPromises()

      expect(getApiGroup(wrapper).attributes('aria-label')).toBe('API: ok')
    })

    it('has correct aria-label for error status', async () => {
      vi.mocked(getHealth).mockRejectedValue(new Error('fail'))
      vi.spyOn(console, 'error').mockImplementation(() => {})

      wrapper = mount(ConnectionStatus)
      await flushPromises()

      expect(getApiGroup(wrapper).attributes('aria-label')).toBe('API: error')
    })
  })
})
