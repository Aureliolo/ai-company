import { create } from 'zustand'
import {
  listSubworkflows,
  searchSubworkflows,
  deleteSubworkflow as deleteSubworkflowApi,
} from '@/api/endpoints/subworkflows'
import { createLogger } from '@/lib/logger'
import { getErrorMessage } from '@/utils/errors'
import { sanitizeForLog } from '@/utils/logging'
import type { SubworkflowSummary } from '@/api/types'

const log = createLogger('subworkflows')

interface SubworkflowsState {
  subworkflows: readonly SubworkflowSummary[]
  listLoading: boolean
  listError: string | null
  searchQuery: string

  fetchSubworkflows: () => Promise<void>
  deleteSubworkflow: (id: string, version: string) => Promise<void>
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
        set(() => ({ listLoading: false }))
        return
      }
      set(() => ({
        subworkflows: results,
        listLoading: false,
      }))
    } catch (err: unknown) {
      if (isStaleRequest(token)) {
        set(() => ({ listLoading: false }))
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
    await deleteSubworkflowApi(id, version)
    set((state) => ({
      subworkflows: state.subworkflows.filter(
        (s) => s.subworkflow_id !== id,
      ),
    }))
  },

  setSearchQuery(q: string) {
    set(() => ({ searchQuery: q }))
  },

  updateFromWsEvent() {
    void get().fetchSubworkflows()
  },
}))
