import {
  listProviders,
  getProviderHealth,
} from '@/api/endpoints/providers'
import { getErrorMessage } from '@/utils/errors'
import { createLogger } from '@/lib/logger'
import { normalizeProviders } from '@/utils/providers'
import type { ProviderHealthStatus, ProviderHealthSummary } from '@/api/types/providers'
import type { ProviderSortKey } from '@/utils/providers'
import type { ProvidersSet } from './types'

const log = createLogger('providers')

let _listRequestId = 0

export function createListActions(set: ProvidersSet) {
  return {
    fetchProviders: async () => {
      const requestId = ++_listRequestId
      set({ listLoading: true, listError: null })
      try {
        const record = await listProviders()
        if (requestId !== _listRequestId) return
        const providers = normalizeProviders(record)
        set({ providers })

        // Fetch health in parallel (best-effort, with logging)
        const names = providers.map((p) => p.name)
        const healthResults = await Promise.allSettled(
          names.map((name) => getProviderHealth(name)),
        )
        if (requestId !== _listRequestId) return
        const healthMap: Record<string, ProviderHealthSummary> = {}
        for (let i = 0; i < names.length; i++) {
          const result = healthResults[i]!
          if (result.status === 'fulfilled') {
            healthMap[names[i]!] = result.value
          } else {
            const reason = getErrorMessage(result.reason)
            log.warn(
              'Failed to fetch health for provider:',
              names[i],
              reason,
            )
          }
        }
        set({ healthMap, listLoading: false })
      } catch (err) {
        if (requestId !== _listRequestId) return
        log.error('Failed to fetch providers:', getErrorMessage(err))
        set({ listLoading: false, listError: getErrorMessage(err) })
      }
    },

    setSearchQuery: (q: string) => set({ searchQuery: q }),
    setHealthFilter: (h: ProviderHealthStatus | null) => set({ healthFilter: h }),
    setSortBy: (key: ProviderSortKey) => set({ sortBy: key }),
    setSortDirection: (dir: 'asc' | 'desc') => set({ sortDirection: dir }),
  }
}
