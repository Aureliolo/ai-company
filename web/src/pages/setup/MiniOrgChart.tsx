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

/** Minimum height for small teams. */
const MIN_HEIGHT = 140
/** Maximum height cap for very large teams. */
const MAX_HEIGHT = 500

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
  radius: number
}

function AgentNode({ agent, agentX, agentY, deptX, deptY, radius }: AgentNodeProps) {
  return (
    <g>
      {/* Line from dept to agent */}
      <line
        x1={deptX}
        y1={deptY + 18}
        x2={agentX}
        y2={agentY - radius}
        className="stroke-border"
        strokeWidth={1}
      />
      {/* Agent circle */}
      <circle
        cx={agentX}
        cy={agentY}
        r={radius}
        className="fill-card stroke-accent/40"
        strokeWidth={1}
      >
        <title>{`${agent.name} - ${agent.role}`}</title>
      </circle>
      <text
        x={agentX}
        y={agentY + 3}
        textAnchor="middle"
        className="fill-foreground font-medium"
        fontSize={radius > 14 ? 10 : 8}
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

  // Scale node sizes based on team size
  const isSmallTeam = agents.length <= 5
  const avatarRadius = isSmallTeam ? 16 : 14
  const nodeWidth = isSmallTeam ? 110 : 90
  const nodeHeight = 36
  const hGap = isSmallTeam ? 40 : 28
  const vGap = isSmallTeam ? 60 : 50

  // Layout calculation
  const maxAgentsInDept = Math.max(...departments.map((d) => d.agents.length), 1)
  const deptWidths = departments.map((d) =>
    Math.max(nodeWidth, d.agents.length * (avatarRadius * 2 + 10)),
  )
  const totalWidth = deptWidths.reduce((sum, w) => sum + w + hGap, 0) - hGap
  const svgWidth = Math.max(totalWidth + 40, 300)
  const svgHeight = vGap * 2 + nodeHeight + maxAgentsInDept * (avatarRadius * 2 + 6) + 24

  // Dynamic height: scale with team, capped at bounds
  const displayHeight = Math.min(Math.max(svgHeight, MIN_HEIGHT), MAX_HEIGHT)

  // Positions
  let xOffset = (svgWidth - totalWidth) / 2
  const deptPositions = departments.map((dept, i) => {
    const width = deptWidths[i]!
    const x = xOffset + width / 2
    xOffset += width + hGap
    return { x, y: vGap, dept }
  })

  const rootX = svgWidth / 2
  const rootY = 16

  return (
    <div className={cn('overflow-x-auto rounded-lg border border-border bg-card p-4', className)}>
      <svg
        viewBox={`0 0 ${svgWidth} ${svgHeight}`}
        width="100%"
        height={displayHeight}
        role="img"
        aria-label="Organization chart"
      >
        {/* Root node (company) */}
        <circle cx={rootX} cy={rootY} r={10} className="fill-accent" />

        {/* Lines from root to departments */}
        {deptPositions.map((pos) => (
          <line
            key={`root-${pos.dept.name}`}
            x1={rootX}
            y1={rootY + 10}
            x2={pos.x}
            y2={pos.y - nodeHeight / 2}
            className="stroke-border"
            strokeWidth={1}
          />
        ))}

        {/* Department nodes */}
        {deptPositions.map((pos) => (
          <g key={pos.dept.name}>
            {/* Dept label */}
            <rect
              x={pos.x - nodeWidth / 2}
              y={pos.y - nodeHeight / 2}
              width={nodeWidth}
              height={nodeHeight}
              rx={6}
              className="fill-surface stroke-border"
              strokeWidth={1}
            />
            <text
              x={pos.x}
              y={pos.y + 4}
              textAnchor="middle"
              className="fill-muted-foreground"
              fontSize={isSmallTeam ? 11 : 9}
            >
              {pos.dept.name.length > 14 ? pos.dept.name.slice(0, 12) + '..' : pos.dept.name}
            </text>

            {/* Agent nodes */}
            {pos.dept.agents.map((agent, agentIdx) => {
              const agentX = pos.x + (agentIdx - (pos.dept.agents.length - 1) / 2) * (avatarRadius * 2 + 10)
              const agentY = pos.y + vGap

              return (
                <AgentNode
                  // eslint-disable-next-line @eslint-react/no-array-index-key -- setup agents can share names; index as tiebreaker
                  key={`${agent.name}-${agentIdx}`}
                  agent={agent}
                  agentX={agentX}
                  agentY={agentY}
                  deptX={pos.x}
                  deptY={pos.y}
                  radius={avatarRadius}
                />
              )
            })}
          </g>
        ))}
      </svg>
    </div>
  )
}
