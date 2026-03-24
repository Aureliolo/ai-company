import { renderHook, act } from '@testing-library/react'
import { useOptimisticUpdate } from '@/hooks/useOptimisticUpdate'

describe('useOptimisticUpdate', () => {
  it('returns initial state', () => {
    const { result } = renderHook(() => useOptimisticUpdate())
    expect(result.current.pending).toBe(false)
    expect(result.current.error).toBeNull()
  })

  it('executes successfully and returns result', async () => {
    const { result } = renderHook(() => useOptimisticUpdate())

    const rollback = vi.fn()
    const applyOptimistic = vi.fn(() => rollback)
    const serverAction = vi.fn().mockResolvedValue({ id: 'test-1' })

    let outcome: unknown
    await act(async () => {
      outcome = await result.current.execute(applyOptimistic, serverAction)
    })

    expect(outcome).toEqual({ id: 'test-1' })
    expect(result.current.pending).toBe(false)
    expect(result.current.error).toBeNull()
    expect(rollback).not.toHaveBeenCalled()
  })

  it('rolls back and sets error on server failure', async () => {
    const { result } = renderHook(() => useOptimisticUpdate())

    const rollback = vi.fn()
    const applyOptimistic = vi.fn(() => rollback)
    const serverAction = vi.fn().mockRejectedValue(new Error('Server error'))

    let outcome: unknown
    await act(async () => {
      outcome = await result.current.execute(applyOptimistic, serverAction)
    })

    expect(outcome).toBeNull()
    expect(result.current.pending).toBe(false)
    expect(result.current.error).toBe('Server error')
    expect(rollback).toHaveBeenCalledOnce()
  })

  it('handles prepare failure without calling server', async () => {
    const { result } = renderHook(() => useOptimisticUpdate())

    const applyOptimistic = vi.fn(() => { throw new Error('Prepare failed') })
    const serverAction = vi.fn()

    let outcome: unknown
    await act(async () => {
      outcome = await result.current.execute(applyOptimistic, serverAction)
    })

    expect(outcome).toBeNull()
    expect(result.current.error).toBe('Prepare failed')
    expect(serverAction).not.toHaveBeenCalled()
  })

  it('blocks concurrent execution', async () => {
    const { result } = renderHook(() => useOptimisticUpdate())

    let resolveServer: (value: string) => void
    const serverPromise = new Promise<string>((r) => { resolveServer = r })
    const applyOptimistic = vi.fn(() => vi.fn())
    const serverAction = vi.fn().mockReturnValue(serverPromise)

    // Start first call
    let p1Result: unknown
    let p2Result: unknown
    await act(async () => {
      const p1 = result.current.execute(applyOptimistic, serverAction)
      // Second call while first is pending should return null
      p2Result = await result.current.execute(applyOptimistic, serverAction)
      resolveServer!('done')
      p1Result = await p1
    })

    expect(p1Result).toBe('done')
    expect(p2Result).toBeNull()
    expect(serverAction).toHaveBeenCalledOnce()
  })

  it('appends warning when rollback fails', async () => {
    const { result } = renderHook(() => useOptimisticUpdate())

    const rollback = vi.fn(() => { throw new Error('Rollback boom') })
    const applyOptimistic = vi.fn(() => rollback)
    const serverAction = vi.fn().mockRejectedValue(new Error('Server error'))

    await act(async () => {
      await result.current.execute(applyOptimistic, serverAction)
    })

    expect(result.current.error).toContain('Server error')
    expect(result.current.error).toContain('UI may be out of sync')
  })
})
