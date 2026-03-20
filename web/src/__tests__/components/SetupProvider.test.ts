import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { defineComponent, h } from 'vue'
import type { ProviderConfig, ProviderPreset } from '@/api/types'

// We mock the API module (not the Pinia store) intentionally: the store's
// actions are thin wrappers around these endpoints, so mocking at the API
// layer lets us verify the full component-to-store-to-API integration path.
// If the store ever refactors its internals, these tests will catch regressions.
vi.mock('@/api/endpoints/providers', () => ({
  listProviders: vi.fn().mockResolvedValue({}),
  listPresets: vi.fn().mockResolvedValue([]),
  testConnection: vi.fn().mockResolvedValue({ success: true, latency_ms: 42, error: null, model_tested: 'test-small-001' }),
  createFromPreset: vi.fn(),
  discoverModels: vi.fn(),
  probePreset: vi.fn().mockResolvedValue({ url: null, model_count: 0, candidates_tried: 0 }),
}))

import * as providersApi from '@/api/endpoints/providers'
import SetupProvider from '@/components/setup/SetupProvider.vue'

const ButtonStub = defineComponent({
  name: 'PvButton',
  props: ['label', 'icon', 'severity', 'size', 'outlined', 'text', 'disabled', 'loading', 'iconPos', 'type'],
  emits: ['click'],
  setup(props, { emit }) {
    return () =>
      h('button', { disabled: props.disabled, type: props.type, onClick: () => emit('click') }, props.label)
  },
})

