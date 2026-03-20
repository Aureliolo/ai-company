import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
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

vi.mock('primevue/textarea', () => ({
  default: defineComponent({
    props: ['modelValue', 'id', 'rows', 'placeholder'],
    emits: ['update:modelValue'],
    setup(props, { emit }) {
      return () =>
        h('textarea', {
          id: props.id,
          value: props.modelValue,
          onInput: (e: Event) => emit('update:modelValue', (e.target as HTMLTextAreaElement).value),
        })
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
    has_company: false,
    has_agents: false,
    min_password_length: 12,
  }),
  listTemplates: vi.fn().mockResolvedValue([]),
  createCompany: vi.fn().mockResolvedValue({ company_name: 'Test', description: null, template_applied: null, department_count: 0 }),
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
  let wrapper: VueWrapper | undefined

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    localStorage.clear()
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
  })

  it('renders welcome step after status loads', async () => {
    wrapper = mount(SetupPage)
    await flushPromises()
    expect(wrapper.text()).toContain('Welcome to SynthOrg')
  })

  it('renders step indicator', async () => {
    wrapper = mount(SetupPage)
    await flushPromises()
    // Should show step counter
    expect(wrapper.text()).toContain('Step 1 of')
  })

  it('shows get started button in welcome step', async () => {
    wrapper = mount(SetupPage)
    await flushPromises()
    const btn = wrapper.find('button')
    expect(btn.exists()).toBe(true)
    expect(btn.text()).toContain('Get Started')
  })

  it('advances to admin step after clicking get started', async () => {
    wrapper = mount(SetupPage)
    await flushPromises()
    // Click the "Get Started" button
    const btn = wrapper.find('button')
    await btn.trigger('click')
    await flushPromises()
    // Should now show admin step (since needs_admin is true)
    expect(wrapper.text()).toContain('Admin')
  })

  it('shows wizard container with step dots', async () => {
    wrapper = mount(SetupPage)
    await flushPromises()
    // The step indicator should have numbered dots
    const dots = wrapper.findAll('[data-testid="step-indicator"]')
    expect(dots.length).toBeGreaterThanOrEqual(1)
  })

  it('includes multiple steps in the wizard', async () => {
    wrapper = mount(SetupPage)
    await flushPromises()
    // Should show "Step X of Y" where Y >= 4 (welcome + admin + provider + company + agent)
    const text = wrapper.text()
    const match = text.match(/Step \d+ of (\d+)/)
    expect(match).toBeTruthy()
    if (match) {
      expect(parseInt(match[1])).toBeGreaterThanOrEqual(4)
    }
  })

  it('step indicators always show numbers, never empty dots', async () => {
    wrapper = mount(SetupPage)
    await flushPromises()
    const dots = wrapper.findAll('[data-testid="step-indicator"]')
    expect(dots.length).toBeGreaterThanOrEqual(1)
    for (let i = 0; i < dots.length; i++) {
      expect(dots[i].text()).toBe(String(i + 1))
    }
  })

  it('current step shows current styling, not done styling', async () => {
    wrapper = mount(SetupPage)
    await flushPromises()
    // Step 1 is current (index 0)
    const dots = wrapper.findAll('[data-testid="step-indicator"]')
    expect(dots.length).toBeGreaterThanOrEqual(1)
    // Current step should have border-2 (current), not bg-brand-600 (done)
    expect(dots[0].classes()).toContain('border-2')
    expect(dots[0].classes()).not.toContain('bg-brand-600')
  })

  it('current step has role="button" and tabindex for keyboard access', async () => {
    wrapper = mount(SetupPage)
    await flushPromises()
    const dots = wrapper.findAll('[data-testid="step-indicator"]')
    expect(dots.length).toBeGreaterThanOrEqual(1)
    // Current step (index 0) should be keyboard-accessible
    expect(dots[0].attributes('role')).toBe('button')
    expect(dots[0].attributes('tabindex')).toBe('0')
  })

  it('future incomplete steps do not have role="button"', async () => {
    wrapper = mount(SetupPage)
    await flushPromises()
    const dots = wrapper.findAll('[data-testid="step-indicator"]')
    // Precondition: multiple steps must exist so the last is a true future step
    expect(dots.length).toBeGreaterThan(1)
    // Last step (incomplete, not current) should not be interactive
    const lastDot = dots[dots.length - 1]
    expect(lastDot.attributes('role')).toBeUndefined()
    expect(lastDot.attributes('tabindex')).toBeUndefined()
  })

  it('renders branding logo', async () => {
    wrapper = mount(SetupPage)
    await flushPromises()
    // The welcome step renders the branded "S" logo inside a styled container
    const logo = wrapper.find('[data-testid="brand-logo"]')
    expect(logo.exists()).toBe(true)
    expect(logo.text()).toBe('S')
  })
})
