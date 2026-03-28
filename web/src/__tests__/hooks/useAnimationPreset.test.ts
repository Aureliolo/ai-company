import { renderHook } from '@testing-library/react'
import fc from 'fast-check'
import { describe, it, expect, beforeEach } from 'vitest'
import { useAnimationPreset } from '@/hooks/useAnimationPreset'
import { useThemeStore } from '@/stores/theme'
import type { AnimationPreset } from '@/stores/theme'

describe('useAnimationPreset', () => {
  beforeEach(() => {
    useThemeStore.getState().reset()
  })

  const presets: AnimationPreset[] = ['minimal', 'spring', 'instant', 'status-driven', 'aggressive']

  it.each(presets)('returns a valid config for "%s" preset', (preset) => {
    useThemeStore.getState().setAnimation(preset)
    const { result } = renderHook(() => useAnimationPreset())

    expect(result.current).toHaveProperty('spring')
    expect(result.current).toHaveProperty('tween')
    expect(result.current).toHaveProperty('staggerDelay')
    expect(result.current).toHaveProperty('enableLayout')
    expect(typeof result.current.staggerDelay).toBe('number')
    expect(typeof result.current.enableLayout).toBe('boolean')
  })

  it('returns a valid config for any random preset (fast-check)', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...presets),
        (preset) => {
          useThemeStore.getState().setAnimation(preset)
          const { result } = renderHook(() => useAnimationPreset())
          expect(result.current).toHaveProperty('spring')
          expect(result.current).toHaveProperty('tween')
          expect(typeof result.current.staggerDelay).toBe('number')
          expect(typeof result.current.enableLayout).toBe('boolean')
        },
      ),
    )
  })

  it('returns enableLayout=false for minimal', () => {
    useThemeStore.getState().setAnimation('minimal')
    const { result } = renderHook(() => useAnimationPreset())
    expect(result.current.enableLayout).toBe(false)
  })

  it('returns enableLayout=false for instant', () => {
    useThemeStore.getState().setAnimation('instant')
    const { result } = renderHook(() => useAnimationPreset())
    expect(result.current.enableLayout).toBe(false)
  })

  it('returns enableLayout=true for spring', () => {
    useThemeStore.getState().setAnimation('spring')
    const { result } = renderHook(() => useAnimationPreset())
    expect(result.current.enableLayout).toBe(true)
  })

  it('returns staggerDelay=0 for minimal', () => {
    useThemeStore.getState().setAnimation('minimal')
    const { result } = renderHook(() => useAnimationPreset())
    expect(result.current.staggerDelay).toBe(0)
  })

  it('returns staggerDelay=0 for instant', () => {
    useThemeStore.getState().setAnimation('instant')
    const { result } = renderHook(() => useAnimationPreset())
    expect(result.current.staggerDelay).toBe(0)
  })

  it('returns staggerDelay>0 for aggressive', () => {
    useThemeStore.getState().setAnimation('aggressive')
    const { result } = renderHook(() => useAnimationPreset())
    expect(result.current.staggerDelay).toBeGreaterThan(0)
  })
})
