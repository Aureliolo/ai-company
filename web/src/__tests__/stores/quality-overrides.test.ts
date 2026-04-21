import { http, HttpResponse } from 'msw'
import { beforeEach, describe } from 'vitest'
import { useQualityOverridesStore } from '@/stores/quality-overrides'
import { useToastStore } from '@/stores/toast'
import { apiError } from '@/mocks/handlers'
import { server } from '@/test-setup'

describe('useQualityOverridesStore', () => {
  beforeEach(() => {
    // Global afterEach handles `dismissAll` + `cancelPendingPersist`;
    // do NOT duplicate here -- double-teardown raises the async-leak
    // count on CI.
    useToastStore.getState().dismissAll()
  })

  describe('getOverride', () => {
    it('returns the override when present', async () => {
      const result = await useQualityOverridesStore
        .getState()
        .getOverride('agent-1')

      expect(result?.agent_id).toBe('agent-1')
      expect(useToastStore.getState().toasts).toHaveLength(0)
    })

    it('returns null silently on 404 (no active override)', async () => {
      server.use(
        http.get('/api/v1/agents/:id/quality/override', () =>
          HttpResponse.json(apiError('not found'), { status: 404 }),
        ),
      )

      const result = await useQualityOverridesStore
        .getState()
        .getOverride('agent-1')

      expect(result).toBeNull()
      // 404 is steady-state for most agents; don't shout about it.
      expect(useToastStore.getState().toasts).toHaveLength(0)
    })

    it('toasts on non-404 failures and returns null', async () => {
      server.use(
        http.get('/api/v1/agents/:id/quality/override', () =>
          HttpResponse.json(apiError('boom'), { status: 500 }),
        ),
      )

      const result = await useQualityOverridesStore
        .getState()
        .getOverride('agent-1')

      expect(result).toBeNull()
      const toasts = useToastStore.getState().toasts
      expect(toasts).toHaveLength(1)
      expect(toasts[0]!.variant).toBe('error')
      expect(toasts[0]!.title).toBe('Failed to load quality override')
    })
  })

  describe('setOverride', () => {
    it('returns the new override + success toast on success', async () => {
      const result = await useQualityOverridesStore
        .getState()
        .setOverride('agent-1', { score: 8, reason: 'good agent', expires_in_days: null })

      expect(result?.score).toBe(8)
      const toasts = useToastStore.getState().toasts
      expect(toasts).toHaveLength(1)
      expect(toasts[0]!.variant).toBe('success')
    })

    it('returns null + error toast on failure', async () => {
      server.use(
        http.post('/api/v1/agents/:id/quality/override', () =>
          HttpResponse.json(apiError('bad'), { status: 400 }),
        ),
      )

      const result = await useQualityOverridesStore
        .getState()
        .setOverride('agent-1', { score: 8, reason: '', expires_in_days: null })

      expect(result).toBeNull()
      const toasts = useToastStore.getState().toasts
      expect(toasts).toHaveLength(1)
      expect(toasts[0]!.title).toBe('Failed to apply quality override')
    })
  })

  describe('clearOverride', () => {
    it('returns true + success toast on success', async () => {
      const result = await useQualityOverridesStore
        .getState()
        .clearOverride('agent-1')

      expect(result).toBe(true)
      const toasts = useToastStore.getState().toasts
      expect(toasts).toHaveLength(1)
      expect(toasts[0]!.variant).toBe('success')
    })

    it('returns false + error toast on failure', async () => {
      server.use(
        http.delete('/api/v1/agents/:id/quality/override', () =>
          HttpResponse.json(apiError('bad'), { status: 500 }),
        ),
      )

      const result = await useQualityOverridesStore
        .getState()
        .clearOverride('agent-1')

      expect(result).toBe(false)
      const toasts = useToastStore.getState().toasts
      expect(toasts).toHaveLength(1)
      expect(toasts[0]!.title).toBe('Failed to clear quality override')
    })
  })
})
