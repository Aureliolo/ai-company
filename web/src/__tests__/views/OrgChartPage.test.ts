import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { setActivePinia, createPinia } from 'pinia'

const mockRouterPush = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockRouterPush, go: vi.fn() }),
  useRoute: () => ({ params: {} }),
  RouterLink: {
    props: ['to'],
    template: '<a :href="to"><slot /></a>',
  },
}))

const mockFitView = vi.fn().mockResolvedValue(true)
vi.mock('@vue-flow/core', () => ({
  VueFlow: {
    name: 'VueFlow',
    props: ['nodes', 'edges', 'fitViewOnInit'],
    emits: ['node-click'],
    template: '<div data-testid="vue-flow"><slot /></div>',
  },
  useVueFlow: () => ({ fitView: mockFitView }),
}))

vi.mock('@vue-flow/controls', () => ({
  Controls: { template: '<div data-testid="controls">Controls</div>' },
}))

vi.mock('@vue-flow/minimap', () => ({
  MiniMap: { template: '<div data-testid="minimap">MiniMap</div>' },
}))

vi.mock('@/components/layout/AppShell.vue', () => ({
  default: { template: '<div><slot /></div>' },
}))

vi.mock('@/components/common/PageHeader.vue', () => ({
  default: {
    props: ['title', 'subtitle'],
    template: '<div><h1>{{ title }}</h1><p>{{ subtitle }}</p></div>',
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
    emits: ['retry'],
    template:
      '<div data-testid="error-boundary"><div v-if="error" data-testid="error-message">{{ error }}</div><slot v-else /></div>',
  },
}))

vi.mock('@/components/common/EmptyState.vue', () => ({
  default: {
    props: ['icon', 'title', 'message'],
    template:
      '<div data-testid="empty-state"><h3>{{ title }}</h3><p>{{ message }}</p><slot name="action" /></div>',
  },
}))

vi.mock('@/components/org-chart/OrgNode.vue', () => ({
  default: {
    props: ['data'],
    template: '<div data-testid="org-node">{{ data.label }}</div>',
  },
}))

vi.mock('@/api/endpoints/company', () => ({
  getCompanyConfig: vi.fn(),
  listDepartments: vi.fn().mockResolvedValue({ data: [], total: 0, offset: 0, limit: 200 }),
  getDepartment: vi.fn(),
}))

vi.mock('@/api/endpoints/agents', () => ({
  listAgents: vi.fn().mockResolvedValue({ data: [], total: 0, offset: 0, limit: 200 }),
  getAgent: vi.fn(),
  getAutonomy: vi.fn(),
  setAutonomy: vi.fn(),
}))

import OrgChartPage from '@/views/OrgChartPage.vue'
import { listDepartments } from '@/api/endpoints/company'
import { listAgents } from '@/api/endpoints/agents'

const MOCK_DEPARTMENTS = [
  {
    name: 'engineering' as const,
    display_name: 'Engineering',
    teams: [{ name: 'Backend', members: ['test-agent'] }],
  },
]

function mockWithDepartments() {
  vi.mocked(listDepartments).mockResolvedValue({
    data: MOCK_DEPARTMENTS,
    total: 1,
    offset: 0,
    limit: 200,
  })
}

