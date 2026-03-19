import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('primevue/tag', () => ({
  default: {
    props: ['value', 'severity'],
    template: '<span :data-severity="severity">{{ value }}</span>',
  },
}))

import SettingSourceBadge from '@/components/settings/SettingSourceBadge.vue'

describe('SettingSourceBadge', () => {
  it.each([
    ['db', 'Database', 'info'],
    ['env', 'Environment', 'warn'],
    ['yaml', 'YAML', 'secondary'],
    ['default', 'Default', 'contrast'],
  ] as const)('renders %s source with label "%s" and severity "%s"', (source, label, severity) => {
    const wrapper = mount(SettingSourceBadge, { props: { source } })
    expect(wrapper.text()).toContain(label)
    expect(wrapper.find(`[data-severity="${severity}"]`).exists()).toBe(true)
  })
})
