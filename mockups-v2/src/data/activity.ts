import type { FeedEvent } from "@/data/types"
import { agents } from "@/data/agents"
import { createRng, pick } from "@/data/seed"

// ---------------------------------------------------------------------------
// Action templates per event type
// ---------------------------------------------------------------------------

const ACTION_MAP: Record<FeedEvent["type"], string[]> = {
  complete: ["completed", "finished", "wrapped up"],
  approve: ["approved", "signed off on", "greenlit"],
  delegate: ["delegated", "reassigned", "handed off"],
  start: ["started", "began working on", "picked up"],
  submit: ["submitted", "sent for review", "turned in"],
  flag: ["flagged an issue in", "raised concern about", "escalated"],
  receive: ["received", "was assigned", "picked up"],
  tool: ["invoked tool for", "ran diagnostics on", "executed tool for"],
}

const EVENT_TYPES: FeedEvent["type"][] = [
  "complete",
  "approve",
  "delegate",
  "start",
  "submit",
  "flag",
  "receive",
  "tool",
]

// Weights: complete and start are most common
const EVENT_WEIGHTS = [25, 10, 8, 25, 12, 5, 10, 5]

// ---------------------------------------------------------------------------
// Time formatting
// ---------------------------------------------------------------------------

function formatMinutesAgo(minutes: number): string {
  if (minutes < 1) return "just now"
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

// ---------------------------------------------------------------------------
// Generate feed
// ---------------------------------------------------------------------------

function buildActivityFeed(): FeedEvent[] {
  const rng = createRng(1337)
  const events: FeedEvent[] = []
  const totalEvents = 220

  // Non-CEO agents for delegation targets
  const delegatableAgents = agents.filter((a) => a.level !== "C-Suite")

  for (let i = 0; i < totalEvents; i++) {
    // Time distribution: exponential -- more events in recent hours
    // Use inverse transform: -ln(U) * scale
    // Scale so most events are within 24h (1440 minutes)
    const u = Math.max(rng(), 0.001) // avoid log(0)
    const minutesAgo = Math.min(
      Math.floor(-Math.log(u) * 180),
      1440,
    )

    // Pick event type with weights
    const totalWeight = EVENT_WEIGHTS.reduce((a, b) => a + b, 0)
    let r = rng() * totalWeight
    let eventType = EVENT_TYPES[0]
    for (let j = 0; j < EVENT_TYPES.length; j++) {
      r -= EVENT_WEIGHTS[j]
      if (r <= 0) {
        eventType = EVENT_TYPES[j]
        break
      }
    }

    const agent = pick(rng, agents)
    const action = pick(rng, ACTION_MAP[eventType])

    // Task: pick from agent's department task names or their own task history
    const task =
      agent.taskHistory.length > 0
        ? pick(rng, agent.taskHistory).name
        : "General task"

    // Delegation target (only for delegate type)
    let to: string | null = null
    let toFull: string | null = null
    if (eventType === "delegate" && delegatableAgents.length > 0) {
      const target = pick(rng, delegatableAgents)
      to = target.shortName
      toFull = target.name
    }

    events.push({
      id: i + 1,
      time: formatMinutesAgo(minutesAgo),
      minutesAgo,
      agent: agent.shortName,
      agentFull: agent.name,
      action,
      task,
      to,
      toFull,
      type: eventType,
    })
  }

  // Sort by time, most recent first
  events.sort((a, b) => a.minutesAgo - b.minutesAgo)

  // Reassign IDs after sorting
  events.forEach((e, idx) => {
    e.id = idx + 1
  })

  return events
}

export const activityFeed: FeedEvent[] = buildActivityFeed()
