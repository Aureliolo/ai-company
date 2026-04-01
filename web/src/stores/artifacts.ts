import { create } from 'zustand'
import { listArtifacts, getArtifact, getArtifactContentText, deleteArtifact as deleteArtifactApi } from '@/api/endpoints/artifacts'
import { getErrorMessage } from '@/utils/errors'
import type { Artifact, ArtifactType, WsEvent } from '@/api/types'

/** Content types eligible for inline text preview: text/*, application/json, and YAML. */
function isPreviewableText(contentType: string): boolean {
  return (
    contentType.startsWith('text/') ||
    contentType === 'application/json' ||
    contentType === 'application/yaml' ||
    contentType === 'application/x-yaml'
  )
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
  contentTypeFilter: string | null
  projectIdFilter: string | null

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
  setContentTypeFilter: (ct: string | null) => void
  setProjectIdFilter: (p: string | null) => void
  clearDetail: () => void
  updateFromWsEvent: (event: WsEvent) => void
}

let _detailRequestToken = 0
/** True when a newer detail request has superseded this one. */
function isStaleDetailRequest(token: number): boolean { return _detailRequestToken !== token }

let _listRequestToken = 0
/** True when a newer list request has superseded this one. */
function isStaleListRequest(token: number): boolean { return _listRequestToken !== token }

export const useArtifactsStore = create<ArtifactsState>()((set) => ({
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

  fetchArtifacts: async () => {
    const token = ++_listRequestToken
    set({ listLoading: true, listError: null })
    try {
      const result = await listArtifacts({ limit: 200 })
      if (isStaleListRequest(token)) return
      set({ artifacts: result.data, totalArtifacts: result.total, listLoading: false })
    } catch (err) {
      if (isStaleListRequest(token)) return
      set({ listLoading: false, listError: getErrorMessage(err) })
    }
  },

  fetchArtifactDetail: async (id: string) => {
    const token = ++_detailRequestToken
    set({ detailLoading: true, detailError: null, selectedArtifact: null, contentPreview: null })
    try {
      const artifact = await getArtifact(id)
      if (isStaleDetailRequest(token)) return

      // Show metadata immediately so the detail page renders while preview loads.
      set({ selectedArtifact: artifact, detailLoading: false })

      // Fetch content preview in the background if applicable.
      if (artifact.content_type && artifact.size_bytes != null && artifact.size_bytes > 0 && isPreviewableText(artifact.content_type)) {
        try {
          const preview = await getArtifactContentText(id)
          if (isStaleDetailRequest(token)) return
          set({ contentPreview: preview })
        } catch (err) {
          if (isStaleDetailRequest(token)) return
          set({ detailError: `Some data failed to load: content preview: ${getErrorMessage(err)}. Displayed data may be incomplete.` })
        }
      }
    } catch (err) {
      if (isStaleDetailRequest(token)) return
      set({ detailLoading: false, detailError: getErrorMessage(err), selectedArtifact: null, contentPreview: null })
    }
  },

  deleteArtifact: async (id: string) => {
    await deleteArtifactApi(id)
    set((state) => {
      const isSelected = state.selectedArtifact?.id === id
      return {
        artifacts: state.artifacts.filter((a) => a.id !== id),
        totalArtifacts: Math.max(0, state.totalArtifacts - 1),
        selectedArtifact: isSelected ? null : state.selectedArtifact,
        contentPreview: isSelected ? null : state.contentPreview,
        detailError: isSelected ? null : state.detailError,
      }
    })
  },

  setSearchQuery: (q) => set({ searchQuery: q }),
  setTypeFilter: (t) => set({ typeFilter: t }),
  setCreatedByFilter: (c) => set({ createdByFilter: c }),
  setTaskIdFilter: (t) => set({ taskIdFilter: t }),
  setContentTypeFilter: (ct) => set({ contentTypeFilter: ct }),
  setProjectIdFilter: (p) => set({ projectIdFilter: p }),

  clearDetail: () => {
    ++_detailRequestToken
    set({
      selectedArtifact: null,
      contentPreview: null,
      detailLoading: false,
      detailError: null,
    })
  },

  // Event payload ignored -- all events trigger a full refetch.
  // Incremental updates are not worth the complexity given 30s polling.
  updateFromWsEvent: () => {
    useArtifactsStore.getState().fetchArtifacts()
  },
}))
