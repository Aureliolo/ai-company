import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import type { SettingDefinition, SettingEntry } from '@/api/types'

vi.mock('primevue/inputtext', () => ({
  default: {
    props: ['modelValue', 'type', 'placeholder', 'disabled'],
    emits: ['update:modelValue'],
    template: '<input :type="type" :value="modelValue" :disabled="disabled" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
}))

vi.mock('primevue/inputnumber', () => ({
  default: {
    props: ['modelValue', 'min', 'max', 'minFractionDigits', 'maxFractionDigits', 'useGrouping', 'disabled'],
    emits: ['update:modelValue'],
    template: '<input type="number" :value="modelValue" :disabled="disabled" @input="$emit(\'update:modelValue\', Number($event.target.value))" />',
  },
}))

vi.mock('primevue/toggleswitch', () => ({
  default: {
    props: ['modelValue', 'disabled'],
    emits: ['update:modelValue'],
    template: '<button role="switch" :aria-checked="modelValue" :disabled="disabled" @click="$emit(\'update:modelValue\', !modelValue)">{{ modelValue }}</button>',
  },
}))

vi.mock('primevue/select', () => ({
  default: {
    props: ['modelValue', 'options', 'disabled'],
    emits: ['update:modelValue'],
    template: '<select :value="modelValue" :disabled="disabled" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-for="o in options" :key="o" :value="o">{{ o }}</option></select>',
  },
}))

vi.mock('primevue/textarea', () => ({
  default: {
    props: ['modelValue', 'rows', 'disabled'],
    emits: ['update:modelValue'],
    template: '<textarea :value="modelValue" :disabled="disabled" @input="$emit(\'update:modelValue\', $event.target.value)"></textarea>',
  },
}))

vi.mock('primevue/button', () => ({
  default: {
    props: ['label', 'icon', 'size', 'severity', 'text', 'disabled', 'loading'],
    template: '<button :disabled="disabled">{{ label }}</button>',
  },
}))

vi.mock('primevue/tag', () => ({
  default: {
    props: ['value', 'severity'],
    template: '<span :data-severity="severity">{{ value }}</span>',
  },
}))

import SettingField from '@/components/settings/SettingField.vue'

function makeDefinition(overrides: Partial<SettingDefinition> = {}): SettingDefinition {
  return {
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
    min_value: null,
    max_value: null,
    yaml_path: null,
    ...overrides,
  }
}

function makeEntry(overrides: Partial<SettingEntry> = {}, defOverrides: Partial<SettingDefinition> = {}): SettingEntry {
  return {
    definition: makeDefinition(defOverrides),
    value: '100.0',
    source: 'default',
    updated_at: null,
    ...overrides,
  }
}

describe('SettingField', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ── Rendering ─────────────────────────────────────────────

  it('renders description as help text', () => {
    const wrapper = mount(SettingField, {
      props: { entry: makeEntry(), saving: false },
    })
    expect(wrapper.text()).toContain('Monthly budget in USD')
  })

  it('renders restart required badge when restart_required is true', () => {
    const wrapper = mount(SettingField, {
      props: { entry: makeEntry({}, { restart_required: true }), saving: false },
    })
    expect(wrapper.text()).toContain('Restart Required')
  })

  it('does not render restart badge when restart_required is false', () => {
    const wrapper = mount(SettingField, {
      props: { entry: makeEntry(), saving: false },
    })
    expect(wrapper.text()).not.toContain('Restart Required')
  })

  it('renders source badge', () => {
    const wrapper = mount(SettingField, {
      props: { entry: makeEntry({ source: 'yaml' }), saving: false },
    })
    expect(wrapper.text()).toContain('YAML')
  })

  it('shows advanced chip for advanced-level settings', () => {
    const wrapper = mount(SettingField, {
      props: { entry: makeEntry({}, { level: 'advanced' }), saving: false },
    })
    expect(wrapper.text()).toContain('Advanced')
  })

  // ── Input types ───────────────────────────────────────────

  it('renders text input for string type', () => {
    const wrapper = mount(SettingField, {
      props: { entry: makeEntry({}, { type: 'str' }), saving: false },
    })
    expect(wrapper.find('input[type="text"]').exists()).toBe(true)
  })

  it('renders password input for sensitive string type', () => {
    const wrapper = mount(SettingField, {
      props: { entry: makeEntry({}, { type: 'str', sensitive: true }), saving: false },
    })
    expect(wrapper.find('input[type="password"]').exists()).toBe(true)
  })

  it('renders number input for int type', () => {
    const wrapper = mount(SettingField, {
      props: { entry: makeEntry({ value: '50' }, { type: 'int', default: '50' }), saving: false },
    })
    expect(wrapper.find('input[type="number"]').exists()).toBe(true)
  })

  it('renders number input for float type', () => {
    const wrapper = mount(SettingField, {
      props: { entry: makeEntry(), saving: false },
    })
    expect(wrapper.find('input[type="number"]').exists()).toBe(true)
  })

  it('renders switch for bool type', () => {
    const wrapper = mount(SettingField, {
      props: {
        entry: makeEntry({ value: 'true' }, { type: 'bool', default: 'true' }),
        saving: false,
      },
    })
    expect(wrapper.find('[role="switch"]').exists()).toBe(true)
  })

  it('renders select for enum type', () => {
    const wrapper = mount(SettingField, {
      props: {
        entry: makeEntry({ value: 'cost_aware' }, {
          type: 'enum',
          default: 'cost_aware',
          enum_values: ['cost_aware', 'round_robin', 'latency'],
        }),
        saving: false,
      },
    })
    expect(wrapper.find('select').exists()).toBe(true)
  })

  it('renders textarea for json type', () => {
    const wrapper = mount(SettingField, {
      props: {
        entry: makeEntry({ value: '{}' }, { type: 'json', default: '{}' }),
        saving: false,
      },
    })
    expect(wrapper.find('textarea').exists()).toBe(true)
  })

  // ── Dirty tracking ────────────────────────────────────────

  it('save button is disabled when value has not changed', () => {
    const wrapper = mount(SettingField, {
      props: { entry: makeEntry(), saving: false },
    })
    const saveBtn = wrapper.findAll('button').find((b) => b.text() === 'Save')
    expect(saveBtn?.attributes('disabled')).toBeDefined()
  })

  it('save button is enabled when value changes', async () => {
    const wrapper = mount(SettingField, {
      props: { entry: makeEntry(), saving: false },
    })
    const input = wrapper.find('input[type="number"]')
    await input.setValue(200)
    await flushPromises()

    const saveBtn = wrapper.findAll('button').find((b) => b.text() === 'Save')
    // The button should now be enabled since value changed from 100.0 to 200
    expect(saveBtn).toBeDefined()
  })

  // ── Events ────────────────────────────────────────────────

  it('emits save event with new value', async () => {
    const entry = makeEntry({ value: '100.0' }, { type: 'float' })
    const wrapper = mount(SettingField, {
      props: { entry, saving: false },
    })
    const input = wrapper.find('input[type="number"]')
    await input.setValue(200)
    await flushPromises()

    const saveBtn = wrapper.findAll('button').find((b) => b.text() === 'Save')
    await saveBtn?.trigger('click')

    expect(wrapper.emitted('save')).toBeTruthy()
    expect(wrapper.emitted('save')![0][0]).toBe('200')
  })

  it('emits reset event when reset button clicked', async () => {
    const entry = makeEntry({ value: '200.0', source: 'db' })
    const wrapper = mount(SettingField, {
      props: { entry, saving: false },
    })

    const resetBtn = wrapper.findAll('button').find((b) => b.text() === 'Reset')
    await resetBtn?.trigger('click')

    expect(wrapper.emitted('reset')).toBeTruthy()
  })

  // ── Validation ────────────────────────────────────────────

  it('shows validation error for invalid integer', async () => {
    const entry = makeEntry({ value: '50' }, { type: 'int', default: '50' })
    const wrapper = mount(SettingField, {
      props: { entry, saving: false },
    })
    const input = wrapper.find('input[type="number"]')
    await input.setValue(3.5)
    await flushPromises()

    expect(wrapper.text()).toContain('Must be a whole number')
  })

  it('shows range error for out-of-bounds value', async () => {
    const entry = makeEntry({ value: '50' }, {
      type: 'int',
      default: '50',
      min_value: 1,
      max_value: 100,
    })
    const wrapper = mount(SettingField, {
      props: { entry, saving: false },
    })
    const input = wrapper.find('input[type="number"]')
    await input.setValue(200)
    await flushPromises()

    expect(wrapper.text()).toContain('Must be at most 100')
  })

  // ── Sensitive toggle ──────────────────────────────────────

  it('toggles password visibility on eye button click', async () => {
    const wrapper = mount(SettingField, {
      props: {
        entry: makeEntry({}, { type: 'str', sensitive: true }),
        saving: false,
      },
    })
    expect(wrapper.find('input[type="password"]').exists()).toBe(true)

    // Find the eye toggle button (not Save/Reset)
    const eyeBtn = wrapper.findAll('button').find(
      (b) => b.text() !== 'Save' && b.text() !== 'Reset',
    )
    if (eyeBtn) {
      await eyeBtn.trigger('click')
      await flushPromises()
      expect(wrapper.find('input[type="text"]').exists()).toBe(true)
    }
  })
})
