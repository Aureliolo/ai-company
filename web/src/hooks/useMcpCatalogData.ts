import { useEffect, useMemo } from 'react'
import type { McpCatalogEntry } from '@/api/types/integrations'
import { useMcpCatalogStore } from '@/stores/mcp-catalog'

export interface UseMcpCatalogDataReturn {
  entries: readonly McpCatalogEntry[]
  visibleEntries: readonly McpCatalogEntry[]
  loading: boolean
  searchLoading: boolean
  searchQuery: string
  hasSearch: boolean
  error: string | null
}

export function useMcpCatalogData(): UseMcpCatalogDataReturn {
  const entries = useMcpCatalogStore((s) => s.entries)
  const loading = useMcpCatalogStore((s) => s.loading)
  const error = useMcpCatalogStore((s) => s.error)
  const searchQuery = useMcpCatalogStore((s) => s.searchQuery)
  const searchResults = useMcpCatalogStore((s) => s.searchResults)
  const searchLoading = useMcpCatalogStore((s) => s.searchLoading)

  useEffect(() => {
    if (entries.length === 0 && !loading) {
      void useMcpCatalogStore.getState().fetchCatalog()
    }
    // eslint-disable-next-line @eslint-react/exhaustive-deps
  }, [])

  const visibleEntries = useMemo<readonly McpCatalogEntry[]>(() => {
    if (searchResults !== null) return searchResults
    return entries
  }, [entries, searchResults])

  return {
    entries,
    visibleEntries,
    loading,
    searchLoading,
    searchQuery,
    hasSearch: searchQuery.trim().length > 0,
    error,
  }
}
