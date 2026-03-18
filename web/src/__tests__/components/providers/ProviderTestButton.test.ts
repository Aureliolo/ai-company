import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ProviderTestButton from '@/components/providers/ProviderTestButton.vue'

vi.mock('@/api/endpoints/providers', () => ({
  listProviders: vi.fn(),
  listPresets: vi.fn(),
  testConnection: vi.fn().mockResolvedValue({
    success: true,
    latency_ms: 42.5,
    error: null,
    model_tested: 'test-model-001',
  }),
}))

describe('ProviderTestButton', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('renders test button', () => {
    const wrapper = mount(ProviderTestButton, {
      props: { providerName: 'test-provider' },
    })
    expect(wrapper.text()).toContain('Test')
  })

  it('calls test connection on click', async () => {
    const providersApi = await import('@/api/endpoints/providers')
    vi.mocked(providersApi.testConnection).mockResolvedValue({
      success: true,
      latency_ms: 42.5,
      error: null,
      model_tested: 'test-model-001',
    })

    const wrapper = mount(ProviderTestButton, {
      props: { providerName: 'test-provider' },
    })
    const btn = wrapper.find('button')
    await btn.trigger('click')
    // Wait for async
    await vi.dynamicImportSettled()
    expect(providersApi.testConnection).toHaveBeenCalledTimes(1)
    expect(vi.mocked(providersApi.testConnection).mock.calls[0]?.[0]).toBe('test-provider')
  })
})
