export type AgentStatus = "active" | "idle" | "warning" | "error" | "onboarding"

export interface Agent {
  id: string
  name: string
  shortName: string
  role: string
  department: string
  level: "Junior" | "Mid" | "Senior" | "Lead" | "VP" | "C-Suite"
  status: AgentStatus
  autonomyLevel: string
  hiredDate: string
  performance: AgentPerformance
  tools: string[]
  taskHistory: TaskEntry[]
  recentActivity: ActivityEntry[]
  careerTimeline: CareerEvent[]
}

export interface AgentPerformance {
  tasksCompleted: number
  avgCompletionTime: number
  successRate: number
  costEfficiency: number
}

export interface TaskEntry {
  id: string
  name: string
  type:
    | "research"
    | "analysis"
    | "report"
    | "development"
    | "review"
    | "operations"
    | "design"
    | "outreach"
  start: number
  duration: number
  completed: boolean
}

export interface ActivityEntry {
  time: string
  type:
    | "complete"
    | "receive"
    | "tool"
    | "start"
    | "submit"
    | "flag"
    | "approve"
    | "delegate"
  description: string
  icon: string
}

export interface CareerEvent {
  date: string
  event: string
  type: "hire" | "promote" | "milestone" | "reassign" | "trust-upgrade"
}

export interface Department {
  name: string
  health: number
  agents: number
  activeAgents: number
  tasks: number
  cost: number
  vpId: string
}

export interface FeedEvent {
  id: number
  time: string
  minutesAgo: number
  agent: string
  agentFull: string
  action: string
  task: string
  to: string | null
  toFull: string | null
  type:
    | "complete"
    | "approve"
    | "delegate"
    | "start"
    | "submit"
    | "flag"
    | "receive"
    | "tool"
}

export interface BudgetDay {
  day: string
  actual: number | null
  forecast: number | null
}

export interface Company {
  name: string
  budget: number
  spentToday: number
  budgetPercent: number
  activeAgents: number
  totalAgents: number
  tasksRunning: number
  pendingApprovals: number
  uptime: number
}
