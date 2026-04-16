import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useWorkflowsStore } from '@/stores/workflows'
import { useToastStore } from '@/stores/toast'
import type { WorkflowDefinition } from '@/api/types'

vi.mock('@/api/endpoints/workflows', () => ({
  listWorkflows: vi.fn(),
  listBlueprints: vi.fn(),
  createWorkflow: vi.fn(),
  createFromBlueprint: vi.fn(),
  deleteWorkflow: vi.fn(),
}))

async function importApi() {
  return await import('@/api/endpoints/workflows')
}

function makeWorkflow(id: string, overrides?: Partial<WorkflowDefinition>): WorkflowDefinition {
  return {
    id,
    name: `wf-${id}`,
    description: null,
    workflow_type: 'sequential_pipeline',
    nodes: [],
    edges: [],
    created_at: '2026-04-01T00:00:00Z',
    updated_at: '2026-04-01T00:00:00Z',
    version: 1,
    ...overrides,
  } as WorkflowDefinition
}

function resetStore() {
  useWorkflowsStore.setState({
    workflows: [],
    totalWorkflows: 0,
    listLoading: false,
    listError: null,
    blueprints: [],
    blueprintsLoading: false,
    blueprintsError: null,
    searchQuery: '',
    workflowTypeFilter: null,
  })
  useToastStore.setState({ toasts: [] })
}

beforeEach(() => {
  resetStore()
  vi.clearAllMocks()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('createWorkflow', () => {
  it('upserts the result and emits a success toast', async () => {
    const api = await importApi()
    const created = makeWorkflow('1', { name: 'Alpha' })
    vi.mocked(api.createWorkflow).mockResolvedValue(created)

    const result = await useWorkflowsStore.getState().createWorkflow({
      name: 'Alpha',
      workflow_type: 'sequential_pipeline',
      nodes: [],
      edges: [],
    })

    expect(result).toEqual(created)
    expect(useWorkflowsStore.getState().workflows[0]).toEqual(created)
    const toasts = useToastStore.getState().toasts
    expect(toasts).toHaveLength(1)
    expect(toasts[0]!.variant).toBe('success')
  })

  it('returns null and emits an error toast on API failure', async () => {
    const api = await importApi()
    vi.mocked(api.createWorkflow).mockRejectedValue(new Error('boom'))

    const result = await useWorkflowsStore.getState().createWorkflow({
      name: 'Alpha',
      workflow_type: 'sequential_pipeline',
      nodes: [],
      edges: [],
    })

    expect(result).toBeNull()
    const toasts = useToastStore.getState().toasts
    expect(toasts).toHaveLength(1)
    expect(toasts[0]!.variant).toBe('error')
  })
})

describe('createFromBlueprint', () => {
  it('upserts the result and emits a success toast', async () => {
    const api = await importApi()
    const created = makeWorkflow('2', { name: 'Beta' })
    vi.mocked(api.createFromBlueprint).mockResolvedValue(created)

    const result = await useWorkflowsStore.getState().createFromBlueprint({
      blueprint_name: 'bp1',
      name: 'Beta',
    })

    expect(result).toEqual(created)
    expect(useToastStore.getState().toasts[0]!.variant).toBe('success')
  })

  it('returns null on API failure', async () => {
    const api = await importApi()
    vi.mocked(api.createFromBlueprint).mockRejectedValue(new Error('boom'))

    const result = await useWorkflowsStore.getState().createFromBlueprint({
      blueprint_name: 'bp1',
      name: 'Beta',
    })

    expect(result).toBeNull()
    expect(useToastStore.getState().toasts[0]!.variant).toBe('error')
  })
})

describe('deleteWorkflow', () => {
  it('optimistically removes the workflow and returns true on success', async () => {
    const api = await importApi()
    const wf = makeWorkflow('1')
    useWorkflowsStore.setState({ workflows: [wf], totalWorkflows: 1 })
    vi.mocked(api.deleteWorkflow).mockResolvedValue(undefined)

    const result = await useWorkflowsStore.getState().deleteWorkflow('1')

    expect(result).toBe(true)
    expect(useWorkflowsStore.getState().workflows).toHaveLength(0)
    expect(useWorkflowsStore.getState().totalWorkflows).toBe(0)
    expect(useToastStore.getState().toasts[0]!.variant).toBe('success')
  })

  it('rolls back state and returns false on API failure', async () => {
    const api = await importApi()
    const wf = makeWorkflow('1')
    useWorkflowsStore.setState({ workflows: [wf], totalWorkflows: 1 })
    vi.mocked(api.deleteWorkflow).mockRejectedValue(new Error('boom'))

    const result = await useWorkflowsStore.getState().deleteWorkflow('1')

    expect(result).toBe(false)
    expect(useWorkflowsStore.getState().workflows).toEqual([wf])
    expect(useWorkflowsStore.getState().totalWorkflows).toBe(1)
    expect(useToastStore.getState().toasts[0]!.variant).toBe('error')
  })
})
