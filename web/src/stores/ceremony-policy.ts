import { create } from 'zustand'

import * as ceremonyApi from '@/api/endpoints/ceremony-policy'
import type {
  ActiveCeremonyStrategy,
  CeremonyPolicyConfig,
  ResolvedCeremonyPolicyResponse,
} from '@/api/types/ceremony-policy'
import { getErrorMessage } from '@/utils/errors'

interface CeremonyPolicyState {
  /** Resolved ceremony policy with field origins (may include department overlay). */
  resolvedPolicy: ResolvedCeremonyPolicyResponse | null
  /** Currently active (locked) strategy in the running sprint. */
  activeStrategy: ActiveCeremonyStrategy | null
  /** Per-department ceremony policy overrides (keyed by department name). */
  departmentPolicies: ReadonlyMap<string, CeremonyPolicyConfig | null>
  /** Whether the initial fetch is in progress. */
  loading: boolean
  /** Error from the most recent resolved policy fetch. */
  error: string | null
  /** Error from the most recent active strategy fetch. */
  activeStrategyError: string | null
  /** Error from the most recent per-department fetch (keyed by dept name). */
  departmentErrors: ReadonlyMap<string, string>
  /** Whether a save operation is in progress. */
  saving: boolean
  /** Error from the most recent save attempt. */
  saveError: string | null

  /** Fetch the resolved project-level policy, optionally with department overlay. */
  fetchResolvedPolicy: (department?: string) => Promise<void>
  /** Fetch the currently active sprint strategy. */
  fetchActiveStrategy: () => Promise<void>
  /** Fetch a department's ceremony policy override. */
  fetchDepartmentPolicy: (name: string) => Promise<void>
  /** Set a department ceremony policy override. */
  updateDepartmentPolicy: (name: string, data: CeremonyPolicyConfig) => Promise<void>
  /** Clear a department's ceremony policy override (revert to inherit). */
  clearDepartmentPolicy: (name: string) => Promise<void>
}

export const useCeremonyPolicyStore = create<CeremonyPolicyState>()((set, get) => ({
  resolvedPolicy: null,
  activeStrategy: null,
  departmentPolicies: new Map(),
  loading: false,
  error: null,
  activeStrategyError: null,
  departmentErrors: new Map(),
  saving: false,
  saveError: null,

  fetchResolvedPolicy: async (department?: string) => {
    set({ loading: true, error: null })
    try {
      const resolved = await ceremonyApi.getResolvedPolicy(department)
      set({ resolvedPolicy: resolved, loading: false })
    } catch (err) {
      set({ error: getErrorMessage(err), loading: false })
    }
  },

  fetchActiveStrategy: async () => {
    set({ activeStrategyError: null })
    try {
      const active = await ceremonyApi.getActiveStrategy()
      set({ activeStrategy: active })
    } catch (err) {
      set({ activeStrategyError: getErrorMessage(err) })
    }
  },

  fetchDepartmentPolicy: async (name: string) => {
    try {
      const policy = await ceremonyApi.getDepartmentCeremonyPolicy(name)
      const current = get().departmentPolicies
      const updated = new Map(current)
      updated.set(name, policy)
      // Clear any previous error for this department
      const errors = new Map(get().departmentErrors)
      errors.delete(name)
      set({ departmentPolicies: updated, departmentErrors: errors })
    } catch (err) {
      const errors = new Map(get().departmentErrors)
      errors.set(name, getErrorMessage(err))
      set({ departmentErrors: errors })
    }
  },

  updateDepartmentPolicy: async (name: string, data: CeremonyPolicyConfig) => {
    set({ saving: true, saveError: null })
    try {
      const saved = await ceremonyApi.updateDepartmentCeremonyPolicy(name, data)
      const current = get().departmentPolicies
      const updated = new Map(current)
      // Use server-normalized response instead of the input data
      updated.set(name, saved)
      set({ departmentPolicies: updated, saving: false })
    } catch (err) {
      set({ saveError: getErrorMessage(err), saving: false })
    }
  },

  clearDepartmentPolicy: async (name: string) => {
    set({ saving: true, saveError: null })
    try {
      await ceremonyApi.clearDepartmentCeremonyPolicy(name)
      const current = get().departmentPolicies
      const updated = new Map(current)
      updated.set(name, null)
      set({ departmentPolicies: updated, saving: false })
    } catch (err) {
      set({ saveError: getErrorMessage(err), saving: false })
    }
  },
}))
