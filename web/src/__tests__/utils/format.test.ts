import {
  formatDate,
  formatRelativeTime,
  formatCurrency,
  formatNumber,
  formatUptime,
  formatLabel,
} from '@/utils/format'

describe('formatDate', () => {
  it('returns -- for null/undefined', () => {
    expect(formatDate(null)).toBe('--')
    expect(formatDate(undefined)).toBe('--')
  })

  it('returns -- for empty string', () => {
    expect(formatDate('')).toBe('--')
  })

  it('returns -- for invalid date', () => {
    expect(formatDate('not-a-date')).toBe('--')
  })

  it('formats valid ISO date', () => {
    const result = formatDate('2025-01-15T10:30:00Z')
    expect(result).toContain('Jan')
    expect(result).toContain('15')
    expect(result).toContain('2025')
  })
})

describe('formatRelativeTime', () => {
  it('returns -- for null/undefined', () => {
    expect(formatRelativeTime(null)).toBe('--')
    expect(formatRelativeTime(undefined)).toBe('--')
  })

  it('returns -- for invalid date', () => {
    expect(formatRelativeTime('not-a-date')).toBe('--')
  })

  it('returns "just now" for recent timestamps', () => {
    const now = new Date().toISOString()
    expect(formatRelativeTime(now)).toBe('just now')
  })

  it('returns minutes ago for recent timestamps', () => {
    const fiveMinAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString()
    expect(formatRelativeTime(fiveMinAgo)).toBe('5m ago')
  })

  it('returns hours ago', () => {
    const threeHoursAgo = new Date(Date.now() - 3 * 3600 * 1000).toISOString()
    expect(formatRelativeTime(threeHoursAgo)).toBe('3h ago')
  })

  it('returns days ago', () => {
    const twoDaysAgo = new Date(Date.now() - 2 * 86400 * 1000).toISOString()
    expect(formatRelativeTime(twoDaysAgo)).toBe('2d ago')
  })

  it('falls back to formatDate for old dates', () => {
    const twoWeeksAgo = new Date(Date.now() - 14 * 86400 * 1000).toISOString()
    const result = formatRelativeTime(twoWeeksAgo)
    expect(result).not.toContain('ago')
    expect(result).not.toBe('--')
  })

  it('falls back to formatDate for future dates', () => {
    const future = new Date(Date.now() + 86400 * 1000).toISOString()
    const result = formatRelativeTime(future)
    expect(result).not.toContain('ago')
    expect(result).not.toBe('--')
  })
})

describe('formatCurrency', () => {
  it('formats positive values', () => {
    expect(formatCurrency(42.5)).toBe('$42.50')
  })

  it('formats zero', () => {
    expect(formatCurrency(0)).toBe('$0.00')
  })

  it('formats small fractional values', () => {
    const result = formatCurrency(0.0001)
    expect(result).toContain('$')
    expect(result).toContain('0.0001')
  })

  it('formats negative values', () => {
    const result = formatCurrency(-10)
    expect(result).toContain('10')
    // Verify negative indicator (varies by locale: "-$10.00" or "($10.00)")
    expect(result.includes('-') || result.includes('(')).toBe(true)
  })
})

describe('formatNumber', () => {
  it('formats with separators', () => {
    expect(formatNumber(1000000)).toBe('1,000,000')
  })

  it('formats zero', () => {
    expect(formatNumber(0)).toBe('0')
  })
})

describe('formatUptime', () => {
  it('formats zero seconds', () => {
    expect(formatUptime(0)).toBe('0m')
  })

  it('formats minutes', () => {
    expect(formatUptime(300)).toBe('5m')
  })

  it('formats hours and minutes', () => {
    expect(formatUptime(3660)).toBe('1h 1m')
  })

  it('formats days, hours, and minutes', () => {
    expect(formatUptime(90061)).toBe('1d 1h 1m')
  })

  it('handles negative values', () => {
    expect(formatUptime(-100)).toBe('0m')
  })

  it('handles Infinity', () => {
    expect(formatUptime(Infinity)).toBe('0m')
  })

  it('handles NaN', () => {
    expect(formatUptime(NaN)).toBe('0m')
  })
})

describe('formatLabel', () => {
  it('capitalizes snake_case', () => {
    expect(formatLabel('in_progress')).toBe('In Progress')
  })

  it('capitalizes single word', () => {
    expect(formatLabel('active')).toBe('Active')
  })

  it('handles empty string', () => {
    expect(formatLabel('')).toBe('')
  })
})
