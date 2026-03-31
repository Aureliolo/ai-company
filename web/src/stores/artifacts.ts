import { create } from 'zustand'
import { listArtifacts, getArtifact, getArtifactContentText, deleteArtifact as deleteArtifactApi } from '@/api/endpoints/artifacts'
import { getErrorMessage } from '@/utils/errors'
import type { Artifact, ArtifactType, WsEvent } from '@/api/types'

/** Content types eligible for inline text preview. */
function isPreviewableText(contentType: string): boolean {
  return contentType.startsWith('text/') || contentType === 'application/json'
}

interface ArtifactsState {
  // List page
  artifacts: readonly Artifact[]
  totalArtifacts: number
  listLoading: boolean
  listError: string | null

  // Filters
  searchQuery: string
  typeFilter: ArtifactType | null
  createdByFilter: string | null
  taskIdFilter: string | null

  // Detail page
  selectedArtifact: Artifact | null
  contentPreview: string | null
  detailLoading: boolean
  detailError: string | null

  // Actions
  fetchArtifacts: () => Promise<void>
  fetchArtifactDetail: (id: string) => Promise<void>
  deleteArtifact: (id: string) => Promise<void>
  setSearchQuery: (q: string) => void
  setTypeFilter: (t: ArtifactType | null) => void
  setCreatedByFilter: (c: string | null) => void
  setTaskIdFilter: (t: string | null) => void
  clearDetail: () => void
  updateFromWsEvent: (event: WsEvent) => void
}

let _detailRequestId = ''

export const useArtifactsStore = create<ArtifactsState>()((set) => ({
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

  fetchArtifacts: async () => {
    set({ listLoading: true, listError: null })
    try {
      const result = await listArtifacts({ limit: 200 })
      set({ artifacts: result.data, totalArtifacts: result.total, listLoading: false })
    } catch (err) {
      set({ listLoading: false, listError: getErrorMessage(err) })
    }
  },

  fetchArtifactDetail: async (id: string) => {
    _detailRequestId = id
    set({ detailLoading: true, detailError: null })
    try {
      const artifact = await getArtifact(id)
      if (_detailRequestId !== id) return

      let preview: string | null = null
      const partialErrors: string[] = []
      if (artifact.content_type && artifact.size_bytes > 0 && isPreviewableText(artifact.content_type)) {
        try {
          preview = await getArtifactContentText(id)
        } catch {
          partialErrors.push('content preview')
        }
      }

      if (_detailRequestId !== id) return
      set({
        selectedArtifact: artifact,
        contentPreview: preview,
        detailLoading: false,
        detailError: partialErrors.length > 0
          ? `Some data failed to load: ${partialErrors.join(', ')}. Displayed data may be incomplete.`
          : null,
      })
    } catch (err) {
      if (_detailRequestId !== id) return
      set({ detailLoading: false, detailError: getErrorMessage(err) })
    }
  },

  deleteArtifact: async (id: string) => {
    await deleteArtifactApi(id)
    set((state) => ({
      artifacts: state.artifacts.filter((a) => a.id !== id),
      totalArtifacts: Math.max(0, state.totalArtifacts - 1),
    }))
  },

  setSearchQuery: (q) => set({ searchQuery: q }),
  setTypeFilter: (t) => set({ typeFilter: t }),
  setCreatedByFilter: (c) => set({ createdByFilter: c }),
  setTaskIdFilter: (t) => set({ taskIdFilter: t }),

  clearDetail: () => {
    _detailRequestId = ''
    set({
      selectedArtifact: null,
      contentPreview: null,
      detailLoading: false,
      detailError: null,
    })
  },

  updateFromWsEvent: () => {
    // Refetch list on any artifact WS event (debounced in hook layer)
    useArtifactsStore.getState().fetchArtifacts()
  },
}))
