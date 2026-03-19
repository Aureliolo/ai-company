import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import type { SettingDefinition, SettingEntry } from '@/api/types'

vi.mock('primevue/inputtext', () => ({
  default: {
    props: ['modelValue', 'type', 'placeholder', 'disabled'],
    emits: ['update:modelValue'],
    template: '<input :type="type" :value="modelValue" />',
  },
}))

vi.mock('primevue/inputnumber', () => ({
  default: {
    props: ['modelValue', 'min', 'max', 'minFractionDigits', 'maxFractionDigits', 'useGrouping', 'disabled'],
    emits: ['update:modelValue'],
    template: '<input type="number" :value="modelValue" />',
  },
}))

vi.mock('primevue/toggleswitch', () => ({
  default: {
    props: ['modelValue', 'disabled'],
    emits: ['update:modelValue'],
    template: '<button role="switch">{{ modelValue }}</button>',
  },
}))

vi.mock('primevue/select', () => ({
  default: {
    props: ['modelValue', 'options', 'disabled'],
    emits: ['update:modelValue'],
    template: '<select :value="modelValue"></select>',
  },
}))

vi.mock('primevue/textarea', () => ({
  default: {
    props: ['modelValue', 'rows', 'disabled'],
    emits: ['update:modelValue'],
    template: '<textarea :value="modelValue"></textarea>',
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
    template: '<span>{{ value }}</span>',
  },
}))

import SettingGroupRenderer from '@/components/settings/SettingGroupRenderer.vue'

function makeDef(overrides: Partial<SettingDefinition> = {}): SettingDefinition {
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

function makeEntry(defOverrides: Partial<SettingDefinition> = {}, entryOverrides: Partial<SettingEntry> = {}): SettingEntry {
  return {
    definition: makeDef(defOverrides),
    value: defOverrides.default ?? '100.0',
    source: 'default',
    updated_at: null,
    ...entryOverrides,
  }
}

function basicLimits() {
  return makeEntry({ key: 'total_monthly', group: 'Limits' })
}

function basicLimits2() {
  return makeEntry({ key: 'per_task_limit', group: 'Limits', default: '5.0' }, { value: '5.0' })
}

function advancedAlerts() {
  return makeEntry({
    key: 'alert_warn_at',
    group: 'Alerts',
    level: 'advanced',
    type: 'int',
    default: '75',
  }, { value: '75' })
}

function advancedDowngrade() {
  return makeEntry({
    key: 'auto_downgrade_enabled',
    group: 'Auto-Downgrade',
    level: 'advanced',
    type: 'bool',
    default: 'false',
  }, { value: 'false' })
}

describe('SettingGroupRenderer', () => {
  it('renders group headings', () => {
    const wrapper = mount(SettingGroupRenderer, {
      props: {
        entries: [basicLimits(), basicLimits2()],
        showAdvanced: false,
      },
    })
    expect(wrapper.text()).toContain('Limits')
  })

  it('renders multiple groups when entries span groups', () => {
    const wrapper = mount(SettingGroupRenderer, {
      props: {
        entries: [basicLimits(), advancedAlerts()],
        showAdvanced: true,
      },
    })
    expect(wrapper.text()).toContain('Limits')
    expect(wrapper.text()).toContain('Alerts')
  })

  it('filters out advanced settings when showAdvanced is false', () => {
    const wrapper = mount(SettingGroupRenderer, {
      props: {
        entries: [basicLimits(), advancedAlerts()],
        showAdvanced: false,
      },
    })
    expect(wrapper.text()).toContain('total_monthly')
    expect(wrapper.text()).not.toContain('alert_warn_at')
  })

  it('shows advanced settings when showAdvanced is true', () => {
    const wrapper = mount(SettingGroupRenderer, {
      props: {
        entries: [basicLimits(), advancedAlerts()],
        showAdvanced: true,
      },
    })
    expect(wrapper.text()).toContain('total_monthly')
    expect(wrapper.text()).toContain('alert_warn_at')
  })

  it('hides group headings that have no visible settings in basic mode', () => {
    const wrapper = mount(SettingGroupRenderer, {
      props: {
        entries: [advancedAlerts(), advancedDowngrade()],
        showAdvanced: false,
      },
    })
    // Both entries are advanced, so nothing should render
    expect(wrapper.text()).not.toContain('Alerts')
    expect(wrapper.text()).not.toContain('Auto-Downgrade')
  })

  it('shows empty state when no entries provided', () => {
    const wrapper = mount(SettingGroupRenderer, {
      props: {
        entries: [],
        showAdvanced: false,
      },
    })
    expect(wrapper.text()).toContain('No settings')
  })

  it('emits save event from child SettingField', async () => {
    const entry = basicLimits()
    const wrapper = mount(SettingGroupRenderer, {
      props: {
        entries: [entry],
        showAdvanced: false,
      },
    })
    // Find the SettingField and trigger its save event
    const settingField = wrapper.findComponent({ name: 'SettingField' })
    settingField.vm.$emit('save', '200.0')

    expect(wrapper.emitted('save')).toBeTruthy()
    expect(wrapper.emitted('save')![0]).toEqual([entry, '200.0'])
  })

  it('emits reset event from child SettingField', async () => {
    const entry = basicLimits()
    const wrapper = mount(SettingGroupRenderer, {
      props: {
        entries: [entry],
        showAdvanced: false,
      },
    })
    const settingField = wrapper.findComponent({ name: 'SettingField' })
    settingField.vm.$emit('reset')

    expect(wrapper.emitted('reset')).toBeTruthy()
    expect(wrapper.emitted('reset')![0]).toEqual([entry])
  })
})
