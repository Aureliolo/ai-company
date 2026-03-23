import type { Company } from "@/data/types"
import { agents } from "@/data/agents"
import { departments } from "@/data/departments"
import { budgetHistory } from "@/data/budget"
import { createRng, randInt } from "@/data/seed"

// ---------------------------------------------------------------------------
// Company-level aggregates
// ---------------------------------------------------------------------------

function buildCompany(): Company {
  const rng = createRng(9999)

  const totalAgents = agents.length
  const activeAgents = agents.filter(
    (a) => a.status === "active",
  ).length
  const tasksRunning = agents.filter(
    (a) => a.taskHistory.some((t) => !t.completed),
  ).length

  const spentToday = departments.reduce((sum, d) => sum + d.cost, 0)
  const todayEntry = budgetHistory.find((d) => d.day === "Mar 23")
  const totalSpent = todayEntry?.actual ?? 0
  const budget = 2400

  return {
    name: "Nexus Dynamics",
    budget,
    spentToday: Math.round(spentToday * 100) / 100,
    budgetPercent:
      Math.round((totalSpent / budget) * 10000) / 100,
    activeAgents,
    totalAgents,
    tasksRunning,
    pendingApprovals: randInt(rng, 2, 5),
    uptime: 99.7,
  }
}

export const company: Company = buildCompany()

// ---------------------------------------------------------------------------
// Metric cards with sparkline trends
// ---------------------------------------------------------------------------

function buildMetrics() {
  const rng = createRng(5555)

  // Tasks: total running, change from yesterday, 7-day trend
  const tasksTrend: number[] = []
  let base = company.tasksRunning - 5
  for (let i = 0; i < 7; i++) {
    base += randInt(rng, -2, 3)
    tasksTrend.push(Math.max(5, base))
  }

  // Agents: active/total, 7-day active trend
  const agentsTrend: number[] = []
  base = company.activeAgents - 3
  for (let i = 0; i < 7; i++) {
    base += randInt(rng, -1, 2)
    agentsTrend.push(Math.max(10, Math.min(company.totalAgents, base)))
  }

  // Spend: daily spend trend over 7 days
  const spendTrend: number[] = []
  base = Math.floor(company.spentToday * 0.85)
  for (let i = 0; i < 7; i++) {
    base += randInt(rng, -10, 15)
    spendTrend.push(Math.max(40, base))
  }

  // Approvals: pending over 7 days
  const approvalsTrend: number[] = []
  for (let i = 0; i < 7; i++) {
    approvalsTrend.push(randInt(rng, 1, 7))
  }

  return {
    tasks: {
      value: company.tasksRunning,
      change: randInt(rng, -3, 5),
      trend: tasksTrend,
    },
    agents: {
      active: company.activeAgents,
      total: company.totalAgents,
      trend: agentsTrend,
    },
    spend: {
      value: company.spentToday,
      percent: company.budgetPercent,
      trend: spendTrend,
    },
    approvals: {
      value: company.pendingApprovals,
      trend: approvalsTrend,
    },
  }
}

export const metrics = buildMetrics()
