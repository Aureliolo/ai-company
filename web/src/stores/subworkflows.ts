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

interface SubworkflowsState {
  subworkflows: readonly SubworkflowSummary[]
  listLoading: boolean
  listError: string | null
  searchQuery: string

  fetchSubworkflows: () => Promise<void>
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
  listError: null,
  searchQuery: '',

  async fetchSubworkflows() {
    const token = ++_listRequestToken
    set(() => ({ listLoading: true, listError: null }))
    try {
      const query = get().searchQuery.trim()
      const results = query
        ? await searchSubworkflows(query)
        : await listSubworkflows()
      if (isStaleRequest(token)) {
        return
      }
      set(() => ({
        subworkflows: results,
        listLoading: false,
      }))
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
