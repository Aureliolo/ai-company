import { useParams } from "react-router-dom"
import type { ReactNode } from "react"
import {
  GridIcon,
  OrgIcon,
  AgentIcon,
  TaskIcon,
  BudgetIcon,
  ApprovalIcon,
  MessageIcon,
  MeetingIcon,
  ProviderIcon,
  SettingsIcon,
  SearchIcon,
} from "@/components/nav-icons.tsx"
import { company } from "@/data/index.ts"

export interface NavEntry {
  label: string
  href: string
  icon: ReactNode
  badge?: number
}

export function useNavItems(): NavEntry[] {
  return [
    { label: "Overview", href: "/dashboard", icon: <GridIcon /> },
    { label: "Org Chart", href: "#", icon: <OrgIcon /> },
    { label: "Agents", href: "/agent/ceo", icon: <AgentIcon /> },
    { label: "Tasks", href: "#", icon: <TaskIcon /> },
    { label: "Budget", href: "#", icon: <BudgetIcon /> },
    {
      label: "Approvals",
      href: "#",
      icon: <ApprovalIcon />,
      badge: company.pendingApprovals,
    },
    { label: "Messages", href: "#", icon: <MessageIcon /> },
    { label: "Meetings", href: "#", icon: <MeetingIcon /> },
    { label: "Providers", href: "#", icon: <ProviderIcon /> },
    { label: "Settings", href: "#", icon: <SettingsIcon /> },
  ]
}

export function SidebarHeader({ compact }: { compact?: boolean }) {
  const { variation } = useParams()
  if (compact) {
    return (
      <div className="p-2 border-b border-border flex items-center justify-center">
        <div className="w-7 h-7 rounded-md bg-accent/[0.12] border border-accent/25 flex items-center justify-center">
          <span className="text-accent text-xs font-bold font-mono">N</span>
        </div>
      </div>
    )
  }

  return (
    <div className="px-4 pt-4 pb-3 border-b border-border">
      <div className="flex items-center gap-2">
        <div className="w-7 h-7 rounded-md bg-accent/[0.12] border border-accent/25 flex items-center justify-center">
          <span className="text-accent text-xs font-bold font-mono">N</span>
        </div>
        <div>
          <div className="text-xs font-semibold text-text-primary leading-tight">
            {company.name}
          </div>
          <div className="text-[10px] text-text-muted mt-0.5">
            {company.totalAgents} agents --{" "}
            <span className="capitalize">{variation}</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export function SidebarSearch({ compact }: { compact?: boolean }) {
  if (compact) return null

  return (
    <div className="px-3 pt-3 pb-4 border-t border-border">
      <div className="flex items-center gap-2 bg-bg-card border border-border rounded-md px-2.5 py-1.5 cursor-pointer hover:border-border-bright transition-colors">
        <SearchIcon />
        <span className="text-xs text-text-muted flex-1">Search...</span>
        <span className="text-[10px] text-text-muted font-mono bg-border px-1 py-px rounded">
          Ctrl+K
        </span>
      </div>
    </div>
  )
}
