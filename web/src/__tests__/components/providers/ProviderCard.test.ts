import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ProviderCard from '@/components/providers/ProviderCard.vue'
import type { ProviderConfig } from '@/api/types'

vi.mock('@/api/endpoints/providers', () => ({
  listProviders: vi.fn(),
  listPresets: vi.fn(),
  testConnection: vi.fn(),
}))

const mockConfig: ProviderConfig = {
  driver: 'litellm',
  auth_type: 'none',
  base_url: 'http://localhost:11434',
  models: [
    {
      id: 'test-model-001',
      alias: 'medium',
      cost_per_1k_input: 0,
      cost_per_1k_output: 0,
      max_context: 200000,
      estimated_latency_ms: null,
    },
  ],
  has_api_key: false,
  has_oauth_credentials: false,
  has_custom_header: false,
  oauth_token_url: null,
  oauth_client_id: null,
  oauth_scope: null,
  custom_header_name: null,
}

describe('ProviderCard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it.each([
    ['provider name', 'test-provider'],
    ['driver badge', 'litellm'],
    ['auth type badge', 'none'],
    ['model count', '1 model'],
    ['base url', 'http://localhost:11434'],
  ])('renders %s', (_label, expected) => {
    const wrapper = mount(ProviderCard, {
      props: { name: 'test-provider', config: mockConfig },
    })
    expect(wrapper.text()).toContain(expected)
  })

  it('emits edit event', async () => {
    const wrapper = mount(ProviderCard, {
      props: { name: 'test-provider', config: mockConfig },
    })
    const editBtn = wrapper.findAll('button').find(b => b.text().includes('Edit'))
    expect(editBtn).toBeDefined()
    await editBtn!.trigger('click')
    expect(wrapper.emitted('edit')).toEqual([['test-provider']])
  })

  it('emits delete event after confirmation', async () => {
    const wrapper = mount(ProviderCard, {
      props: { name: 'test-provider', config: mockConfig },
    })
    const deleteBtn = wrapper.findAll('button').find(b => b.text().includes('Delete'))
    expect(deleteBtn).toBeDefined()
    await deleteBtn!.trigger('click')
    // First click shows confirmation
    const confirmBtn = wrapper.findAll('button').find(b => b.text().includes('Confirm'))
    expect(confirmBtn).toBeDefined()
    await confirmBtn!.trigger('click')
    expect(wrapper.emitted('delete')).toEqual([['test-provider']])
  })
})
