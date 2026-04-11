import {
  browseMcpCatalog,
  searchMcpCatalog,
} from '@/api/endpoints/mcp-catalog'
import type { McpCatalogEntry } from '@/api/types'
import { createLogger } from '@/lib/logger'
import { getErrorMessage } from '@/utils/errors'
import type { McpCatalogSet, McpCatalogState } from './types'

const log = createLogger('mcp-catalog')

let _searchDebounceHandle: ReturnType<typeof setTimeout> | null = null

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
      if (_searchDebounceHandle !== null) clearTimeout(_searchDebounceHandle)
      if (!q.trim()) {
        set({ searchResults: null, searchLoading: false })
        return
      }
      set({ searchLoading: true })
      await new Promise<void>((resolve) => {
        _searchDebounceHandle = setTimeout(resolve, 200)
      })
      try {
        const results = await searchMcpCatalog(q)
        set({
          searchResults: results as readonly McpCatalogEntry[],
          searchLoading: false,
        })
      } catch (err) {
        log.warn('MCP search failed:', getErrorMessage(err))
        set({ searchResults: [], searchLoading: false })
      }
    },

    selectEntry: (entry: McpCatalogState['selectedEntry']) =>
      set({ selectedEntry: entry }),
  }
}
