import { useArtifactsStore } from '@/stores/artifacts'
import { makeArtifact } from '../helpers/factories'

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
  })

  describe('filters', () => {
    it('sets search query', () => {
      useArtifactsStore.getState().setSearchQuery('test')
      expect(useArtifactsStore.getState().searchQuery).toBe('test')
    })

    it('sets type filter', () => {
      useArtifactsStore.getState().setTypeFilter('code')
      expect(useArtifactsStore.getState().typeFilter).toBe('code')
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
