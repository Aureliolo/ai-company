import { describe, expect, it } from 'vitest'
import { mapHrToRuntime, resolveRuntimeStatus } from '@/pages/org/status-mapping'

describe('mapHrToRuntime', () => {
  it('maps terminated to offline', () => {
    expect(mapHrToRuntime('terminated')).toBe('offline')
  })

  it('maps on_leave to offline', () => {
    expect(mapHrToRuntime('on_leave')).toBe('offline')
  })

  it('maps onboarding to idle', () => {
    expect(mapHrToRuntime('onboarding')).toBe('idle')
  })

  it('maps active to idle as default', () => {
    expect(mapHrToRuntime('active')).toBe('idle')
  })
})

describe('resolveRuntimeStatus', () => {
  it('returns HR-derived default when no runtime override exists', () => {
    expect(resolveRuntimeStatus('agent-1', 'active', {})).toBe('idle')
  })

  it('returns runtime override when present', () => {
    expect(resolveRuntimeStatus('agent-1', 'active', { 'agent-1': 'active' })).toBe('active')
  })

  it('returns runtime error override even for active HR status', () => {
    expect(resolveRuntimeStatus('agent-1', 'active', { 'agent-1': 'error' })).toBe('error')
  })

  it('ignores runtime overrides for other agents', () => {
    expect(resolveRuntimeStatus('agent-1', 'on_leave', { 'agent-2': 'active' })).toBe('offline')
  })

  it('runtime override takes precedence over terminated HR status', () => {
    // Edge case: agent marked terminated in HR but WS says active (stale data)
    expect(resolveRuntimeStatus('agent-1', 'terminated', { 'agent-1': 'active' })).toBe('active')
  })
})
