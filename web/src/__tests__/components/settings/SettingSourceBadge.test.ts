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
  it('renders the source label for db', () => {
    const wrapper = mount(SettingSourceBadge, { props: { source: 'db' } })
    expect(wrapper.text()).toContain('Database')
  })

  it('renders the source label for env', () => {
    const wrapper = mount(SettingSourceBadge, { props: { source: 'env' } })
    expect(wrapper.text()).toContain('Environment')
  })

  it('renders the source label for yaml', () => {
    const wrapper = mount(SettingSourceBadge, { props: { source: 'yaml' } })
    expect(wrapper.text()).toContain('YAML')
  })

  it('renders the source label for default', () => {
    const wrapper = mount(SettingSourceBadge, { props: { source: 'default' } })
    expect(wrapper.text()).toContain('Default')
  })

  it('applies info severity for db source', () => {
    const wrapper = mount(SettingSourceBadge, { props: { source: 'db' } })
    expect(wrapper.find('[data-severity="info"]').exists()).toBe(true)
  })

  it('applies warn severity for env source', () => {
    const wrapper = mount(SettingSourceBadge, { props: { source: 'env' } })
    expect(wrapper.find('[data-severity="warn"]').exists()).toBe(true)
  })

  it('applies secondary severity for yaml source', () => {
    const wrapper = mount(SettingSourceBadge, { props: { source: 'yaml' } })
    expect(wrapper.find('[data-severity="secondary"]').exists()).toBe(true)
  })

  it('applies contrast severity for default source', () => {
    const wrapper = mount(SettingSourceBadge, { props: { source: 'default' } })
    expect(wrapper.find('[data-severity="contrast"]').exists()).toBe(true)
  })
})
