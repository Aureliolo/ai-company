import { useParams, Link } from "react-router-dom"
import { motion } from "framer-motion"
import { useTheme } from "@/themes/provider.tsx"
import { SectionCard } from "@/components/section-card.tsx"
import { StatusDot } from "@/components/status-dot.tsx"
import { AgentAvatar } from "@/components/agent-avatar.tsx"
import { PerfMetric } from "@/components/perf-metric.tsx"
import { ToolBadge } from "@/components/tool-badge.tsx"
import { CareerEvent } from "@/components/career-event.tsx"
import { TaskBar } from "@/components/task-bar.tsx"
import { IdentityRow } from "@/components/identity-row.tsx"
import { ActivityStream } from "@/components/activity-stream.tsx"
import { getAgent, agents } from "@/data/index.ts"
import type { Agent } from "@/data/types.ts"

function AutonomyBadge({ level }: { level: string }) {
  return (
    <span className="text-[11px] font-mono text-warning bg-warning/[0.08] border border-warning/20 px-1.5 py-0.5 rounded">
      {level}
    </span>
  )
}

function AgentNotFound() {
  const firstAgent = agents[0]
  return (
    <div className="p-6 flex flex-col items-center justify-center gap-4 min-h-[50vh]">
      <p className="text-text-secondary text-sm">Agent not found</p>
      <Link
        to={`agent/${firstAgent?.id ?? "ceo"}`}
        className="text-accent text-sm hover:underline"
      >
        View {firstAgent?.name ?? "CEO"}
      </Link>
    </div>
  )
}

function AgentProfileContent({ agent }: { agent: Agent }) {
  const theme = useTheme()
  const { density, animation } = theme
  const maxEnd = Math.max(...agent.taskHistory.map((t) => t.start + t.duration))

  const feedEvents = agent.recentActivity.map((a, i) => ({
    id: i,
    time: a.time,
    minutesAgo: 0,
    agent: agent.shortName,
    agentFull: agent.name,
    action: a.description,
    task: "",
    to: null,
    toFull: null,
    type: a.type,
  }))

  return (
    <motion.div
      className={`${density.cardPadding} flex flex-col ${density.sectionGap}`}
      initial="hidden"
      animate="visible"
      variants={{
        visible: {
          transition: { staggerChildren: animation.staggerChildren },
        },
      }}
    >
      {/* Page header */}
      <div>
        <div className="flex items-center gap-2.5 mb-0.5">
          <h1 className="text-lg font-semibold text-text-primary tracking-tight">
            {agent.shortName}
          </h1>
          <span className="text-[11px] text-text-muted font-mono bg-white/5 border border-border px-2 py-0.5 rounded">
            {agent.role}
          </span>
          <StatusDot status={agent.status} />
          <span className="text-[11px] text-accent font-mono capitalize">
            {agent.status}
          </span>
        </div>
        <p className="text-xs text-text-muted font-mono">
          {agent.name} -- {agent.department} -- {agent.autonomyLevel}
        </p>
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-[2fr_3fr] gap-5 items-start">
        {/* LEFT COLUMN */}
        <div className={`flex flex-col ${density.sectionGap}`}>
          {/* Identity card */}
          <SectionCard title="Identity">
            <div className="flex items-center gap-3.5 mb-4">
              <AgentAvatar name={agent.name} size={56} />
              <div>
                <div className="text-base font-bold text-text-primary mb-0.5">
                  {agent.name}
                </div>
                <div className="text-xs text-text-secondary mb-0.5">
                  {agent.role}
                </div>
                <div className="text-[11px] text-text-muted">
                  {agent.department} -- {agent.level}
                </div>
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <IdentityRow
                label="Status"
                value={
                  <span className="inline-flex items-center gap-1.5 text-[11px] text-accent font-mono">
                    <StatusDot status={agent.status} size={6} />
                    <span className="capitalize">{agent.status}</span>
                  </span>
                }
              />
              <IdentityRow
                label="Autonomy"
                value={<AutonomyBadge level={agent.autonomyLevel} />}
              />
              <IdentityRow label="Department" value={agent.department} />
              <IdentityRow label="Level" value={agent.level} />
            </div>
          </SectionCard>

          {/* Performance */}
          <SectionCard title="Performance">
            <div className="grid grid-cols-2 gap-2.5">
              <PerfMetric
                label="Tasks Completed"
                value={String(agent.performance.tasksCompleted)}
                color="accent"
              />
              <PerfMetric
                label="Avg Time"
                value={String(agent.performance.avgCompletionTime)}
                unit="h"
                color="accent"
              />
              <PerfMetric
                label="Success Rate"
                value={String(agent.performance.successRate)}
                unit="%"
                color="success"
              />
              <PerfMetric
                label="Cost / Task"
                value={`$${agent.performance.costEfficiency}`}
                color="warning"
              />
            </div>
          </SectionCard>

          {/* Tools */}
          <SectionCard title="Available Tools">
            <div className="flex flex-wrap gap-1.5">
              {agent.tools.map((tool) => (
                <ToolBadge key={tool} name={tool} />
              ))}
            </div>
          </SectionCard>

          {/* Career Timeline */}
          <SectionCard title="Career Timeline">
            <div className="flex flex-col">
              {agent.careerTimeline.map((event, i) => (
                <CareerEvent
                  key={i}
                  event={event}
                  isLast={i === agent.careerTimeline.length - 1}
                />
              ))}
            </div>
          </SectionCard>
        </div>

        {/* RIGHT COLUMN */}
        <div className={`flex flex-col ${density.sectionGap}`}>
          {/* Task Timeline */}
          <SectionCard title="Task Timeline">
            <div className="flex flex-col gap-1.5">
              {agent.taskHistory.map((task) => (
                <TaskBar key={task.id} task={task} maxEnd={maxEnd} />
              ))}
            </div>
            {/* Time axis */}
            <div className="flex justify-between mt-2 pl-24 pr-6 text-[9px] font-mono text-text-muted">
              {Array.from({ length: 6 }, (_, i) => (
                <span key={i}>{((maxEnd / 5) * i).toFixed(0)}h</span>
              ))}
            </div>
          </SectionCard>

          {/* Recent Activity */}
          <SectionCard title="Recent Activity">
            <ActivityStream events={feedEvents} compact />
          </SectionCard>
        </div>
      </div>
    </motion.div>
  )
}

export function AgentProfile() {
  const { agentId } = useParams()
  const agent = getAgent(agentId ?? "")

  if (!agent) return <AgentNotFound />
  return <AgentProfileContent agent={agent} />
}
