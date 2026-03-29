/**
 * Aggregate inter-agent messages into communication links for the force-directed graph.
 *
 * Bidirectional messages (A->B and B->A) are combined into a single link.
 * Self-messages are excluded. Links are sorted by volume descending.
 */

export interface CommunicationLink {
  /** Agent identifier (alphabetically first of the pair). */
  source: string
  /** Agent identifier (alphabetically second of the pair). */
  target: string
  /** Total message count in both directions. */
  volume: number
  /** Messages per hour over the given time window. */
  frequency: number
}

/**
 * Aggregate raw messages into communication links.
 *
 * @param messages - Messages with at least `sender` and `to` fields.
 * @param timeWindowMs - Time window in milliseconds over which frequency is computed.
 * @returns Deduplicated, bidirectional communication links sorted by volume descending.
 */
export function aggregateMessages(
  messages: readonly { sender: string; to: string }[],
  timeWindowMs: number,
): CommunicationLink[] {
  const volumeMap = new Map<string, { source: string; target: string; volume: number }>()

  for (const msg of messages) {
    if (msg.sender === msg.to) continue

    // Normalize pair key so A::B and B::A map to the same entry
    const [source, target] =
      msg.sender < msg.to ? [msg.sender, msg.to] : [msg.to, msg.sender]
    const key = `${source}::${target}`

    const entry = volumeMap.get(key)
    if (entry) {
      entry.volume += 1
    } else {
      volumeMap.set(key, { source, target, volume: 1 })
    }
  }

  const MS_PER_HOUR = 3_600_000
  const timeWindowHours = timeWindowMs / MS_PER_HOUR

  return [...volumeMap.values()]
    .map(({ source, target, volume }) => ({
      source,
      target,
      volume,
      frequency: volume / timeWindowHours,
    }))
    .sort((a, b) => b.volume - a.volume)
}
