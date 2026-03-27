import { describe, expect, it } from 'vitest'
import { buildOrgTree } from '@/pages/org/build-org-tree'
import type { AgentConfig, CompanyConfig, DepartmentHealth, DepartmentName } from '@/api/types'

// ── Test helpers ────────────────────────────────────────────

function makeAgent(overrides: Partial<AgentConfig> & { id: string; name: string }): AgentConfig {
  return {
    role: 'Developer',
    department: 'engineering' as DepartmentName,
    level: 'mid',
    status: 'active',
    personality: {
      traits: [],
      communication_style: 'direct',
      risk_tolerance: 'medium',
      creativity: 'medium',
      description: '',
      openness: 0.5,
      conscientiousness: 0.5,
      extraversion: 0.5,
      agreeableness: 0.5,
      stress_response: 0.5,
      decision_making: 'analytical',
      collaboration: 'team',
      verbosity: 'balanced',
      conflict_approach: 'collaborate',
    },
    model: { provider: 'test', model_id: 'test-001', temperature: 0.7, max_tokens: 4096, fallback_model: null },
    skills: { primary: [], secondary: [] },
    memory: { type: 'session', retention_days: null },
    tools: { access_level: 'standard', allowed: [], denied: [] },
    autonomy_level: null,
    hiring_date: '2026-01-01',
    ...overrides,
  }
}

function makeConfig(agents: AgentConfig[], departments?: CompanyConfig['departments']): CompanyConfig {
  // Auto-generate departments from agents if not provided
  const deptNames = [...new Set(agents.map((a) => a.department))]
  return {
    company_name: 'Test Corp',
    agents,
    departments: departments ?? deptNames.map((name) => ({
      name,
      display_name: name.charAt(0).toUpperCase() + name.slice(1),
      teams: [],
    })),
  }
}

function makeHealth(name: DepartmentName, health: number): DepartmentHealth {
  return {
    name,
    display_name: name.charAt(0).toUpperCase() + name.slice(1),
    health_percent: health,
    agent_count: 3,
    task_count: 5,
    cost_usd: 12.5,
  }
}

// ── Tests ───────────────────────────────────────────────────

