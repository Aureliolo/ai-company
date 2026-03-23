import type { Department } from "@/data/types"
import { agents } from "@/data/agents"
import { createRng, randFloat } from "@/data/seed"

// ---------------------------------------------------------------------------
// Derive department data from agents
// ---------------------------------------------------------------------------

function buildDepartments(): Department[] {
  const rng = createRng(7777) // separate seed for department-specific randomness

  // Group agents by department (exclude Executive/CEO)
  const deptNames = [
    "Engineering",
    "Marketing",
    "Finance",
    "HR",
    "Product",
    "Sales",
    "Legal",
    "Operations",
  ]

  return deptNames.map((name) => {
    const deptAgents = agents.filter((a) => a.department === name)
    const activeAgents = deptAgents.filter(
      (a) => a.status === "active" || a.status === "idle",
    ).length
    const warningCount = deptAgents.filter(
      (a) => a.status === "warning",
    ).length
    const errorCount = deptAgents.filter(
      (a) => a.status === "error",
    ).length

    // Health computation:
    // - Base: 80-100 when all active/idle
    // - Degrade by 15 per warning agent, 25 per error agent
    // - Floor at 20
    let health: number
    if (errorCount > 0) {
      health = Math.max(20, 65 - errorCount * 25 - warningCount * 10)
    } else if (warningCount > 0) {
      health = Math.max(50, 85 - warningCount * 15)
    } else {
      health = Math.min(100, 80 + Math.floor(rng() * 21))
    }

    // Active tasks: sum of incomplete tasks across dept agents
    const tasks = deptAgents.reduce(
      (sum, a) => sum + a.taskHistory.filter((t) => !t.completed).length,
      0,
    )

    // Daily cost: proportional to agent count and levels
    // VP/C-Suite: $30-50, Senior/Lead: $20-35, Mid: $12-25, Junior: $8-15
    const cost = deptAgents.reduce((sum, a) => {
      switch (a.level) {
        case "C-Suite":
        case "VP":
          return sum + randFloat(rng, 30, 50)
        case "Lead":
        case "Senior":
          return sum + randFloat(rng, 20, 35)
        case "Mid":
          return sum + randFloat(rng, 12, 25)
        case "Junior":
          return sum + randFloat(rng, 8, 15)
      }
    }, 0)

    // Find the VP for this department
    const vp = deptAgents.find(
      (a) => a.level === "VP" || a.level === "C-Suite",
    )

    return {
      name,
      health,
      agents: deptAgents.length,
      activeAgents,
      tasks,
      cost: Math.round(cost * 100) / 100,
      vpId: vp?.id ?? "",
    }
  })
}

export const departments: Department[] = buildDepartments()
