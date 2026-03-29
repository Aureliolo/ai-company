import { describe, expect, it } from 'vitest'
import fc from 'fast-check'
import { aggregateMessages, type CommunicationLink } from '@/pages/org/aggregate-messages'

const ONE_HOUR_MS = 3_600_000

describe('aggregateMessages', () => {
  it('returns empty array for empty messages', () => {
    expect(aggregateMessages([], ONE_HOUR_MS)).toEqual([])
  })

  it('aggregates a single sender-receiver pair', () => {
    const messages = [{ sender: 'alice', to: 'bob' }]
    const result = aggregateMessages(messages, ONE_HOUR_MS)
    expect(result).toHaveLength(1)
    expect(result[0]).toEqual<CommunicationLink>({
      source: 'alice',
      target: 'bob',
      volume: 1,
      frequency: 1,
    })
  })

  it('combines bidirectional messages into one link', () => {
    const messages = [
      { sender: 'alice', to: 'bob' },
      { sender: 'bob', to: 'alice' },
      { sender: 'alice', to: 'bob' },
    ]
    const result = aggregateMessages(messages, ONE_HOUR_MS)
    expect(result).toHaveLength(1)
    expect(result[0]!.volume).toBe(3)
    expect(result[0]!.frequency).toBe(3)
  })

  it('normalizes pair order (source < target alphabetically)', () => {
    const messages = [{ sender: 'zara', to: 'anna' }]
    const result = aggregateMessages(messages, ONE_HOUR_MS)
    expect(result[0]!.source).toBe('anna')
    expect(result[0]!.target).toBe('zara')
  })

  it('excludes self-messages', () => {
    const messages = [
      { sender: 'alice', to: 'alice' },
      { sender: 'alice', to: 'bob' },
    ]
    const result = aggregateMessages(messages, ONE_HOUR_MS)
    expect(result).toHaveLength(1)
    expect(result[0]!.volume).toBe(1)
  })

  it('computes frequency based on time window', () => {
    const twoHoursMs = 2 * ONE_HOUR_MS
    const messages = [
      { sender: 'alice', to: 'bob' },
      { sender: 'alice', to: 'bob' },
      { sender: 'alice', to: 'bob' },
      { sender: 'alice', to: 'bob' },
    ]
    const result = aggregateMessages(messages, twoHoursMs)
    expect(result[0]!.volume).toBe(4)
    expect(result[0]!.frequency).toBe(2) // 4 messages / 2 hours
  })

  it('produces independent links for multiple pairs', () => {
    const messages = [
      { sender: 'alice', to: 'bob' },
      { sender: 'alice', to: 'carol' },
      { sender: 'bob', to: 'carol' },
    ]
    const result = aggregateMessages(messages, ONE_HOUR_MS)
    expect(result).toHaveLength(3)
    const pairs = result.map((l) => `${l.source}::${l.target}`)
    expect(pairs).toContain('alice::bob')
    expect(pairs).toContain('alice::carol')
    expect(pairs).toContain('bob::carol')
  })

  it('sorts by volume descending', () => {
    const messages = [
      { sender: 'alice', to: 'bob' },
      { sender: 'carol', to: 'dave' },
      { sender: 'carol', to: 'dave' },
      { sender: 'carol', to: 'dave' },
      { sender: 'eve', to: 'frank' },
      { sender: 'eve', to: 'frank' },
    ]
    const result = aggregateMessages(messages, ONE_HOUR_MS)
    expect(result[0]!.volume).toBe(3)
    expect(result[1]!.volume).toBe(2)
    expect(result[2]!.volume).toBe(1)
  })

  it('handles zero time window gracefully (frequency = Infinity)', () => {
    const messages = [{ sender: 'alice', to: 'bob' }]
    const result = aggregateMessages(messages, 0)
    expect(result[0]!.frequency).toBe(Infinity)
  })

  describe('properties', () => {
    const agentArb = fc.constantFrom('a', 'b', 'c', 'd')
    const messageArb = fc.record({ sender: agentArb, to: agentArb })

    it('volume is always a positive integer', () => {
      fc.assert(
        fc.property(
          fc.array(messageArb, { minLength: 1, maxLength: 50 }),
          (messages) => {
            const result = aggregateMessages(messages, ONE_HOUR_MS)
            for (const link of result) {
              expect(link.volume).toBeGreaterThan(0)
              expect(Number.isInteger(link.volume)).toBe(true)
            }
          },
        ),
      )
    })

    it('no self-links in output', () => {
      fc.assert(
        fc.property(
          fc.array(messageArb, { minLength: 1, maxLength: 50 }),
          (messages) => {
            const result = aggregateMessages(messages, ONE_HOUR_MS)
            for (const link of result) {
              expect(link.source).not.toBe(link.target)
            }
          },
        ),
      )
    })
  })
})