const InputTextStub = defineComponent({
  name: 'PvInputText',
  props: ['modelValue', 'id', 'type', 'placeholder', 'class'],
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    return () =>
      h('input', {
        id: props.id,
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
  candidate_urls: ['http://host.docker.internal:11434', 'http://localhost:11434'],
  default_models: [],
}

const mockApiKeyPreset: ProviderPreset = {
  name: 'openrouter',
  display_name: 'OpenRouter',
  description: 'OpenRouter API',
  driver: 'litellm',
  auth_type: 'api_key',
  default_base_url: 'https://openrouter.ai/api/v1',
  candidate_urls: [],
  default_models: [],
}

function findButton(w: ReturnType<typeof mount>, label: string) {
  return w.findAll('button').find((b) => b.text().includes(label))
}

/** Mount SetupProvider with a pre-existing provider and presets loaded. */
function mountWithExistingProvider(
  provider: ProviderConfig = mockProvider,
  presets: ProviderPreset[] = [mockPreset],
) {
  vi.mocked(providersApi.listProviders).mockResolvedValue({ 'test-provider': provider })
  vi.mocked(providersApi.listPresets).mockResolvedValue(presets)
  return mount(SetupProvider, { global: { stubs: globalStubs } })
}

describe('SetupProvider', () => {
  let wrapper: ReturnType<typeof mount> | undefined

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
    // Re-establish factory defaults after resetAllMocks clears implementations
    vi.mocked(providersApi.listProviders).mockResolvedValue({})
    vi.mocked(providersApi.listPresets).mockResolvedValue([])
    vi.mocked(providersApi.testConnection).mockResolvedValue({ success: true, latency_ms: 42, error: null, model_tested: 'test-small-001' })
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
  })

  describe('auto-test on mount', () => {
    it('triggers connection test when existing provider has models', async () => {
      wrapper = mountWithExistingProvider()
      await flushPromises()

      expect(providersApi.testConnection).toHaveBeenCalledWith('test-provider', undefined)
    })

    it('enables Next button when auto-test succeeds', async () => {
      wrapper = mountWithExistingProvider()
      await flushPromises()

      const nextBtn = findButton(wrapper, 'Next')
      expect(nextBtn?.exists()).toBe(true)
      expect(nextBtn!.attributes('disabled')).toBeUndefined()
    })

    it('disables Next button when auto-test fails', async () => {
      vi.mocked(providersApi.testConnection).mockResolvedValue({
        success: false,
        latency_ms: null,
        error: 'Connection refused',
        model_tested: null,
      })

      wrapper = mountWithExistingProvider()
      await flushPromises()

      const nextBtn = findButton(wrapper, 'Next')
      expect(nextBtn?.exists()).toBe(true)
      expect(nextBtn!.attributes('disabled')).toBe('')
    })

    it('shows error when auto-test fails', async () => {
      vi.mocked(providersApi.testConnection).mockResolvedValue({
        success: false,
        latency_ms: null,
        error: 'Connection refused',
        model_tested: null,
      })

      wrapper = mountWithExistingProvider()
      await flushPromises()

      expect(wrapper.text()).toContain('Connection refused')
    })

    it('handles auto-test network error gracefully', async () => {
      vi.mocked(providersApi.testConnection).mockRejectedValue(new Error('Network error'))

      wrapper = mountWithExistingProvider()
      await flushPromises()

      expect(wrapper.text()).toContain('Network error')
      const nextBtn = findButton(wrapper, 'Next')
      expect(nextBtn).toBeTruthy()
      expect(nextBtn!.attributes('disabled')).toBe('')
    })

    it('does not auto-test when no existing providers', async () => {
      vi.mocked(providersApi.listProviders).mockResolvedValue({})
      vi.mocked(providersApi.listPresets).mockResolvedValue([mockPreset])

      wrapper = mount(SetupProvider, { global: { stubs: globalStubs } })
      await flushPromises()

      expect(providersApi.testConnection).not.toHaveBeenCalled()
    })

    it('does not auto-test when provider has no models', async () => {
      wrapper = mountWithExistingProvider(mockProviderNoModels)
      await flushPromises()

      expect(providersApi.testConnection).not.toHaveBeenCalled()
    })
  })

  describe('preset selection and form', () => {
    it('shows preset cards when no provider exists', async () => {
      vi.mocked(providersApi.listProviders).mockResolvedValue({})
      vi.mocked(providersApi.listPresets).mockResolvedValue([mockPreset, mockApiKeyPreset])

      wrapper = mount(SetupProvider, { global: { stubs: globalStubs } })
      await flushPromises()

      expect(wrapper.text()).toContain('Ollama')
      expect(wrapper.text()).toContain('OpenRouter')
    })

    it('shows configuration form after selecting a preset', async () => {
      vi.mocked(providersApi.listProviders).mockResolvedValue({})
      vi.mocked(providersApi.listPresets).mockResolvedValue([mockPreset])

      wrapper = mount(SetupProvider, { global: { stubs: globalStubs } })
      await flushPromises()

      // Click on the preset card button
      const presetBtn = wrapper.findAll('button').find((b) => b.text().includes('Ollama'))
      expect(presetBtn).toBeTruthy()
      await presetBtn!.trigger('click')

      expect(wrapper.text()).toContain('Configuring')
      expect(wrapper.text()).toContain('Provider Name')
      expect(wrapper.text()).toContain('Add Provider')
    })

    it('disables Add Provider when name is empty', async () => {
      vi.mocked(providersApi.listProviders).mockResolvedValue({})
      vi.mocked(providersApi.listPresets).mockResolvedValue([mockApiKeyPreset])

      wrapper = mount(SetupProvider, { global: { stubs: globalStubs } })
      await flushPromises()

      // Select preset
      const presetBtn = wrapper.findAll('button').find((b) => b.text().includes('OpenRouter'))
      expect(presetBtn).toBeTruthy()
      await presetBtn!.trigger('click')

      // Clear the name field (auto-filled from preset)
      const nameInput = wrapper.find('#sp-name')
      await nameInput.setValue('')

      const addBtn = findButton(wrapper, 'Add Provider')
      expect(addBtn).toBeTruthy()
      expect(addBtn!.attributes('disabled')).toBe('')
    })
  })

  describe('model discovery', () => {
    it('passes preset name as hint when discovering models after creation', async () => {
      vi.mocked(providersApi.listProviders).mockResolvedValue({})
      vi.mocked(providersApi.listPresets).mockResolvedValue([mockPreset])
      vi.mocked(providersApi.createFromPreset).mockResolvedValue(mockProvider)
      vi.mocked(providersApi.discoverModels).mockResolvedValue({
        discovered_models: mockProvider.models,
        provider_name: 'ollama',
      })

      wrapper = mount(SetupProvider, { global: { stubs: globalStubs } })
      await flushPromises()

      // Select the Ollama preset (triggers async auto-probe)
      const presetBtn = wrapper.findAll('button').find((b) => b.text().includes('Ollama'))
      expect(presetBtn).toBeTruthy()
      await presetBtn!.trigger('click')
      await flushPromises()

      // Submit the form (triggers create + discover)
      const form = wrapper.find('form')
      expect(form.exists()).toBe(true)
      await form.trigger('submit')
      await flushPromises()

      expect(providersApi.discoverModels).toHaveBeenCalledWith('ollama', 'ollama')
    })
  })

  describe('navigation events', () => {
    it('emits next when Next button is clicked and canProceed is true', async () => {
      vi.mocked(providersApi.testConnection).mockResolvedValue({
        success: true,
        latency_ms: 42,
        error: null,
        model_tested: 'test-small-001',
      })

      wrapper = mountWithExistingProvider()
      await flushPromises()

      const nextBtn = findButton(wrapper, 'Next')
      expect(nextBtn).toBeTruthy()
      expect(nextBtn!.attributes('disabled')).toBeUndefined()
      await nextBtn!.trigger('click')

      expect(wrapper.emitted('next')).toBeTruthy()
    })

    it('emits previous when Back button is clicked', async () => {
      vi.mocked(providersApi.listProviders).mockResolvedValue({})
      vi.mocked(providersApi.listPresets).mockResolvedValue([mockPreset])

      wrapper = mount(SetupProvider, { global: { stubs: globalStubs } })
      await flushPromises()

      const backBtn = findButton(wrapper, 'Back')
      expect(backBtn).toBeTruthy()
      await backBtn!.trigger('click')

      expect(wrapper.emitted('previous')).toBeTruthy()
    })
  })
})
