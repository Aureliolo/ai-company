import { cn } from '@/lib/utils'

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
