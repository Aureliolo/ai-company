import { act, fireEvent, render, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { createMemoryRouter, RouterProvider, useNavigate } from 'react-router'
import { useUnsavedChangesGuard } from '@/hooks/use-unsaved-changes-guard'

const DRAFT_KEY = 'test-draft-guard'

function hookWrapper({ children }: { children: ReactNode }) {
  const router = createMemoryRouter(
    [
      { path: '/a', element: <>{children}</> },
      { path: '/b', element: <div>Page B</div> },
    ],
    { initialEntries: ['/a'] },
  )
  return <RouterProvider router={router} />
}

function ConfirmHarnessPage() {
  const guard = useUnsavedChangesGuard({ when: true })
  const navigate = useNavigate()
  return (
    <div>
      <button type="button" onClick={() => navigate('/b')} aria-label="go-b">go</button>
      <span data-testid="confirm">{String(guard.confirmOpen)}</span>
      <button type="button" aria-label="cancel" onClick={guard.cancel}>cancel</button>
      <button type="button" aria-label="proceed" onClick={guard.proceed}>proceed</button>
    </div>
  )
}

function ProceedDraftHarnessPage() {
  const guard = useUnsavedChangesGuard({ when: true, draftKey: DRAFT_KEY })
  const navigate = useNavigate()
  return (
    <div>
      <button type="button" onClick={() => navigate('/b')} aria-label="go-b">go</button>
      <button type="button" aria-label="proceed" onClick={guard.proceed}>proceed</button>
      <span data-testid="has-draft">{String(guard.hasDraft)}</span>
    </div>
  )
}

afterEach(() => {
  window.localStorage.removeItem(DRAFT_KEY)
})

describe('useUnsavedChangesGuard', () => {
  it('confirmOpen is false when not dirty', () => {
    const { result } = renderHook(
      () => useUnsavedChangesGuard({ when: false }),
      { wrapper: hookWrapper },
    )
    expect(result.current.confirmOpen).toBe(false)
  })

  it('hasDraft reads localStorage on mount', () => {
    window.localStorage.setItem(DRAFT_KEY, JSON.stringify({ foo: 'bar' }))
    const { result } = renderHook(
      () => useUnsavedChangesGuard({ when: false, draftKey: DRAFT_KEY }),
      { wrapper: hookWrapper },
    )
    expect(result.current.hasDraft).toBe(true)
    expect(result.current.restoreDraft()).toEqual({ foo: 'bar' })
  })

  it('hasDraft false when localStorage is empty', () => {
    const { result } = renderHook(
      () => useUnsavedChangesGuard({ when: false, draftKey: DRAFT_KEY }),
      { wrapper: hookWrapper },
    )
    expect(result.current.hasDraft).toBe(false)
    expect(result.current.restoreDraft()).toBeNull()
  })

  it('discardDraft removes localStorage entry and clears hasDraft', () => {
    window.localStorage.setItem(DRAFT_KEY, JSON.stringify({ a: 1 }))
    const { result } = renderHook(
      () => useUnsavedChangesGuard({ when: false, draftKey: DRAFT_KEY }),
      { wrapper: hookWrapper },
    )
    act(() => {
      result.current.discardDraft()
    })
    expect(window.localStorage.getItem(DRAFT_KEY)).toBeNull()
    expect(result.current.hasDraft).toBe(false)
  })

  it('debounced draft write persists after draftDebounceMs', () => {
    vi.useFakeTimers()
    try {
      const payload = { v: 2 }
      renderHook(
        () =>
          useUnsavedChangesGuard({
            when: true,
            draftKey: DRAFT_KEY,
            draftData: () => payload,
            draftDebounceMs: 100,
          }),
        { wrapper: hookWrapper },
      )
      act(() => {
        vi.advanceTimersByTime(150)
      })
      expect(JSON.parse(window.localStorage.getItem(DRAFT_KEY) ?? '{}')).toEqual({ v: 2 })
    } finally {
      vi.useRealTimers()
    }
  })

  it('beforeunload event is prevented when dirty', () => {
    renderHook(() => useUnsavedChangesGuard({ when: true }), { wrapper: hookWrapper })
    const event = new Event('beforeunload', { cancelable: true }) as BeforeUnloadEvent
    act(() => {
      fireEvent(window, event)
    })
    expect(event.defaultPrevented).toBe(true)
  })

  it('blocks navigation and exposes confirmOpen', async () => {
    const router = createMemoryRouter(
      [
        { path: '/a', element: <ConfirmHarnessPage /> },
        { path: '/b', element: <div>Page B</div> },
      ],
      { initialEntries: ['/a'] },
    )

    const { getByLabelText, getByTestId } = render(<RouterProvider router={router} />)

    expect(getByTestId('confirm').textContent).toBe('false')

    act(() => {
      fireEvent.click(getByLabelText('go-b'))
    })

    await waitFor(() => {
      expect(getByTestId('confirm').textContent).toBe('true')
    })

    act(() => {
      fireEvent.click(getByLabelText('cancel'))
    })

    await waitFor(() => {
      expect(getByTestId('confirm').textContent).toBe('false')
    })
  })

  it('proceed() clears draft on confirm and allows navigation', async () => {
    window.localStorage.setItem(DRAFT_KEY, JSON.stringify({ existing: true }))

    const router = createMemoryRouter(
      [
        { path: '/a', element: <ProceedDraftHarnessPage /> },
        { path: '/b', element: <div>Page B</div> },
      ],
      { initialEntries: ['/a'] },
    )

    const { getByLabelText } = render(<RouterProvider router={router} />)

    act(() => {
      fireEvent.click(getByLabelText('go-b'))
    })
    act(() => {
      fireEvent.click(getByLabelText('proceed'))
    })
    await waitFor(() => {
      expect(window.localStorage.getItem(DRAFT_KEY)).toBeNull()
    })
  })
})
