import { useMemo } from 'react'
import type { SetupAgentSummary } from '@/api/types'
import { cn } from '@/lib/utils'

export interface MiniOrgChartProps {
  agents: readonly SetupAgentSummary[]
  className?: string
}

interface DeptNode {
  name: string
  agents: SetupAgentSummary[]
}

const NODE_WIDTH = 80
const NODE_HEIGHT = 32
const H_GAP = 24
const V_GAP = 48
const AVATAR_RADIUS = 12

function getInitials(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0] ?? '')
    .join('')
    .toUpperCase()
}

interface AgentNodeProps {
  agent: SetupAgentSummary
  agentX: number
  agentY: number
  deptX: number
  deptY: number
}

function AgentNode({ agent, agentX, agentY, deptX, deptY }: AgentNodeProps) {
  return (
    <g>
      {/* Line from dept to agent */}
      <line
        x1={deptX}
        y1={deptY + NODE_HEIGHT / 2}
        x2={agentX}
        y2={agentY - AVATAR_RADIUS}
        className="stroke-border"
        strokeWidth={1}
      />
      {/* Agent circle */}
      <circle
        cx={agentX}
        cy={agentY}
        r={AVATAR_RADIUS}
        className="fill-card stroke-accent/40"
        strokeWidth={1}
      >
        <title>{`${agent.name} - ${agent.role}`}</title>
      </circle>
      <text
        x={agentX}
        y={agentY + 3}
        textAnchor="middle"
        className="fill-foreground text-[8px] font-medium"
      >
        {getInitials(agent.name)}
      </text>
    </g>
  )
}

export function MiniOrgChart({ agents, className }: MiniOrgChartProps) {
  const departments = useMemo(() => {
    const deptMap = new Map<string, SetupAgentSummary[]>()
    for (const agent of agents) {
      const dept = agent.department || 'unassigned'
      const existing = deptMap.get(dept)
      if (existing) {
        existing.push(agent)
      } else {
        deptMap.set(dept, [agent])
      }
    }
    return [...deptMap.entries()].map(([name, deptAgents]): DeptNode => ({
      name,
      agents: deptAgents,
    }))
  }, [agents])

  if (agents.length === 0) return null

  // Layout calculation
  const maxAgentsInDept = Math.max(...departments.map((d) => d.agents.length), 1)
  const deptWidths = departments.map((d) =>
    Math.max(NODE_WIDTH, d.agents.length * (AVATAR_RADIUS * 2 + 8)),
  )
  const totalWidth = deptWidths.reduce((sum, w) => sum + w + H_GAP, 0) - H_GAP
  const svgWidth = Math.max(totalWidth + 40, 200)
  const svgHeight = V_GAP * 2 + NODE_HEIGHT + maxAgentsInDept * (AVATAR_RADIUS * 2 + 4) + 20

  // Positions
  let xOffset = (svgWidth - totalWidth) / 2
  const deptPositions = departments.map((dept, i) => {
    const width = deptWidths[i]!
    const x = xOffset + width / 2
    xOffset += width + H_GAP
    return { x, y: V_GAP, dept }
  })

  const rootX = svgWidth / 2
  const rootY = 16

  return (
    <div className={cn('overflow-x-auto rounded-lg border border-border bg-card p-4', className)}>
      <svg
        viewBox={`0 0 ${svgWidth} ${svgHeight}`}
        width="100%"
        height={Math.min(svgHeight, 200)}
        role="img"
        aria-label="Organization chart"
      >
        {/* Root node (company) */}
        <circle cx={rootX} cy={rootY} r={8} className="fill-accent" />

        {/* Lines from root to departments */}
        {deptPositions.map((pos) => (
          <line
            key={`root-${pos.dept.name}`}
            x1={rootX}
            y1={rootY + 8}
            x2={pos.x}
            y2={pos.y - NODE_HEIGHT / 2}
            className="stroke-border"
            strokeWidth={1}
          />
        ))}

        {/* Department nodes */}
        {deptPositions.map((pos) => (
          <g key={pos.dept.name}>
            {/* Dept label */}
            <rect
              x={pos.x - NODE_WIDTH / 2}
              y={pos.y - NODE_HEIGHT / 2}
              width={NODE_WIDTH}
              height={NODE_HEIGHT}
              rx={6}
              className="fill-surface stroke-border"
              strokeWidth={1}
            />
            <text
              x={pos.x}
              y={pos.y + 4}
              textAnchor="middle"
              className="fill-muted-foreground text-[9px]"
            >
              {pos.dept.name.length > 12 ? pos.dept.name.slice(0, 10) + '..' : pos.dept.name}
            </text>

            {/* Agent nodes */}
            {pos.dept.agents.map((agent, agentIdx) => {
              const agentX = pos.x + (agentIdx - (pos.dept.agents.length - 1) / 2) * (AVATAR_RADIUS * 2 + 8)
              const agentY = pos.y + V_GAP

              return (
                <AgentNode
                  key={`${agent.name}-${agentIdx}`}
                  agent={agent}
                  agentX={agentX}
                  agentY={agentY}
                  deptX={pos.x}
                  deptY={pos.y}
                />
              )
            })}
          </g>
        ))}
      </svg>
    </div>
  )
}
