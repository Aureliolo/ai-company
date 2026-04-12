import { create } from 'zustand'
import { createInstallActions } from './mcp-catalog/install-actions'
import { createListActions } from './mcp-catalog/list-actions'
import type { InstallContext, McpCatalogState } from './mcp-catalog/types'

export type {
  InstallContext,
  InstallFlowState,
  McpCatalogState,
} from './mcp-catalog/types'

const EMPTY_INSTALL_CONTEXT: InstallContext = {
  entryId: null,
  connectionName: null,
  errorMessage: null,
  result: null,
}

const INITIAL_STATE = {
  entries: [] as const,
  loading: false,
  error: null,
  searchQuery: '',
  searchLoading: false,
  searchResults: null,
  selectedEntry: null,
  installedEntryIds: new Set<string>(),
  installFlow: 'idle' as const,
  installContext: EMPTY_INSTALL_CONTEXT,
}

export const useMcpCatalogStore = create<McpCatalogState>()((set, get) => ({
  ...INITIAL_STATE,
  ...createListActions(set),
  ...createInstallActions(set, get),
  reset: () =>
    set({
      ...INITIAL_STATE,
      installedEntryIds: new Set<string>(),
      installContext: { ...EMPTY_INSTALL_CONTEXT },
    }),
}))
