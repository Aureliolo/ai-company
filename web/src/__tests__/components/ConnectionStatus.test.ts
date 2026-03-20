import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { useWebSocketStore } from '@/stores/websocket'
import ConnectionStatus from '@/components/layout/ConnectionStatus.vue'

vi.mock('@/api/endpoints/auth', () => ({
  getWsTicket: vi.fn().mockResolvedValue({ ticket: 'test-ticket', expires_in: 30 }),
}))

vi.mock('@/api/endpoints/health', () => ({
  getHealth: vi.fn().mockResolvedValue({ status: 'ok' }),
}))

vi.mock('@/composables/usePolling', () => ({
  usePolling: () => ({ start: vi.fn(), stop: vi.fn() }),
}))

describe('ConnectionStatus', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  function getWsDot(wrapper: ReturnType<typeof mount>) {
    // The WS status dot is the second status group
    const groups = wrapper.findAll('[class*="flex items-center gap-1.5"]')
    const wsGroup = groups[1]
    return wsGroup.find('span[aria-hidden="true"]')
  }

  function getWsLabel(wrapper: ReturnType<typeof mount>) {
    const groups = wrapper.findAll('[class*="flex items-center gap-1.5"]')
    return groups[1]
  }

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
    const wsGroup = getWsLabel(wrapper)
    expect(wsGroup.attributes('aria-label')).toBe('WebSocket: connected')
  })

  it('has correct aria-label for reconnecting state', () => {
    const wsStore = useWebSocketStore()
    wsStore.$patch({ connected: false, reconnectExhausted: false })

    const wrapper = mount(ConnectionStatus)
    const wsGroup = getWsLabel(wrapper)
    expect(wsGroup.attributes('aria-label')).toBe('WebSocket: reconnecting')
  })

  it('has correct aria-label for connection lost state', () => {
    const wsStore = useWebSocketStore()
    wsStore.$patch({ connected: false, reconnectExhausted: true })

    const wrapper = mount(ConnectionStatus)
    const wsGroup = getWsLabel(wrapper)
    expect(wsGroup.attributes('aria-label')).toBe('WebSocket: connection lost')
  })
})
