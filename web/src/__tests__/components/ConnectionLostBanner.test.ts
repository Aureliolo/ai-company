import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { defineComponent, h } from 'vue'
import { useWebSocketStore } from '@/stores/websocket'
import ConnectionLostBanner from '@/components/common/ConnectionLostBanner.vue'

vi.mock('@/api/endpoints/auth', () => ({
  getWsTicket: vi.fn().mockResolvedValue({ ticket: 'test-ticket', expires_in: 30 }),
}))

const ButtonStub = defineComponent({
  name: 'PvButton',
  props: ['label', 'icon', 'severity', 'size', 'text'],
  emits: ['click'],
  setup(props, { emit }) {
    return () => h('button', { onClick: () => emit('click') }, props.label)
  },
})

describe('ConnectionLostBanner', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  function mountBanner() {
    return mount(ConnectionLostBanner, {
      global: { stubs: { Button: ButtonStub } },
    })
  }

  it('does not render when reconnectExhausted is false', () => {
    const wrapper = mountBanner()
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.text()).toBe('')
  })

  it('renders warning banner when reconnectExhausted is true', () => {
    const wsStore = useWebSocketStore()
    wsStore.$patch({ reconnectExhausted: true })

    const wrapper = mountBanner()
    const alert = wrapper.find('[role="alert"]')
    expect(alert.exists()).toBe(true)
    expect(wrapper.text()).toContain('Connection lost')
    expect(wrapper.text()).toContain('real-time updates unavailable')
  })

  it('has warning icon', () => {
    const wsStore = useWebSocketStore()
    wsStore.$patch({ reconnectExhausted: true })

    const wrapper = mountBanner()
    const icon = wrapper.find('.pi-exclamation-triangle')
    expect(icon.exists()).toBe(true)
  })

  it('has a Reload button that calls window.location.reload', async () => {
    const wsStore = useWebSocketStore()
    wsStore.$patch({ reconnectExhausted: true })

    const reloadMock = vi.fn()
    Object.defineProperty(window, 'location', {
      value: { ...window.location, reload: reloadMock },
      writable: true,
    })

    const wrapper = mountBanner()
    const reloadBtn = wrapper.find('button')
    expect(reloadBtn.exists()).toBe(true)
    expect(reloadBtn.text()).toContain('Reload')
    await reloadBtn.trigger('click')
    expect(reloadMock).toHaveBeenCalledOnce()
  })

  it('uses amber warning styling', () => {
    const wsStore = useWebSocketStore()
    wsStore.$patch({ reconnectExhausted: true })

    const wrapper = mountBanner()
    const alert = wrapper.find('[role="alert"]')
    expect(alert.classes()).toContain('bg-amber-500/10')
    expect(alert.classes()).toContain('border-b')
  })
})
