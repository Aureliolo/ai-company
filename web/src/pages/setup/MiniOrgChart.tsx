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

/** Layout constants. */
const SMALL_TEAM_THRESHOLD = 5
const LARGE_AVATAR_RADIUS = 16
const SMALL_AVATAR_RADIUS = 14
const LARGE_NODE_WIDTH = 110
const SMALL_NODE_WIDTH = 90
const AGENT_SPACING_GAP = 10

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

interface DepartmentGroupProps {
  pos: { x: number; y: number; dept: DeptNode }
  nodeWidth: number
  nodeHeight: number
  avatarRadius: number
  vGap: number
  isSmallTeam: boolean
}

function DepartmentGroup({ pos, nodeWidth, nodeHeight, avatarRadius, vGap, isSmallTeam }: DepartmentGroupProps) {
  return (
    <g>
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
        const agentSpacing = avatarRadius * 2 + AGENT_SPACING_GAP
        const centerOffset = agentIdx - (pos.dept.agents.length - 1) / 2
        const agentX = pos.x + centerOffset * agentSpacing
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
  const isSmallTeam = agents.length <= SMALL_TEAM_THRESHOLD
  const avatarRadius = isSmallTeam
    ? LARGE_AVATAR_RADIUS : SMALL_AVATAR_RADIUS
  const nodeWidth = isSmallTeam
    ? LARGE_NODE_WIDTH : SMALL_NODE_WIDTH
  const nodeHeight = 36
  const hGap = isSmallTeam ? 40 : 28
  const vGap = isSmallTeam ? 60 : 50

  // Layout calculation
  const maxAgentsInDept = Math.max(...departments.map((d) => d.agents.length), 1)
  const deptWidths = departments.map((d) =>
    Math.max(nodeWidth, d.agents.length * (avatarRadius * 2 + AGENT_SPACING_GAP)),
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
          <DepartmentGroup
            key={pos.dept.name}
            pos={pos}
            nodeWidth={nodeWidth}
            nodeHeight={nodeHeight}
            avatarRadius={avatarRadius}
            vGap={vGap}
            isSmallTeam={isSmallTeam}
          />
        ))}
      </svg>
    </div>
  )
}
