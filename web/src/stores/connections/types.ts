import type { StoreApi } from 'zustand'
import type {
  Connection,
  ConnectionHealthStatus,
  ConnectionType,
  CreateConnectionRequest,
  HealthReport,
  UpdateConnectionRequest,
} from '@/api/types/integrations'

export type ConnectionSortKey = 'name' | 'type' | 'health' | 'created_at'

export interface ConnectionsState {
  // List
  connections: readonly Connection[]
  healthMap: Record<string, HealthReport>
  listLoading: boolean
  listError: string | null

  // Filters
  searchQuery: string
  typeFilter: ConnectionType | null
  healthFilter: ConnectionHealthStatus | null
  sortBy: ConnectionSortKey
  sortDirection: 'asc' | 'desc'

  // Per-row UI state
  checkingHealth: readonly string[]
  mutating: boolean

  // Actions
  fetchConnections: () => Promise<void>
  createConnection: (data: CreateConnectionRequest) => Promise<Connection | null>
  updateConnection: (
    name: string,
    data: UpdateConnectionRequest,
  ) => Promise<Connection | null>
  deleteConnection: (name: string) => Promise<boolean>
  runHealthCheck: (name: string) => Promise<void>
  setSearchQuery: (q: string) => void
  setTypeFilter: (t: ConnectionType | null) => void
  setHealthFilter: (h: ConnectionHealthStatus | null) => void
  setSortBy: (key: ConnectionSortKey) => void
  setSortDirection: (dir: 'asc' | 'desc') => void
  reset: () => void
}

export type ConnectionsSet = StoreApi<ConnectionsState>['setState']
export type ConnectionsGet = StoreApi<ConnectionsState>['getState']