describe('OrgChartPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    // Re-set default mocks (clearAllMocks only clears history, not implementations)
    vi.mocked(listDepartments).mockResolvedValue({ data: [], total: 0, offset: 0, limit: 200 })
    vi.mocked(listAgents).mockResolvedValue({ data: [], total: 0, offset: 0, limit: 200 })
    mockFitView.mockResolvedValue(true)
  })

  it('mounts without error', () => {
    const wrapper = mount(OrgChartPage)
    expect(wrapper.exists()).toBe(true)
  })

  it('renders "Organization Chart" heading', () => {
    const wrapper = mount(OrgChartPage)
    expect(wrapper.find('h1').text()).toBe('Organization Chart')
  })

  it('fetches departments and agents on mount', async () => {
    mount(OrgChartPage)
    await flushPromises()
    expect(listDepartments).toHaveBeenCalledWith(
      expect.objectContaining({ limit: expect.any(Number) }),
    )
    expect(listAgents).toHaveBeenCalledWith(
      expect.objectContaining({ limit: expect.any(Number) }),
    )
  })

  it('shows loading skeleton while fetching', async () => {
    vi.mocked(listDepartments).mockReturnValue(new Promise(() => {}))
    vi.mocked(listAgents).mockReturnValue(new Promise(() => {}))
    const wrapper = mount(OrgChartPage)
    await nextTick()
    expect(wrapper.find('[data-testid="loading-skeleton"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="empty-state"]').exists()).toBe(false)
  })

  it('shows empty state when no departments exist', async () => {
    const wrapper = mount(OrgChartPage)
    await flushPromises()
    expect(wrapper.find('[data-testid="empty-state"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="empty-state"] h3').text()).toBe('No departments')
    expect(wrapper.find('[data-testid="vue-flow"]').exists()).toBe(false)
  })

  it('empty state includes a link to /settings', async () => {
    const wrapper = mount(OrgChartPage)
    await flushPromises()
    const link = wrapper.find('[data-testid="empty-state"] a')
    expect(link.text()).toContain('Go to Settings')
    expect(link.attributes('href')).toBe('/settings')
  })

  describe('when departments exist', () => {
    let wrapper: ReturnType<typeof mount>

    beforeEach(async () => {
      mockWithDepartments()
      wrapper = mount(OrgChartPage)
      await flushPromises()
    })

    it('shows VueFlow and hides empty state', () => {
      expect(wrapper.find('[data-testid="vue-flow"]').exists()).toBe(true)
      expect(wrapper.find('[data-testid="empty-state"]').exists()).toBe(false)
    })

    it('renders controls and minimap', () => {
      expect(wrapper.find('[data-testid="controls"]').exists()).toBe(true)
      expect(wrapper.find('[data-testid="minimap"]').exists()).toBe(true)
    })

    it('calls fitView once after nodes populate', () => {
      expect(mockFitView).toHaveBeenCalledTimes(1)
    })

    it('navigates to /agents/{name} on agent node click', async () => {
      const vueFlow = wrapper.findComponent({ name: 'VueFlow' })
      vueFlow.vm.$emit('node-click', { node: { id: 'agent-test-agent' } })
      await nextTick()
      expect(mockRouterPush).toHaveBeenCalledWith('/agents/test-agent')
    })

    it('navigates to /agents on department node click', async () => {
      const vueFlow = wrapper.findComponent({ name: 'VueFlow' })
      vueFlow.vm.$emit('node-click', { node: { id: 'dept-engineering' } })
      await nextTick()
      expect(mockRouterPush).toHaveBeenCalledWith('/agents')
    })

    it('navigates to /agents on team node click', async () => {
      const vueFlow = wrapper.findComponent({ name: 'VueFlow' })
      vueFlow.vm.$emit('node-click', { node: { id: 'team-engineering-Backend' } })
      await nextTick()
      expect(mockRouterPush).toHaveBeenCalledWith('/agents')
    })
  })

  it('shows error when department fetch fails', async () => {
    vi.mocked(listDepartments).mockRejectedValue(new Error('Network error'))
    const wrapper = mount(OrgChartPage)
    await flushPromises()
    // Fetch attempted; store captured the error (hasDepartments stays false).
    // ErrorBoundary mock shows error message instead of slot content.
    expect(listDepartments).toHaveBeenCalled()
    expect(wrapper.find('[data-testid="error-message"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="vue-flow"]').exists()).toBe(false)
  })

  it('shows error when only agent fetch fails', async () => {
    mockWithDepartments()
    vi.mocked(listAgents).mockRejectedValue(new Error('Agent service down'))
    const wrapper = mount(OrgChartPage)
    await flushPromises()
    // Departments loaded but agent error triggers ErrorBoundary
    expect(wrapper.find('[data-testid="error-message"]').exists()).toBe(true)
  })
})
