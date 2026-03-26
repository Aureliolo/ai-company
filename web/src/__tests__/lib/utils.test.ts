import { cn, getStatusColor, getHealthColor } from '@/lib/utils'

describe('cn', () => {
  it('merges class names', () => {
    expect(cn('foo', 'bar')).toBe('foo bar')
  })

  it('resolves Tailwind conflicts (last wins)', () => {
    expect(cn('px-2', 'px-4')).toBe('px-4')
  })

  it('handles conditional and falsy values', () => {
    const isHidden = false
    expect(cn('base', isHidden && 'hidden', undefined, null, 'end')).toBe('base end')
  })
})

describe('getStatusColor', () => {
  it('maps active to success', () => {
    expect(getStatusColor('active')).toBe('success')
  })

  it('maps idle to accent', () => {
    expect(getStatusColor('idle')).toBe('accent')
  })

  it('maps error to danger', () => {
    expect(getStatusColor('error')).toBe('danger')
  })

  it('maps offline to text-secondary', () => {
    expect(getStatusColor('offline')).toBe('text-secondary')
  })
})

describe('getHealthColor', () => {
  it('returns success for percentage >= 75', () => {
    expect(getHealthColor(75)).toBe('success')
    expect(getHealthColor(100)).toBe('success')
  })

  it('returns accent for percentage >= 50 and < 75', () => {
    expect(getHealthColor(50)).toBe('accent')
    expect(getHealthColor(74)).toBe('accent')
  })

  it('returns warning for percentage >= 25 and < 50', () => {
    expect(getHealthColor(25)).toBe('warning')
    expect(getHealthColor(49)).toBe('warning')
  })

  it('returns danger for percentage < 25', () => {
    expect(getHealthColor(24)).toBe('danger')
    expect(getHealthColor(0)).toBe('danger')
  })
})
