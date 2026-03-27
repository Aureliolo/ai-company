import { Search } from 'lucide-react'
import { useAgentsStore } from '@/stores/agents'
import { DEPARTMENT_NAME_VALUES, SENIORITY_LEVEL_VALUES, AGENT_STATUS_VALUES } from '@/api/types'
import { formatLabel } from '@/utils/format'
import { cn } from '@/lib/utils'

export function AgentFilters({ className }: { className?: string }) {
  const searchQuery = useAgentsStore((s) => s.searchQuery)
  const departmentFilter = useAgentsStore((s) => s.departmentFilter)
  const levelFilter = useAgentsStore((s) => s.levelFilter)
  const statusFilter = useAgentsStore((s) => s.statusFilter)
  const sortBy = useAgentsStore((s) => s.sortBy)

  const setSearchQuery = useAgentsStore((s) => s.setSearchQuery)
  const setDepartmentFilter = useAgentsStore((s) => s.setDepartmentFilter)
  const setLevelFilter = useAgentsStore((s) => s.setLevelFilter)
  const setStatusFilter = useAgentsStore((s) => s.setStatusFilter)
  const setSortBy = useAgentsStore((s) => s.setSortBy)

  return (
    <div className={cn('flex flex-wrap items-center gap-3', className)}>
      {/* Search */}
      <div className="relative flex-1 min-w-48 max-w-sm">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
        <input
          type="text"
          placeholder="Search by name or role..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="h-9 w-full rounded-lg border border-border bg-card pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-accent focus:outline-none"
          aria-label="Search agents"
        />
      </div>

      {/* Department */}
      <select
        value={departmentFilter ?? ''}
        onChange={(e) => setDepartmentFilter(e.target.value ? e.target.value as typeof departmentFilter : null)}
        className="h-9 rounded-lg border border-border bg-card px-3 text-sm text-foreground focus:border-accent focus:outline-none"
        aria-label="Filter by department"
      >
        <option value="">All departments</option>
        {DEPARTMENT_NAME_VALUES.map((d) => (
          <option key={d} value={d}>{formatLabel(d)}</option>
        ))}
      </select>

      {/* Level */}
      <select
        value={levelFilter ?? ''}
        onChange={(e) => setLevelFilter(e.target.value ? e.target.value as typeof levelFilter : null)}
        className="h-9 rounded-lg border border-border bg-card px-3 text-sm text-foreground focus:border-accent focus:outline-none"
        aria-label="Filter by level"
      >
        <option value="">All levels</option>
        {SENIORITY_LEVEL_VALUES.map((l) => (
          <option key={l} value={l}>{formatLabel(l)}</option>
        ))}
      </select>

      {/* Status */}
      <select
        value={statusFilter ?? ''}
        onChange={(e) => setStatusFilter(e.target.value ? e.target.value as typeof statusFilter : null)}
        className="h-9 rounded-lg border border-border bg-card px-3 text-sm text-foreground focus:border-accent focus:outline-none"
        aria-label="Filter by status"
      >
        <option value="">All statuses</option>
        {AGENT_STATUS_VALUES.map((s) => (
          <option key={s} value={s}>{formatLabel(s)}</option>
        ))}
      </select>

      {/* Sort */}
      <select
        value={sortBy}
        onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
        className="h-9 rounded-lg border border-border bg-card px-3 text-sm text-foreground focus:border-accent focus:outline-none"
        aria-label="Sort agents by"
      >
        <option value="name">Sort: Name</option>
        <option value="department">Sort: Department</option>
        <option value="level">Sort: Level</option>
        <option value="status">Sort: Status</option>
        <option value="hiring_date">Sort: Hire date</option>
      </select>
    </div>
  )
}
