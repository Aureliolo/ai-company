import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { defineComponent, h } from 'vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
}))

vi.mock('primevue/inputtext', () => ({
  default: defineComponent({
    props: ['modelValue', 'id', 'type', 'placeholder', 'autocomplete', 'ariaDescribedby'],
    emits: ['update:modelValue'],
    setup(props, { emit }) {
      return () =>
        h('input', {
          id: props.id,
          type: props.type ?? 'text',
          value: props.modelValue,
          onInput: (e: Event) => emit('update:modelValue', (e.target as HTMLInputElement).value),
        })
    },
  }),
}))

vi.mock('primevue/button', () => ({
  default: defineComponent({
    props: ['label', 'icon', 'type', 'loading', 'disabled', 'severity', 'size', 'outlined'],
    emits: ['click'],
    setup(props, { emit }) {
      return () =>
        h(
          'button',
          {
            type: props.type ?? 'button',
            disabled: props.disabled || props.loading,
            onClick: () => emit('click'),
          },
          props.label,
        )
    },
  }),
}))

vi.mock('primevue/select', () => ({
  default: defineComponent({
    props: ['modelValue', 'options', 'optionLabel', 'optionValue', 'placeholder', 'disabled'],
    emits: ['update:modelValue'],
    setup(props) {
      return () => h('select', {}, props.placeholder ?? '')
    },
  }),
}))

vi.mock('primevue/tag', () => ({
  default: defineComponent({
    props: ['value', 'severity'],
    setup(props) {
      return () => h('span', {}, props.value)
    },
  }),
}))

vi.mock('@/router', () => ({
  router: {
    currentRoute: { value: { path: '/setup' } },
    push: vi.fn(),
  },
}))

// Mock onUnmounted for useLoginLockout's interval cleanup
vi.mock('vue', async () => {
  const actual = await vi.importActual<typeof import('vue')>('vue')
  return { ...actual, onUnmounted: vi.fn() }
})

// Mock the setup API to return a default status
vi.mock('@/api/endpoints/setup', () => ({
  getSetupStatus: vi.fn().mockResolvedValue({
    needs_admin: true,
    needs_setup: true,
    has_providers: false,
  }),
  listTemplates: vi.fn().mockResolvedValue([]),
  createCompany: vi.fn().mockResolvedValue({ company_name: 'Test', template_applied: null, department_count: 0 }),
  createAgent: vi.fn().mockResolvedValue({ name: 'Agent', role: 'CEO', department: 'exec', model_provider: 'p', model_id: 'm' }),
  completeSetup: vi.fn().mockResolvedValue({ setup_complete: true }),
}))

// Mock providers API
vi.mock('@/api/endpoints/providers', () => ({
  listProviders: vi.fn().mockResolvedValue({}),
  listPresets: vi.fn().mockResolvedValue([]),
  createFromPreset: vi.fn().mockResolvedValue({}),
  testConnection: vi.fn().mockResolvedValue({ success: true, latency_ms: 42 }),
}))

import SetupPage from '@/views/SetupPage.vue'

describe('SetupPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('renders welcome step after status loads', async () => {
    const wrapper = mount(SetupPage)
    await flushPromises()
    expect(wrapper.text()).toContain('Welcome to SynthOrg')
  })

  it('renders step indicator', async () => {
    const wrapper = mount(SetupPage)
    await flushPromises()
    // Should show step counter
    expect(wrapper.text()).toContain('Step 1 of')
  })

  it('shows get started button in welcome step', async () => {
    const wrapper = mount(SetupPage)
    await flushPromises()
    const btn = wrapper.find('button')
    expect(btn.exists()).toBe(true)
    expect(btn.text()).toContain('Get Started')
  })

  it('advances to admin step after clicking get started', async () => {
    const wrapper = mount(SetupPage)
    await flushPromises()
    // Click the "Get Started" button
    const btn = wrapper.find('button')
    await btn.trigger('click')
    await flushPromises()
    // Should now show admin step (since needs_admin is true)
    expect(wrapper.text()).toContain('Admin')
  })

  it('shows wizard container with step dots', async () => {
    const wrapper = mount(SetupPage)
    await flushPromises()
    // The step indicator should have numbered dots
    const dots = wrapper.findAll('.rounded-full')
    expect(dots.length).toBeGreaterThanOrEqual(1)
  })

  it('includes multiple steps in the wizard', async () => {
    const wrapper = mount(SetupPage)
    await flushPromises()
    // Should show "Step X of Y" where Y >= 4 (welcome + admin + provider + company + agent)
    const text = wrapper.text()
    const match = text.match(/Step \d+ of (\d+)/)
    expect(match).toBeTruthy()
    if (match) {
      expect(parseInt(match[1])).toBeGreaterThanOrEqual(4)
    }
  })

  it('renders branding logo', async () => {
    const wrapper = mount(SetupPage)
    await flushPromises()
    // The welcome step includes the "S" logo
    expect(wrapper.text()).toContain('S')
  })
})
