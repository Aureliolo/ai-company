import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as trainingApi from '@/api/endpoints/training'
import type {
  TrainingPlanResponse,
  TrainingResultResponse,
} from '@/api/endpoints/training'
import { useTrainingStore } from '@/stores/training'
import { useToastStore } from '@/stores/toast'

function mockPlan(overrides: Partial<TrainingPlanResponse> = {}): TrainingPlanResponse {
  return {
    id: 'plan-1',
    new_agent_id: 'agent-1',
    new_agent_role: 'engineer',
    source_selector_type: 'seniority',
    enabled_content_types: ['procedural', 'semantic', 'tool_patterns'],
    curation_strategy_type: 'default',
    volume_caps: [],
    override_sources: [],
    skip_training: false,
    require_review: true,
    status: 'pending',
    created_at: '2026-04-01T00:00:00Z',
    executed_at: null,
    ...overrides,
  }
}

function mockResult(overrides: Partial<TrainingResultResponse> = {}): TrainingResultResponse {
  return {
    id: 'res-1',
    plan_id: 'plan-1',
    new_agent_id: 'agent-1',
    source_agents_used: ['source-1'],
    items_extracted: [['procedural', 3]],
    items_after_curation: [['procedural', 3]],
    items_after_guards: [['procedural', 3]],
    items_stored: [['procedural', 3]],
    approval_item_id: null,
    review_pending: false,
    errors: [],
    started_at: '2026-04-01T00:00:00Z',
    completed_at: '2026-04-01T00:05:00Z',
    ...overrides,
  }
}

describe('useTrainingStore', () => {
  beforeEach(() => {
    useTrainingStore.setState({
      plansByAgent: {},
      resultsByAgent: {},
      loading: {},
      error: {},
    })
    useToastStore.setState({ toasts: [] })
    vi.restoreAllMocks()
  })

  it('fetchResult stores the result and clears loading', async () => {
    const result = mockResult()
    vi.spyOn(trainingApi, 'getTrainingResult').mockResolvedValueOnce(result)

    await useTrainingStore.getState().fetchResult('agent-1')

    const state = useTrainingStore.getState()
    expect(state.resultsByAgent['agent-1']).toEqual(result)
    expect(state.loading['agent-1']).toBe(false)
    expect(state.error['agent-1']).toBeNull()
  })

  it('fetchResult sets error when the API rejects', async () => {
    vi.spyOn(trainingApi, 'getTrainingResult').mockRejectedValueOnce(
      new Error('offline'),
    )

    await useTrainingStore.getState().fetchResult('agent-1')

    const state = useTrainingStore.getState()
    expect(state.resultsByAgent['agent-1']).toBeUndefined()
    expect(state.loading['agent-1']).toBe(false)
    expect(state.error['agent-1']).toContain('offline')
  })

  it('createPlan updates the store and emits a success toast', async () => {
    const plan = mockPlan()
    vi.spyOn(trainingApi, 'createTrainingPlan').mockResolvedValueOnce(plan)

    const returned = await useTrainingStore.getState().createPlan('agent-1', {
      override_sources: [],
      skip_training: false,
      require_review: true,
    })

    expect(returned).toEqual(plan)
    expect(useTrainingStore.getState().plansByAgent['agent-1']).toEqual(plan)
    const toasts = useToastStore.getState().toasts
    expect(toasts).toHaveLength(1)
    expect(toasts[0]?.variant).toBe('success')
  })

  it('createPlan returns null and emits an error toast on failure', async () => {
    vi.spyOn(trainingApi, 'createTrainingPlan').mockRejectedValueOnce(
      new Error('server exploded'),
    )

    const returned = await useTrainingStore.getState().createPlan('agent-1', {
      override_sources: [],
      skip_training: false,
      require_review: true,
    })

    expect(returned).toBeNull()
    const toasts = useToastStore.getState().toasts
    expect(toasts[0]?.variant).toBe('error')
    expect(toasts[0]?.description).toContain('server exploded')
  })

  it('executePlan stores the result on success', async () => {
    const result = mockResult()
    vi.spyOn(trainingApi, 'executeTrainingPlan').mockResolvedValueOnce(result)

    const returned = await useTrainingStore.getState().executePlan('agent-1')

    expect(returned).toEqual(result)
    expect(useTrainingStore.getState().resultsByAgent['agent-1']).toEqual(result)
  })

  it('updateOverrides replaces the cached plan on success', async () => {
    const updated = mockPlan({ status: 'executed' })
    vi.spyOn(trainingApi, 'updateTrainingOverrides').mockResolvedValueOnce(
      updated,
    )

    const returned = await useTrainingStore
      .getState()
      .updateOverrides('agent-1', 'plan-1', { override_sources: ['s2'] })

    expect(returned).toEqual(updated)
    expect(useTrainingStore.getState().plansByAgent['agent-1']).toEqual(updated)
  })
})
