import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { defineComponent, h } from 'vue'
import type { ProviderConfig, ProviderPreset, TestConnectionResponse } from '@/api/types'

vi.mock('@/api/endpoints/providers', () => ({
  listProviders: vi.fn().mockResolvedValue({}),
  listPresets: vi.fn().mockResolvedValue([]),
  testConnection: vi.fn().mockResolvedValue({
    success: true,
    latency_ms: 42,
    error: null,
    model_tested: 'test-small-001',
  }),
  createFromPreset: vi.fn(),
  discoverModels: vi.fn(),
}))

import * as providersApi from '@/api/endpoints/providers'
import SetupProvider from '@/components/setup/SetupProvider.vue'

const ButtonStub = defineComponent({
  name: 'PvButton',
  props: ['label', 'icon', 'severity', 'size', 'outlined', 'text', 'disabled', 'loading', 'iconPos'],
  emits: ['click'],
  setup(props, { emit }) {
    return () =>
      h('button', { disabled: props.disabled, onClick: () => emit('click') }, props.label)
  },
})

const InputTextStub = defineComponent({
  name: 'PvInputText',
  props: ['modelValue', 'id', 'type', 'placeholder', 'class'],
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    return () =>
      h('input', {
        value: props.modelValue,
        onInput: (e: Event) => emit('update:modelValue', (e.target as HTMLInputElement).value),
      })
  },
})

const TagStub = defineComponent({
  name: 'PvTag',
  props: ['value', 'severity', 'class'],
  setup(props) {
    return () => h('span', {}, props.value)
  },
})

const globalStubs = {
  Button: ButtonStub,
  InputText: InputTextStub,
  Tag: TagStub,
}

const mockProvider: ProviderConfig = {
  driver: 'litellm',
  auth_type: 'none',
  base_url: 'http://localhost:11434',
  models: [{ id: 'test-small-001', alias: null, cost_per_1k_input: 0, cost_per_1k_output: 0, max_context: 4096, estimated_latency_ms: null }],
  has_api_key: false,
  has_oauth_credentials: false,
  has_custom_header: false,
  oauth_token_url: null,
  oauth_client_id: null,
  oauth_scope: null,
  custom_header_name: null,
}

const mockProviderNoModels: ProviderConfig = {
  ...mockProvider,
  models: [],
}

const mockPreset: ProviderPreset = {
  name: 'ollama',
  display_name: 'Ollama',
  description: 'Local Ollama instance',
  driver: 'litellm',
  auth_type: 'none',
  default_base_url: 'http://localhost:11434',
  default_models: [],
}

describe('SetupProvider', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('auto-triggers connection test when existing provider has models', async () => {
    vi.mocked(providersApi.listProviders).mockResolvedValue({ 'test-provider': mockProvider })
    vi.mocked(providersApi.listPresets).mockResolvedValue([mockPreset])
    vi.mocked(providersApi.testConnection).mockResolvedValue({
      success: true,
      latency_ms: 42,
      error: null,
      model_tested: 'test-small-001',
    })

    mount(SetupProvider, { global: { stubs: globalStubs } })
    await flushPromises()

    expect(providersApi.testConnection).toHaveBeenCalledWith('test-provider', undefined)
  })

  it('enables Next button when auto-test succeeds', async () => {
    vi.mocked(providersApi.listProviders).mockResolvedValue({ 'test-provider': mockProvider })
    vi.mocked(providersApi.listPresets).mockResolvedValue([mockPreset])
    vi.mocked(providersApi.testConnection).mockResolvedValue({
      success: true,
      latency_ms: 42,
      error: null,
      model_tested: 'test-small-001',
    })

    const wrapper = mount(SetupProvider, { global: { stubs: globalStubs } })
    await flushPromises()

    const nextBtn = wrapper.findAll('button').find((b) => b.text().includes('Next'))
    expect(nextBtn).toBeDefined()
    expect(nextBtn!.attributes('disabled')).toBeUndefined()
  })

  it('disables Next button when auto-test fails', async () => {
    vi.mocked(providersApi.listProviders).mockResolvedValue({ 'test-provider': mockProvider })
    vi.mocked(providersApi.listPresets).mockResolvedValue([mockPreset])
    vi.mocked(providersApi.testConnection).mockResolvedValue({
      success: false,
      latency_ms: null,
      error: 'Connection refused',
      model_tested: null,
    })

    const wrapper = mount(SetupProvider, { global: { stubs: globalStubs } })
    await flushPromises()

    const nextBtn = wrapper.findAll('button').find((b) => b.text().includes('Next'))
    expect(nextBtn).toBeDefined()
    expect(nextBtn!.attributes('disabled')).toBe('')
  })

  it('shows error when auto-test fails', async () => {
    vi.mocked(providersApi.listProviders).mockResolvedValue({ 'test-provider': mockProvider })
    vi.mocked(providersApi.listPresets).mockResolvedValue([mockPreset])
    vi.mocked(providersApi.testConnection).mockResolvedValue({
      success: false,
      latency_ms: null,
      error: 'Connection refused',
      model_tested: null,
    })

    const wrapper = mount(SetupProvider, { global: { stubs: globalStubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Connection refused')
  })

  it('handles auto-test network error gracefully', async () => {
    vi.mocked(providersApi.listProviders).mockResolvedValue({ 'test-provider': mockProvider })
    vi.mocked(providersApi.listPresets).mockResolvedValue([mockPreset])
    vi.mocked(providersApi.testConnection).mockRejectedValue(new Error('Network error'))

    const wrapper = mount(SetupProvider, { global: { stubs: globalStubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Network error')
    const nextBtn = wrapper.findAll('button').find((b) => b.text().includes('Next'))
    expect(nextBtn!.attributes('disabled')).toBe('')
  })

  it('does not auto-test when no existing providers', async () => {
    vi.mocked(providersApi.listProviders).mockResolvedValue({})
    vi.mocked(providersApi.listPresets).mockResolvedValue([mockPreset])

    mount(SetupProvider, { global: { stubs: globalStubs } })
    await flushPromises()

    expect(providersApi.testConnection).not.toHaveBeenCalled()
  })

  it('does not auto-test when provider has no models', async () => {
    vi.mocked(providersApi.listProviders).mockResolvedValue({ 'test-provider': mockProviderNoModels })
    vi.mocked(providersApi.listPresets).mockResolvedValue([mockPreset])

    mount(SetupProvider, { global: { stubs: globalStubs } })
    await flushPromises()

    expect(providersApi.testConnection).not.toHaveBeenCalled()
  })
})
