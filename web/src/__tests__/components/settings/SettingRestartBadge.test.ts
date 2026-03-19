import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('primevue/tag', () => ({
  default: {
    props: ['value', 'severity'],
    template: '<span :data-severity="severity">{{ value }}</span>',
  },
}))

import SettingRestartBadge from '@/components/settings/SettingRestartBadge.vue'

describe('SettingRestartBadge', () => {
  it('renders restart required text', () => {
    const wrapper = mount(SettingRestartBadge)
    expect(wrapper.text()).toContain('Restart Required')
  })

  it('uses warn severity', () => {
    const wrapper = mount(SettingRestartBadge)
    expect(wrapper.find('[data-severity="warn"]').exists()).toBe(true)
  })
})
