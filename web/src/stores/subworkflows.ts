import { create } from 'zustand'
import {
  listSubworkflows,
  searchSubworkflows,
  deleteSubworkflow as deleteSubworkflowApi,
} from '@/api/endpoints/subworkflows'
import { createLogger } from '@/lib/logger'
import { useToastStore } from '@/stores/toast'
import { getErrorMessage } from '@/utils/errors'
import { sanitizeForLog } from '@/utils/logging'
import type { SubworkflowSummary } from '@/api/types/workflows'

const log = createLogger('subworkflows')

const PAGE_SIZE = 50

interface SubworkflowsState {
  subworkflows: readonly SubworkflowSummary[]
  listLoading: boolean
  /** Whether a follow-up fetchMoreSubworkflows() is currently in flight. */
  loadingMore: boolean
  listError: string | null
  searchQuery: string
  /** Opaque cursor for the next page; null on the final page or on search. */
  nextCursor: string | null
  /** Whether more pages follow the current snapshot. */
  hasMore: boolean

  fetchSubworkflows: () => Promise<void>
  fetchMoreSubworkflows: () => Promise<void>
  deleteSubworkflow: (id: string, version: string) => Promise<boolean>
  setSearchQuery: (q: string) => void
  updateFromWsEvent: () => void
}

let _listRequestToken = 0
function isStaleRequest(token: number): boolean {
  return _listRequestToken !== token
}

export const useSubworkflowsStore = create<SubworkflowsState>((set, get) => ({
  subworkflows: [],
  listLoading: false,
  loadingMore: false,
  listError: null,
  searchQuery: '',
  nextCursor: null,
  hasMore: false,

  async fetchSubworkflows() {
    const token = ++_listRequestToken
    set(() => ({
      listLoading: true,
      listError: null,
      // Reset cursor state on every fresh fetch so the page never
      // shows a stale "Load More" stub against the wrong dataset.
      subworkflows: [],
      nextCursor: null,
      hasMore: false,
    }))
    try {
      const query = get().searchQuery.trim()
      if (query) {
        // Search endpoint is intentionally non-paginated: a search
        // returns matches across the whole registry, and the user
        // expects to see all matches, not a single page.
        const results = await searchSubworkflows(query)
        if (isStaleRequest(token)) return
        set(() => ({
          subworkflows: results,
          listLoading: false,
          nextCursor: null,
          hasMore: false,
        }))
      } else {
        const page = await listSubworkflows({ limit: PAGE_SIZE })
        if (isStaleRequest(token)) return
        set(() => ({
          subworkflows: page.data,
          listLoading: false,
          nextCursor: page.nextCursor,
          hasMore: page.hasMore,
        }))
      }
    } catch (err: unknown) {
      if (isStaleRequest(token)) {
        return
      }
      log.warn('Failed to fetch subworkflows', sanitizeForLog(err))
      set(() => ({
        listLoading: false,
        listError: getErrorMessage(err),
      }))
    }
  },

  async fetchMoreSubworkflows() {
    const { hasMore, nextCursor, loadingMore, listLoading, searchQuery } = get()
    // Search results are unpaginated, so Load More is not applicable
    // when a query is active.
    if (searchQuery.trim() !== '') return
    if (loadingMore || listLoading) return
    if (!hasMore || !nextCursor) return
    set(() => ({ loadingMore: true }))
    try {
      const page = await listSubworkflows({
        cursor: nextCursor,
        limit: PAGE_SIZE,
      })
      set((state) => ({
        subworkflows: [...state.subworkflows, ...page.data],
        nextCursor: page.nextCursor,
        hasMore: page.hasMore,
        loadingMore: false,
      }))
    } catch (err) {
      log.warn('Failed to fetch more subworkflows', sanitizeForLog(err))
      // Surface the failure through the same banner the initial fetch
      // uses; preserve the already-loaded items so the user is not
      // dumped back to an empty grid on a flaky network.
      set(() => ({
        loadingMore: false,
        listError: getErrorMessage(err),
      }))
    }
  },

  async deleteSubworkflow(id: string, version: string) {
    try {
      await deleteSubworkflowApi(id, version)
      await get().fetchSubworkflows()
      useToastStore.getState().add({
        variant: 'success',
        title: 'Subworkflow deleted',
      })
      return true
    } catch (err) {
      log.error('Delete subworkflow failed', sanitizeForLog(err))
      useToastStore.getState().add({
        variant: 'error',
        title: 'Failed to delete subworkflow',
        description: getErrorMessage(err),
      })
      return false
    }
  },

  setSearchQuery(q: string) {
    set(() => ({ searchQuery: q }))
  },

  updateFromWsEvent() {
    void get().fetchSubworkflows()
  },
}))
