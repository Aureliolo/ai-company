import { computeLineDiff } from '@/pages/settings/editor-diff'

describe('computeLineDiff', () => {
  it('returns empty array for identical texts', () => {
    const text = 'line1\nline2\nline3'
    expect(computeLineDiff(text, text)).toEqual([])
  })

  it('detects added lines', () => {
    const server = 'a\nb'
    const edited = 'a\nx\nb'
    const diffs = computeLineDiff(server, edited)
    expect(diffs).toEqual([{ line: 2, kind: 'added' }])
  })

  it('detects removed lines', () => {
    const server = 'a\nb\nc'
    const edited = 'a\nc'
    const diffs = computeLineDiff(server, edited)
    expect(diffs).toEqual([{ line: 2, kind: 'removed' }])
  })

  it('detects mixed additions and removals', () => {
    const server = 'a\nb\nc'
    const edited = 'a\nx\nc'
    const diffs = computeLineDiff(server, edited)
    expect(diffs).toHaveLength(2)
    expect(diffs).toContainEqual({ line: 2, kind: 'added' })
    expect(diffs).toContainEqual({ line: 2, kind: 'removed' })
  })

  it('handles empty server text', () => {
    const diffs = computeLineDiff('', 'new line')
    expect(diffs.length).toBeGreaterThan(0)
    expect(diffs.some((d) => d.kind === 'added')).toBe(true)
  })

  it('handles empty edited text', () => {
    const diffs = computeLineDiff('old line', '')
    expect(diffs.length).toBeGreaterThan(0)
    expect(diffs.some((d) => d.kind === 'removed')).toBe(true)
  })

  it('handles both empty', () => {
    expect(computeLineDiff('', '')).toEqual([])
  })

  it('returns diffs sorted by line number', () => {
    const server = 'a\nb\nc\nd'
    const edited = 'x\nb\ny\nd'
    const diffs = computeLineDiff(server, edited)
    for (let i = 1; i < diffs.length; i++) {
      expect(diffs[i]!.line).toBeGreaterThanOrEqual(diffs[i - 1]!.line)
    }
  })

  it('handles insertion at end', () => {
    const server = 'a\nb'
    const edited = 'a\nb\nc'
    const diffs = computeLineDiff(server, edited)
    expect(diffs).toEqual([{ line: 3, kind: 'added' }])
  })

  it('handles insertion at beginning', () => {
    const server = 'a\nb'
    const edited = 'x\na\nb'
    const diffs = computeLineDiff(server, edited)
    expect(diffs).toEqual([{ line: 1, kind: 'added' }])
  })
})
