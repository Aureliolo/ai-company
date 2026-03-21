import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import type { SettingDefinition, SettingEntry } from '@/api/types'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), go: vi.fn() }),
  useRoute: () => ({ params: {}, query: {} }),
  RouterLink: { template: '<a><slot /></a>' },
  createRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    go: vi.fn(),
    beforeEach: vi.fn(),
    currentRoute: { value: { path: '/' } },
  }),
  createWebHistory: vi.fn(),
}))

vi.mock('primevue/usetoast', () => ({
  useToast: () => ({ add: vi.fn() }),
}))

vi.mock('primevue/tabs', () => ({
  default: {
    props: ['value'],
    emits: ['update:value'],
    template: '<div data-testid="tabs"><slot /></div>',
  },
}))

vi.mock('primevue/tablist', () => ({
  default: { template: '<div><slot /></div>' },
}))

vi.mock('primevue/tab', () => ({
  default: {
    props: ['value', 'disabled'],
    template: '<div :data-tab-header="value"><slot /></div>',
  },
}))

vi.mock('primevue/tabpanels', () => ({
  default: { template: '<div><slot /></div>' },
}))

vi.mock('primevue/tabpanel', () => ({
  default: {
    props: ['value'],
    template: '<div :data-tab="value"><slot /></div>',
  },
}))

vi.mock('primevue/inputtext', () => ({
  default: {
    props: ['modelValue', 'type', 'placeholder'],
    template: '<input :type="type" />',
  },
}))

vi.mock('primevue/password', () => ({
  default: {
    props: ['modelValue', 'inputId', 'toggleMask', 'feedback', 'placeholder', 'fluid', 'disabled', 'inputProps'],
    emits: ['update:modelValue'],
    template: '<input :id="inputId" type="password" />',
  },
}))

vi.mock('primevue/button', () => ({
  default: {
    props: ['label', 'icon', 'type', 'size', 'loading', 'disabled', 'severity', 'text'],
    template: '<button :disabled="disabled">{{ label }}</button>',
  },
}))

vi.mock('primevue/toggleswitch', () => ({
  default: {
    props: ['modelValue', 'disabled'],
    emits: ['update:modelValue'],
    template: '<button role="switch">{{ modelValue }}</button>',
  },
}))

vi.mock('primevue/inputnumber', () => ({
  default: {
    props: ['modelValue', 'min', 'max', 'minFractionDigits', 'maxFractionDigits', 'useGrouping', 'disabled'],
    template: '<input type="number" />',
  },
}))

vi.mock('primevue/select', () => ({
  default: {
    props: ['modelValue', 'options', 'disabled'],
    template: '<select></select>',
  },
}))

vi.mock('primevue/textarea', () => ({
  default: {
    props: ['modelValue', 'rows', 'disabled'],
    template: '<textarea></textarea>',
  },
}))

vi.mock('primevue/tag', () => ({
  default: {
    props: ['value', 'severity'],
    template: '<span>{{ value }}</span>',
  },
}))

vi.mock('@/components/layout/AppShell.vue', () => ({
  default: { template: '<div><slot /></div>' },
}))

vi.mock('@/components/common/PageHeader.vue', () => ({
  default: {
    props: ['title', 'subtitle'],
    template: '<div><h1>{{ title }}</h1><p>{{ subtitle }}</p><slot name="actions" /></div>',
  },
}))

vi.mock('@/components/common/LoadingSkeleton.vue', () => ({
  default: {
    props: ['lines'],
    template: '<div data-testid="loading-skeleton">Loading...</div>',
  },
}))

vi.mock('@/components/common/ErrorBoundary.vue', () => ({
  default: {
    props: ['error'],
    template: '<div><slot /></div>',
  },
}))

vi.mock('@/api/endpoints/company', () => ({
  getCompanyConfig: vi.fn().mockResolvedValue({
    company_name: 'Test Corp',
    agents: [{ name: 'alice', role: 'Developer' }],
  }),
  listDepartments: vi.fn().mockResolvedValue({ data: [], total: 0 }),
  getDepartment: vi.fn(),
}))

