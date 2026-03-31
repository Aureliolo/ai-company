import fc from 'fast-check'
import { useArtifactsStore } from '@/stores/artifacts'
import { makeArtifact } from '../helpers/factories'
import type { WsEvent } from '@/api/types'

vi.mock('@/api/endpoints/artifacts', () => ({
  listArtifacts: vi.fn(),
  getArtifact: vi.fn(),
  getArtifactContentText: vi.fn(),
  deleteArtifact: vi.fn(),
}))

const { listArtifacts, getArtifact, getArtifactContentText, deleteArtifact } =
  await import('@/api/endpoints/artifacts')

describe('useArtifactsStore', () => {
  beforeEach(() => {
    useArtifactsStore.setState({
      artifacts: [],
      totalArtifacts: 0,
      listLoading: false,
      listError: null,
      searchQuery: '',
      typeFilter: null,
      createdByFilter: null,
      taskIdFilter: null,
      contentTypeFilter: null,
      projectIdFilter: null,
      selectedArtifact: null,
      contentPreview: null,
      detailLoading: false,
      detailError: null,
    })
    vi.clearAllMocks()
  })

  describe('fetchArtifacts', () => {
    it('populates artifacts on success', async () => {
      const artifact = makeArtifact('artifact-001')
      vi.mocked(listArtifacts).mockResolvedValue({ data: [artifact], total: 1, offset: 0, limit: 200 })

      await useArtifactsStore.getState().fetchArtifacts()

      const state = useArtifactsStore.getState()
      expect(state.artifacts).toEqual([artifact])
      expect(state.totalArtifacts).toBe(1)
      expect(state.listLoading).toBe(false)
    })

    it('sets error on failure', async () => {
      vi.mocked(listArtifacts).mockRejectedValue(new Error('Network error'))

      await useArtifactsStore.getState().fetchArtifacts()

      expect(useArtifactsStore.getState().listError).toBe('Network error')
    })
  })

  describe('fetchArtifactDetail', () => {
    it('populates selected artifact', async () => {
      const artifact = makeArtifact('artifact-001', { content_type: 'text/plain', size_bytes: 100 })
      vi.mocked(getArtifact).mockResolvedValue(artifact)
      vi.mocked(getArtifactContentText).mockResolvedValue('hello world')

      await useArtifactsStore.getState().fetchArtifactDetail('artifact-001')

      const state = useArtifactsStore.getState()
      expect(state.selectedArtifact).toEqual(artifact)
      expect(state.contentPreview).toBe('hello world')
    })

    it('sets error when artifact not found', async () => {
      vi.mocked(getArtifact).mockRejectedValue(new Error('Not found'))

      await useArtifactsStore.getState().fetchArtifactDetail('missing')

      expect(useArtifactsStore.getState().detailError).toBe('Not found')
    })

    it('handles partial content preview failure gracefully', async () => {
      const artifact = makeArtifact('artifact-001', { content_type: 'text/plain', size_bytes: 100 })
      vi.mocked(getArtifact).mockResolvedValue(artifact)
      vi.mocked(getArtifactContentText).mockRejectedValue(new Error('Content unavailable'))

      await useArtifactsStore.getState().fetchArtifactDetail('artifact-001')

      const state = useArtifactsStore.getState()
      expect(state.selectedArtifact).toEqual(artifact)
      expect(state.contentPreview).toBeNull()
      expect(state.detailError).toMatch(/content preview/)
    })
  })

  describe('deleteArtifact', () => {
    it('removes artifact from list', async () => {
      const a1 = makeArtifact('artifact-001')
      const a2 = makeArtifact('artifact-002')
      useArtifactsStore.setState({ artifacts: [a1, a2], totalArtifacts: 2 })
      vi.mocked(deleteArtifact).mockResolvedValue()

      await useArtifactsStore.getState().deleteArtifact('artifact-001')

      expect(useArtifactsStore.getState().artifacts).toEqual([a2])
      expect(useArtifactsStore.getState().totalArtifacts).toBe(1)
    })

    it('propagates error without modifying list', async () => {
      const a1 = makeArtifact('artifact-001')
      useArtifactsStore.setState({ artifacts: [a1], totalArtifacts: 1 })
      vi.mocked(deleteArtifact).mockRejectedValue(new Error('Delete failed'))

      await expect(useArtifactsStore.getState().deleteArtifact('artifact-001')).rejects.toThrow('Delete failed')

      expect(useArtifactsStore.getState().artifacts).toEqual([a1])
      expect(useArtifactsStore.getState().totalArtifacts).toBe(1)
    })
  })

  describe('updateFromWsEvent', () => {
    it('triggers fetchArtifacts on WS event', async () => {
      vi.mocked(listArtifacts).mockResolvedValue({ data: [], total: 0, offset: 0, limit: 200 })

      const event: WsEvent = {
        event_type: 'artifact.created',
        channel: 'artifacts',
        timestamp: '2026-03-31T12:00:00Z',
        payload: { artifact_id: 'artifact-new', task_id: 'task-001' },
      }
      useArtifactsStore.getState().updateFromWsEvent(event)

      expect(listArtifacts).toHaveBeenCalled()
    })
  })

  describe('filters', () => {
    it('sets search query with arbitrary strings', () => {
      fc.assert(
        fc.property(fc.string(), (s) => {
          useArtifactsStore.getState().setSearchQuery(s)
          return useArtifactsStore.getState().searchQuery === s
        }),
      )
    })

    it('sets type filter', () => {
      useArtifactsStore.getState().setTypeFilter('code')
      expect(useArtifactsStore.getState().typeFilter).toBe('code')
    })

    it('sets type filter to null for clear', () => {
      useArtifactsStore.getState().setTypeFilter('code')
      useArtifactsStore.getState().setTypeFilter(null)
      expect(useArtifactsStore.getState().typeFilter).toBeNull()
    })
  })

  describe('clearDetail', () => {
    it('clears detail state', () => {
      useArtifactsStore.setState({
        selectedArtifact: makeArtifact('artifact-001'),
        contentPreview: 'some content',
        detailError: 'old error',
      })

      useArtifactsStore.getState().clearDetail()

      const state = useArtifactsStore.getState()
      expect(state.selectedArtifact).toBeNull()
      expect(state.contentPreview).toBeNull()
      expect(state.detailError).toBeNull()
    })
  })
})
