import type { Node, Edge } from '@xyflow/react'
import type { AgentConfig, CompanyConfig, DepartmentHealth, DepartmentName, SeniorityLevel } from '@/api/types'
import type { AgentRuntimeStatus } from '@/lib/utils'
import { resolveRuntimeStatus } from './status-mapping'

// ── Node data interfaces ────────────────────────────────────

export interface AgentNodeData {
  agentId: string
  name: string
  role: string
  department: DepartmentName
  level: SeniorityLevel
  runtimeStatus: AgentRuntimeStatus
  [key: string]: unknown
}

export interface CeoNodeData extends AgentNodeData {
  companyName: string
  [key: string]: unknown
}

export interface DepartmentGroupData {
  departmentName: DepartmentName
  displayName: string
  healthPercent: number | null
  agentCount: number
  activeCount: number
  taskCount: number | null
  costUsd: number | null
  [key: string]: unknown
}

// ── Seniority ordering ──────────────────────────────────────

const SENIORITY_RANK: Record<SeniorityLevel, number> = {
  c_suite: 7,
  vp: 6,
  director: 5,
  principal: 4,
  lead: 3,
  senior: 2,
  mid: 1,
  junior: 0,
}

function seniorityOf(level: SeniorityLevel): number {
  return SENIORITY_RANK[level] ?? -1
}

// ── Core tree-building function ─────────────────────────────

export interface OrgTree {
  nodes: Node[]
  edges: Edge[]
}

/**
 * Build React Flow nodes and edges from a CompanyConfig.
 *
 * Derives hierarchy from seniority levels and team membership:
 * 1. CEO = highest-seniority agent in executive dept (or globally)
 * 2. Department heads = highest-seniority agent per department
 * 3. Team structure from Department.teams[].members
 *
 * Terminated agents are excluded from the chart.
 */
export function buildOrgTree(
  config: CompanyConfig,
  runtimeStatuses: Record<string, AgentRuntimeStatus>,
  departmentHealths: readonly DepartmentHealth[],
): OrgTree {
  // Filter out terminated agents
  const agents = config.agents.filter((a) => a.status !== 'terminated')

  const healthMap = new Map(departmentHealths.map((h) => [h.name, h]))
  const nodes: Node[] = []
  const edges: Edge[] = []

  // Group agents by department
  const deptAgents = new Map<DepartmentName, AgentConfig[]>()
  for (const agent of agents) {
    const list = deptAgents.get(agent.department) ?? []
    list.push(agent)
    deptAgents.set(agent.department, list)
  }

  // Identify CEO: highest seniority in executive, or highest globally
  const ceo = findCeo(agents)

  // Build department group nodes + agent nodes
  for (const dept of config.departments) {
    const deptMembers = deptAgents.get(dept.name) ?? []
    const health = healthMap.get(dept.name)
    const activeCount = deptMembers.filter(
      (a) => resolveRuntimeStatus(a.id, a.status, runtimeStatuses) === 'active',
    ).length

    // Department group node
    const groupId = `dept-${dept.name}`
    nodes.push({
      id: groupId,
      type: 'department',
      position: { x: 0, y: 0 },
      data: {
        departmentName: dept.name,
        displayName: dept.display_name,
        healthPercent: health?.health_percent ?? null,
        agentCount: deptMembers.length,
        activeCount,
        taskCount: health?.task_count ?? null,
        costUsd: health?.cost_usd ?? null,
      } satisfies DepartmentGroupData,
    })

    // Find department head (highest seniority, excluding CEO if they're in executive)
    const head = findDepartmentHead(deptMembers, ceo)

    // Build team membership map for this department
    const teamMemberSet = new Map<string, string>() // agentId -> teamLeadId
    for (const team of dept.teams) {
      const teamMembers = deptMembers.filter((a) => team.members.includes(a.name))
      const teamLead = findHighestSeniority(teamMembers)
      for (const member of teamMembers) {
        if (teamLead && member.id !== teamLead.id && !teamMemberSet.has(member.id)) {
          teamMemberSet.set(member.id, teamLead.id)
        }
      }
    }

    // Create agent nodes and edges within this department
    for (const agent of deptMembers) {
      const isCeo = ceo && agent.id === ceo.id
      const runtimeStatus = resolveRuntimeStatus(agent.id, agent.status, runtimeStatuses)

      const nodeData: AgentNodeData = {
        agentId: agent.id,
        name: agent.name,
        role: agent.role,
        department: agent.department,
        level: agent.level,
        runtimeStatus,
      }

      nodes.push({
        id: agent.id,
        type: isCeo ? 'ceo' : 'agent',
        position: { x: 0, y: 0 },
        parentId: groupId,
        data: isCeo
          ? { ...nodeData, companyName: config.company_name } satisfies CeoNodeData
          : nodeData,
      })

      // Create edges
      if (isCeo) {
        // CEO connects to all department heads
        // (edges created below after all nodes exist)
      } else if (teamMemberSet.has(agent.id)) {
        // Agent reports to team lead
        const leadId = teamMemberSet.get(agent.id)!
        edges.push({
          id: `e-${leadId}-${agent.id}`,
          source: leadId,
          target: agent.id,
          type: 'hierarchy',
        })
      } else if (head && agent.id !== head.id) {
        // Agent reports to department head
        edges.push({
          id: `e-${head.id}-${agent.id}`,
          source: head.id,
          target: agent.id,
          type: 'hierarchy',
        })
      }
    }

    // Edge from CEO to department head (avoid duplicate if already connected via team)
    if (ceo && head && ceo.id !== head.id) {
      const alreadyConnected = edges.some(
        (e) => e.source === ceo.id && e.target === head.id,
      )
      if (!alreadyConnected) {
        edges.push({
          id: `e-${ceo.id}-${head.id}`,
          source: ceo.id,
          target: head.id,
          type: 'hierarchy',
        })
      }
    }
  }

  return { nodes, edges }
}

// ── Helper functions ────────────────────────────────────────

/** Return the highest-seniority agent. Ties are broken by array order (first wins). */
function findHighestSeniority(agents: readonly AgentConfig[]): AgentConfig | null {
  if (agents.length === 0) return null
  return agents.reduce((best, curr) =>
    seniorityOf(curr.level) > seniorityOf(best.level) ? curr : best,
  )
}

/** Identify the CEO. Ties at each priority level are broken by array order (first wins). */
function findCeo(agents: readonly AgentConfig[]): AgentConfig | null {
  // Prefer c_suite in executive department
  const execCSuite = agents.filter(
    (a) => a.department === 'executive' && a.level === 'c_suite',
  )
  if (execCSuite.length > 0) return execCSuite[0]!

  // Fall back to any c_suite agent
  const cSuite = agents.filter((a) => a.level === 'c_suite')
  if (cSuite.length > 0) return cSuite[0]!

  // Fall back to highest seniority globally
  return findHighestSeniority(agents)
}

function findDepartmentHead(
  members: readonly AgentConfig[],
  ceo: AgentConfig | null,
): AgentConfig | null {
  // Department head is the highest-seniority member, excluding CEO
  const candidates = ceo ? members.filter((m) => m.id !== ceo.id) : members
  return findHighestSeniority(candidates)
}