vi.mock('@/api/endpoints/providers', () => ({
  listProviders: vi.fn().mockResolvedValue({}),
  getProvider: vi.fn(),
  getProviderModels: vi.fn(),
  listPresets: vi.fn().mockResolvedValue([]),
  createFromPreset: vi.fn(),
}))

vi.mock('@/api/endpoints/auth', () => ({
  getMe: vi.fn(),
  login: vi.fn(),
  setup: vi.fn(),
  changePassword: vi.fn(),
}))

const budgetDef: SettingDefinition = {
  namespace: 'budget',
  key: 'total_monthly',
  type: 'float',
  default: '100.0',
  description: 'Monthly budget in USD',
  group: 'Limits',
  level: 'basic',
  sensitive: false,
  restart_required: false,
  enum_values: [],
  validator_pattern: null,
  min_value: 0.0,
  max_value: null,
  yaml_path: 'budget.total_monthly',
}

const securityDef: SettingDefinition = {
  namespace: 'security',
  key: 'enabled',
  type: 'bool',
  default: 'true',
  description: 'Enable security engine',
  group: 'General',
  level: 'basic',
  sensitive: false,
  restart_required: false,
  enum_values: [],
  validator_pattern: null,
  min_value: null,
  max_value: null,
  yaml_path: null,
}

const budgetEntry: SettingEntry = {
  definition: budgetDef,
  value: '100.0',
  source: 'default',
  updated_at: null,
}

const securityEntry: SettingEntry = {
  definition: securityDef,
  value: 'true',
  source: 'yaml',
  updated_at: null,
}

vi.mock('@/api/endpoints/settings', () => ({
  getSchema: vi.fn(),
  getAllSettings: vi.fn(),
  updateSetting: vi.fn(),
  resetSetting: vi.fn(),
}))

import SettingsPage from '@/views/SettingsPage.vue'

describe('SettingsPage (dynamic)', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    localStorage.clear()

    // Configure mock return values here (not in factory, since variables aren't available there)
    const settingsApi = await import('@/api/endpoints/settings')
    vi.mocked(settingsApi.getSchema).mockResolvedValue([budgetDef, securityDef])
    vi.mocked(settingsApi.getAllSettings).mockResolvedValue([budgetEntry, securityEntry])
  })

  it('renders Settings heading', () => {
    const wrapper = mount(SettingsPage)
    expect(wrapper.find('h1').text()).toBe('Settings')
  })

  it('shows loading skeleton initially', () => {
    const wrapper = mount(SettingsPage)
    expect(wrapper.find('[data-testid="loading-skeleton"]').exists()).toBe(true)
  })

  it('fetches settings schema and entries on mount', async () => {
    const settingsApi = await import('@/api/endpoints/settings')
    mount(SettingsPage)
    await flushPromises()
    expect(settingsApi.getSchema).toHaveBeenCalled()
    expect(settingsApi.getAllSettings).toHaveBeenCalled()
  })

  it('renders dynamic namespace tabs after loading', async () => {
    const wrapper = mount(SettingsPage)
    await flushPromises()

    // Should have tabs for budget, security, providers, and user
    const tabs = wrapper.findAll('[data-tab]')
    const tabValues = tabs.map((t) => t.attributes('data-tab'))
    expect(tabValues).toContain('budget')
    expect(tabValues).toContain('security')
    expect(tabValues).toContain('providers')
    expect(tabValues).toContain('user')
  })

  it('renders setting fields inside namespace tabs', async () => {
    const wrapper = mount(SettingsPage)
    await flushPromises()

    expect(wrapper.text()).toContain('total_monthly')
    expect(wrapper.text()).toContain('Monthly budget in USD')
  })

  it('preserves user tab with password change form', async () => {
    const wrapper = mount(SettingsPage)
    await flushPromises()

    expect(wrapper.text()).toContain('Change Password')
  })

  it('renders basic/advanced toggle', async () => {
    const wrapper = mount(SettingsPage)
    await flushPromises()

    // The toggle switch should be rendered in the header actions slot
    expect(wrapper.find('[role="switch"]').exists()).toBe(true)
  })
})
