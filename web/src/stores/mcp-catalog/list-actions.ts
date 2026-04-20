import {
  browseMcpCatalog,
  searchMcpCatalog,
} from '@/api/endpoints/mcp-catalog'
import type { McpCatalogEntry } from '@/api/types/integrations'
import { createLogger } from '@/lib/logger'
import { getErrorMessage } from '@/utils/errors'
import type { McpCatalogSet, McpCatalogState } from './types'

const log = createLogger('mcp-catalog')

let _searchDebounceHandle: ReturnType<typeof setTimeout> | null = null
let _searchGeneration = 0

export function createListActions(set: McpCatalogSet) {
  return {
    fetchCatalog: async () => {
      set({ loading: true, error: null })
      try {
        const entries = await browseMcpCatalog()
        set({ entries, loading: false })
      } catch (err) {
        log.error('Failed to fetch MCP catalog:', getErrorMessage(err))
        set({
          loading: false,
          error: getErrorMessage(err),
        })
      }
    },

    setSearchQuery: async (q: string) => {
      set({ searchQuery: q })
      if (_searchDebounceHandle !== null) {
        clearTimeout(_searchDebounceHandle)
        _searchDebounceHandle = null
      }
      if (!q.trim()) {
        set({ searchResults: null, searchLoading: false })
        return
      }
      set({ searchLoading: true })
      const generation = ++_searchGeneration
      _searchDebounceHandle = setTimeout(async () => {
        if (generation !== _searchGeneration) return
        try {
          const results = await searchMcpCatalog(q)
          if (generation !== _searchGeneration) return
          set({
            searchResults: results as readonly McpCatalogEntry[],
            searchLoading: false,
          })
        } catch (err) {
          if (generation !== _searchGeneration) return
          log.warn('MCP search failed:', getErrorMessage(err))
          set({ searchResults: [], searchLoading: false })
        }
      }, 200)
    },

    selectEntry: (entry: McpCatalogState['selectedEntry']) =>
      set({ selectedEntry: entry }),
  }
}
