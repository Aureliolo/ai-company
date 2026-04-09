/**
 * Zustand store for ontology entity catalog and drift monitor.
 */
import { create } from 'zustand'
import {
  listEntities,
  listDriftReports,
  type EntityResponse,
  type DriftReportResponse,
} from '@/api/endpoints/ontology'
import { createLogger } from '@/lib/logger'
import { getErrorMessage } from '@/utils/errors'

const log = createLogger('ontology')

type TierFilter = 'all' | 'core' | 'user'

interface OntologyState {
  // ── Entity catalog ──
  entities: readonly EntityResponse[]
  totalEntities: number
  entitiesLoading: boolean
  entitiesError: string | null

  // ── Drift monitor ──
  driftReports: readonly DriftReportResponse[]
  driftLoading: boolean
  driftError: string | null

  // ── Filters ──
  tierFilter: TierFilter
  searchQuery: string

  // ── Selected entity ──
  selectedEntity: EntityResponse | null

  // ── Actions ──
  fetchEntities: () => Promise<void>
  fetchDriftReports: () => Promise<void>
  setTierFilter: (tier: TierFilter) => void
  setSearchQuery: (q: string) => void
  setSelectedEntity: (entity: EntityResponse | null) => void
}

export const useOntologyStore = create<OntologyState>()((set) => ({
  // ── Defaults ──
  entities: [],
  totalEntities: 0,
  entitiesLoading: false,
  entitiesError: null,

  driftReports: [],
  driftLoading: false,
  driftError: null,

  tierFilter: 'all',
  searchQuery: '',
  selectedEntity: null,

  // ── Actions ──
  fetchEntities: async () => {
    set({ entitiesLoading: true, entitiesError: null })
    try {
      const result = await listEntities({ limit: 200 })
      set({
        entities: result.data,
        totalEntities: result.total,
        entitiesLoading: false,
      })
    } catch (err) {
      log.error('Failed to fetch entities:', getErrorMessage(err))
      set({
        entitiesError: getErrorMessage(err),
        entitiesLoading: false,
      })
    }
  },

  fetchDriftReports: async () => {
    set({ driftLoading: true, driftError: null })
    try {
      const result = await listDriftReports({ limit: 100 })
      set({
        driftReports: result.data,
        driftLoading: false,
      })
    } catch (err) {
      log.error('Failed to fetch drift reports:', getErrorMessage(err))
      set({
        driftError: getErrorMessage(err),
        driftLoading: false,
      })
    }
  },

  setTierFilter: (tier: TierFilter) => set({ tierFilter: tier }),
  setSearchQuery: (q: string) => set({ searchQuery: q }),
  setSelectedEntity: (entity: EntityResponse | null) =>
    set({ selectedEntity: entity }),
}))
