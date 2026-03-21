import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), go: vi.fn() }),
  useRoute: () => ({ params: {} }),
  RouterLink: { template: '<a><slot /></a>' },
}))

vi.mock('@vue-flow/core', () => ({
  VueFlow: {
    props: ['nodes', 'edges', 'fitViewOnInit'],
    template: '<div data-testid="vue-flow"><slot /></div>',
  },
  useVueFlow: () => ({ fitView: vi.fn() }),
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
    template: '<div><slot /></div>',
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
    expect(listDepartments).toHaveBeenCalled()
    expect(listAgents).toHaveBeenCalled()
  })

  it('shows empty state when no departments exist', async () => {
    const wrapper = mount(OrgChartPage)
    await flushPromises()
    expect(wrapper.find('[data-testid="empty-state"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="empty-state"] h3').text()).toBe('No departments')
    expect(wrapper.find('[data-testid="vue-flow"]').exists()).toBe(false)
  })

  it('shows VueFlow when departments exist', async () => {
    mockWithDepartments()
    const wrapper = mount(OrgChartPage)
    await flushPromises()
    expect(wrapper.find('[data-testid="vue-flow"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="empty-state"]').exists()).toBe(false)
  })

  it('renders controls and minimap when departments exist', async () => {
    mockWithDepartments()
    const wrapper = mount(OrgChartPage)
    await flushPromises()
    expect(wrapper.find('[data-testid="controls"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="minimap"]').exists()).toBe(true)
  })

  it('empty state includes a link to settings', async () => {
    const wrapper = mount(OrgChartPage)
    await flushPromises()
    // EmptyState action slot renders a RouterLink to /settings
    expect(wrapper.text()).toContain('Go to Settings')
  })

  it('shows error boundary when fetch fails', async () => {
    vi.mocked(listDepartments).mockRejectedValue(new Error('Network error'))
    const wrapper = mount(OrgChartPage)
    await flushPromises()
    // ErrorBoundary mock renders slot content; the store captures the error
    // Verify the fetch ran and the error was captured (no unhandled rejection)
    expect(listDepartments).toHaveBeenCalled()
    // VueFlow should not render when there is an error
    expect(wrapper.find('[data-testid="vue-flow"]').exists()).toBe(false)
  })
})
