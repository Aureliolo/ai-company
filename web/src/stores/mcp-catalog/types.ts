import type { StoreApi } from 'zustand'
import type { McpCatalogEntry, McpInstallResponse } from '@/api/types'

export type InstallFlowState =
  | 'idle'
  | 'picking-connection'
  | 'creating-connection'
  | 'oauth-pending'
  | 'installing'
  | 'done'
  | 'error'

export interface InstallContext {
  readonly entryId: string | null
  readonly connectionName: string | null
  readonly errorMessage: string | null
  readonly result: McpInstallResponse | null
}

export interface McpCatalogState {
  // Catalog list
  entries: readonly McpCatalogEntry[]
  loading: boolean
  error: string | null

  // Search
  searchQuery: string
  searchLoading: boolean
  searchResults: readonly McpCatalogEntry[] | null

  // Detail drawer
  selectedEntry: McpCatalogEntry | null

  // Installed entries (by entry id) -- populated by the install store
  installedEntryIds: ReadonlySet<string>

  // Install flow
  installFlow: InstallFlowState
  installContext: InstallContext

  // Actions
  fetchCatalog: () => Promise<void>
  setSearchQuery: (q: string) => Promise<void>
  selectEntry: (entry: McpCatalogEntry | null) => void
  startInstall: (entryId: string) => void
  setInstallConnection: (connectionName: string | null) => void
  confirmInstall: () => Promise<McpInstallResponse | null>
  uninstall: (entryId: string) => Promise<boolean>
  resetInstall: () => void
  reset: () => void
}

export type McpCatalogSet = StoreApi<McpCatalogState>['setState']
export type McpCatalogGet = StoreApi<McpCatalogState>['getState']