describe('buildOrgTree', () => {
  it('returns empty nodes and edges for empty config', () => {
    const config = makeConfig([])
    const result = buildOrgTree(config, {}, [])
    expect(result.nodes).toEqual([])
    expect(result.edges).toEqual([])
  })

  it('identifies CEO from c_suite agent in executive department', () => {
    const agents = [
      makeAgent({ id: 'ceo-1', name: 'Alice', role: 'CEO', department: 'executive', level: 'c_suite' }),
      makeAgent({ id: 'dev-1', name: 'Bob', department: 'engineering', level: 'senior' }),
    ]
    const config = makeConfig(agents)
    const result = buildOrgTree(config, {}, [])

    const ceoNode = result.nodes.find((n) => n.type === 'ceo')
    expect(ceoNode).toBeDefined()
    expect(ceoNode!.data.name).toBe('Alice')
  })

  it('falls back to c_suite agent in non-executive department as CEO', () => {
    const agents = [
      makeAgent({ id: 'cto', name: 'CTO', department: 'engineering', level: 'c_suite' }),
      makeAgent({ id: 'dev', name: 'Dev', department: 'engineering', level: 'mid' }),
    ]
    const config = makeConfig(agents)
    const result = buildOrgTree(config, {}, [])

    const ceoNode = result.nodes.find((n) => n.type === 'ceo')
    expect(ceoNode).toBeDefined()
    expect(ceoNode!.data.name).toBe('CTO')
  })

  it('falls back to highest-seniority agent as CEO when no executive dept', () => {
    const agents = [
      makeAgent({ id: 'lead-1', name: 'Carol', department: 'engineering', level: 'lead' }),
      makeAgent({ id: 'jr-1', name: 'Dave', department: 'engineering', level: 'junior' }),
    ]
    const config = makeConfig(agents)
    const result = buildOrgTree(config, {}, [])

    const ceoNode = result.nodes.find((n) => n.type === 'ceo')
    expect(ceoNode).toBeDefined()
    expect(ceoNode!.data.name).toBe('Carol')
  })

  it('creates a single CEO node for a single-agent org', () => {
    const agents = [
      makeAgent({ id: 'solo', name: 'Eve', department: 'executive', level: 'c_suite' }),
    ]
    const config = makeConfig(agents)
    const result = buildOrgTree(config, {}, [])

    expect(result.nodes.filter((n) => n.type === 'ceo')).toHaveLength(1)
    expect(result.nodes.filter((n) => n.type === 'agent')).toHaveLength(0)
    expect(result.edges).toHaveLength(0)
  })

  it('groups agents by department', () => {
    const agents = [
      makeAgent({ id: 'a1', name: 'A1', department: 'engineering', level: 'lead' }),
      makeAgent({ id: 'a2', name: 'A2', department: 'engineering', level: 'mid' }),
      makeAgent({ id: 'a3', name: 'A3', department: 'product', level: 'lead' }),
    ]
    const config = makeConfig(agents)
    const result = buildOrgTree(config, {}, [])

    const deptNodes = result.nodes.filter((n) => n.type === 'department')
    expect(deptNodes).toHaveLength(2)

    const engAgents = result.nodes.filter((n) => n.parentId === 'dept-engineering')
    expect(engAgents).toHaveLength(2)

    const prodAgents = result.nodes.filter((n) => n.parentId === 'dept-product')
    expect(prodAgents).toHaveLength(1)
  })

  it('creates edges from CEO to department heads', () => {
    const agents = [
      makeAgent({ id: 'ceo', name: 'CEO', department: 'executive', level: 'c_suite' }),
      makeAgent({ id: 'cto', name: 'CTO', department: 'engineering', level: 'c_suite' }),
      makeAgent({ id: 'cpo', name: 'CPO', department: 'product', level: 'c_suite' }),
    ]
    const config = makeConfig(agents)
    const result = buildOrgTree(config, {}, [])

    const ceoEdges = result.edges.filter((e) => e.source === 'ceo')
    expect(ceoEdges).toHaveLength(2)
    expect(ceoEdges.map((e) => e.target).sort()).toEqual(['cpo', 'cto'])
  })

  it('breaks ties deterministically for same-level peers (first in array wins)', () => {
    const agents = [
      makeAgent({ id: 'ceo', name: 'CEO', department: 'executive', level: 'c_suite' }),
      makeAgent({ id: 'vp-a', name: 'VP Alpha', department: 'engineering', level: 'vp' }),
      makeAgent({ id: 'vp-b', name: 'VP Beta', department: 'engineering', level: 'vp' }),
      makeAgent({ id: 'vp-c', name: 'VP Gamma', department: 'engineering', level: 'vp' }),
    ]
    const config = makeConfig(agents)
    const result = buildOrgTree(config, {}, [])

    // Department head should be vp-a (first VP in array order)
    const ceoEdges = result.edges.filter((e) => e.source === 'ceo')
    expect(ceoEdges.map((e) => e.target)).toEqual(['vp-a'])

    // vp-a is dept head; vp-b and vp-c report to vp-a
    const headEdges = result.edges.filter((e) => e.source === 'vp-a')
    expect(headEdges.map((e) => e.target).sort()).toEqual(['vp-b', 'vp-c'])
  })

  it('creates edges from department head to team members', () => {
    const agents = [
      makeAgent({ id: 'lead', name: 'Lead', department: 'engineering', level: 'lead' }),
      makeAgent({ id: 'dev1', name: 'Dev1', department: 'engineering', level: 'mid' }),
      makeAgent({ id: 'dev2', name: 'Dev2', department: 'engineering', level: 'junior' }),
    ]
    const config = makeConfig(agents)
    const result = buildOrgTree(config, {}, [])

    // Lead is CEO (highest seniority). Dept head = dev1 (next highest).
    // Hierarchy: lead (CEO) -> dev1 (dept head) -> dev2 (member)
    const leadEdges = result.edges.filter((e) => e.source === 'lead')
    expect(leadEdges.map((e) => e.target)).toEqual(['dev1'])

    const dev1Edges = result.edges.filter((e) => e.source === 'dev1')
    expect(dev1Edges.map((e) => e.target)).toEqual(['dev2'])
  })

  it('excludes terminated agents from the chart', () => {
    const agents = [
      makeAgent({ id: 'active-1', name: 'Active', department: 'engineering', level: 'lead', status: 'active' }),
      makeAgent({ id: 'fired-1', name: 'Fired', department: 'engineering', level: 'mid', status: 'terminated' }),
    ]
    const config = makeConfig(agents)
    const result = buildOrgTree(config, {}, [])

    const agentNodes = result.nodes.filter((n) => n.type === 'agent' || n.type === 'ceo')
    expect(agentNodes).toHaveLength(1)
    expect(agentNodes[0]!.data.name).toBe('Active')
  })

  it('creates department group nodes with health data', () => {
    const agents = [
      makeAgent({ id: 'a1', name: 'Dev', department: 'engineering', level: 'mid' }),
    ]
    const config = makeConfig(agents)
    const healthData = [makeHealth('engineering', 85)]
    const result = buildOrgTree(config, {}, healthData)

    const deptNode = result.nodes.find((n) => n.type === 'department')
    expect(deptNode).toBeDefined()
    expect(deptNode!.data.healthPercent).toBe(85)
    expect(deptNode!.data.taskCount).toBe(5)
    expect(deptNode!.data.costUsd).toBe(12.5)
  })

  it('uses runtime status from the status map', () => {
    const agents = [
      makeAgent({ id: 'a1', name: 'Dev', department: 'engineering', level: 'mid', status: 'active' }),
    ]
    const config = makeConfig(agents)
    const result = buildOrgTree(config, { 'a1': 'error' }, [])

    const agentNode = result.nodes.find((n) => n.id === 'a1')
    expect(agentNode!.data.runtimeStatus).toBe('error')
  })

  it('uses team structure to derive reporting hierarchy', () => {
    const agents = [
      makeAgent({ id: 'lead', name: 'Lead', department: 'engineering', level: 'lead' }),
      makeAgent({ id: 'sr', name: 'Senior', department: 'engineering', level: 'senior' }),
      makeAgent({ id: 'jr', name: 'Junior', department: 'engineering', level: 'junior' }),
    ]
    const config = makeConfig(agents, [
      {
        name: 'engineering',
        display_name: 'Engineering',
        teams: [
          { name: 'backend', members: ['Lead', 'Senior', 'Junior'] },
        ],
      },
    ])
    const result = buildOrgTree(config, {}, [])

    // Lead is CEO (highest seniority) and team lead.
    // Senior and Junior report to Lead via team membership.
    // CEO-to-dept-head edge (lead->sr) is deduplicated with team edge.
    const leadEdges = result.edges.filter((e) => e.source === 'lead')
    expect(leadEdges.map((e) => e.target).sort()).toEqual(['jr', 'sr'])
    // No duplicate edges
    const edgeIds = result.edges.map((e) => e.id)
    expect(new Set(edgeIds).size).toBe(edgeIds.length)
  })

  it('renders empty departments with zero agent count', () => {
    const agents = [
      makeAgent({ id: 'a1', name: 'Dev', department: 'engineering', level: 'mid' }),
    ]
    const config: CompanyConfig = {
      company_name: 'Test',
      agents,
      departments: [
        { name: 'engineering', display_name: 'Engineering', teams: [] },
        { name: 'product', display_name: 'Product', teams: [] },
      ],
    }
    const result = buildOrgTree(config, {}, [])

    const deptNodes = result.nodes.filter((n) => n.type === 'department')
    expect(deptNodes).toHaveLength(2)
    // Empty department is still rendered
    const productDept = deptNodes.find((n) => n.data.departmentName === 'product')
    expect(productDept).toBeDefined()
    expect(productDept!.data.agentCount).toBe(0)
  })

  it('assigns correct node types', () => {
    const agents = [
      makeAgent({ id: 'ceo', name: 'CEO', department: 'executive', level: 'c_suite' }),
      makeAgent({ id: 'dev', name: 'Dev', department: 'engineering', level: 'mid' }),
    ]
    const config = makeConfig(agents)
    const result = buildOrgTree(config, {}, [])

    const types = result.nodes.map((n) => n.type).sort()
    expect(types).toEqual(['agent', 'ceo', 'department', 'department'])
  })

  it('returns null health when no health data provided', () => {
    const agents = [
      makeAgent({ id: 'a1', name: 'Dev', department: 'engineering', level: 'mid' }),
    ]
    const config = makeConfig(agents)
    const result = buildOrgTree(config, {}, [])

    const deptNode = result.nodes.find((n) => n.type === 'department')
    expect(deptNode!.data.healthPercent).toBeNull()
    expect(deptNode!.data.taskCount).toBeNull()
  })

  it('includes companyName in CEO node data', () => {
    const agents = [
      makeAgent({ id: 'ceo', name: 'Boss', department: 'executive', level: 'c_suite' }),
    ]
    const config = makeConfig(agents)
    config.company_name = 'Acme Inc'
    const result = buildOrgTree(config, {}, [])

    const ceoNode = result.nodes.find((n) => n.type === 'ceo')
    expect(ceoNode!.data.companyName).toBe('Acme Inc')
  })

  it('all edges have type "hierarchy"', () => {
    const agents = [
      makeAgent({ id: 'ceo', name: 'CEO', department: 'executive', level: 'c_suite' }),
      makeAgent({ id: 'cto', name: 'CTO', department: 'engineering', level: 'c_suite' }),
      makeAgent({ id: 'dev', name: 'Dev', department: 'engineering', level: 'mid' }),
    ]
    const config = makeConfig(agents)
    const result = buildOrgTree(config, {}, [])

    for (const edge of result.edges) {
      expect(edge.type).toBe('hierarchy')
    }
  })
})
