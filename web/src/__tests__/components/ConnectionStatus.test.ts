import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
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
    start: () => { fn() },
    stop: vi.fn(),
  }),
}))

describe('ConnectionStatus', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  function getWsGroup(wrapper: ReturnType<typeof mount>) {
    return wrapper.find('[aria-label^="WebSocket:"]')
  }

  function getWsDot(wrapper: ReturnType<typeof mount>) {
    return getWsGroup(wrapper).find('span[aria-hidden="true"]')
  }

  function getApiGroup(wrapper: ReturnType<typeof mount>) {
    return wrapper.find('[aria-label^="API:"]')
  }

  function getApiDot(wrapper: ReturnType<typeof mount>) {
    return getApiGroup(wrapper).find('span[aria-hidden="true"]')
  }

  describe('WebSocket status', () => {
    it('shows green dot when connected', () => {
      const wsStore = useWebSocketStore()
      wsStore.$patch({ connected: true })

      const wrapper = mount(ConnectionStatus)
      const dot = getWsDot(wrapper)
      expect(dot.classes()).toContain('bg-green-500')
    })

    it('shows yellow dot when disconnected but not exhausted', () => {
      const wsStore = useWebSocketStore()
      wsStore.$patch({ connected: false, reconnectExhausted: false })

      const wrapper = mount(ConnectionStatus)
      const dot = getWsDot(wrapper)
      expect(dot.classes()).toContain('bg-yellow-500')
    })

    it('shows red dot when reconnect exhausted', () => {
      const wsStore = useWebSocketStore()
      wsStore.$patch({ connected: false, reconnectExhausted: true })

      const wrapper = mount(ConnectionStatus)
      const dot = getWsDot(wrapper)
      expect(dot.classes()).toContain('bg-red-500')
    })

    it('has correct aria-label for connected state', () => {
      const wsStore = useWebSocketStore()
      wsStore.$patch({ connected: true })

      const wrapper = mount(ConnectionStatus)
      expect(getWsGroup(wrapper).attributes('aria-label')).toBe('WebSocket: connected')
    })

    it('has correct aria-label for reconnecting state', () => {
      const wsStore = useWebSocketStore()
      wsStore.$patch({ connected: false, reconnectExhausted: false })

      const wrapper = mount(ConnectionStatus)
      expect(getWsGroup(wrapper).attributes('aria-label')).toBe('WebSocket: reconnecting')
    })

    it('has correct aria-label for connection lost state', () => {
      const wsStore = useWebSocketStore()
      wsStore.$patch({ connected: false, reconnectExhausted: true })

      const wrapper = mount(ConnectionStatus)
      expect(getWsGroup(wrapper).attributes('aria-label')).toBe('WebSocket: connection lost')
    })
  })

  describe('API health status', () => {
    it('shows green dot when health status is ok', async () => {
      vi.mocked(getHealth).mockResolvedValue({ status: 'ok', persistence: true, message_bus: true, version: '0.1.0', uptime_seconds: 100 })

      const wrapper = mount(ConnectionStatus)
      await flushPromises()

      const dot = getApiDot(wrapper)
      expect(dot.classes()).toContain('bg-green-500')
    })

    it('shows yellow dot when health status is degraded', async () => {
      vi.mocked(getHealth).mockResolvedValue({ status: 'degraded', persistence: true, message_bus: false, version: '0.1.0', uptime_seconds: 100 })

      const wrapper = mount(ConnectionStatus)
      await flushPromises()

      const dot = getApiDot(wrapper)
      expect(dot.classes()).toContain('bg-yellow-500')
    })

    it('shows red dot when health check fails', async () => {
      vi.mocked(getHealth).mockRejectedValue(new Error('Network error'))
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      const wrapper = mount(ConnectionStatus)
      await flushPromises()

      const dot = getApiDot(wrapper)
      expect(dot.classes()).toContain('bg-red-500')
      consoleSpy.mockRestore()
    })

    it('shows gray dot before health is fetched', () => {
      // Make getHealth never resolve during this test
      vi.mocked(getHealth).mockReturnValue(new Promise(() => {}))

      const wrapper = mount(ConnectionStatus)
      // Don't flush -- health hasn't resolved yet
      const dot = getApiDot(wrapper)
      expect(dot.classes()).toContain('bg-gray-500')
    })

    it('has correct aria-label for ok status', async () => {
      vi.mocked(getHealth).mockResolvedValue({ status: 'ok', persistence: true, message_bus: true, version: '0.1.0', uptime_seconds: 100 })

      const wrapper = mount(ConnectionStatus)
      await flushPromises()

      expect(getApiGroup(wrapper).attributes('aria-label')).toBe('API: ok')
    })

    it('has correct aria-label for error status', async () => {
      vi.mocked(getHealth).mockRejectedValue(new Error('fail'))
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      const wrapper = mount(ConnectionStatus)
      await flushPromises()

      expect(getApiGroup(wrapper).attributes('aria-label')).toBe('API: error')
      consoleSpy.mockRestore()
    })
  })
})
