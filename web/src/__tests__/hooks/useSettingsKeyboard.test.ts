import { renderHook } from '@testing-library/react'
import { useSettingsKeyboard } from '@/hooks/useSettingsKeyboard'

describe('useSettingsKeyboard', () => {
  it('calls onSave on Ctrl+S when canSave is true', () => {
    const onSave = vi.fn()
    const onSearchFocus = vi.fn()
    renderHook(() =>
      useSettingsKeyboard({ onSave, onSearchFocus, canSave: true }),
    )
    const event = new KeyboardEvent('keydown', {
      key: 's',
      ctrlKey: true,
      bubbles: true,
    })
    document.dispatchEvent(event)
    expect(onSave).toHaveBeenCalledOnce()
  })

  it('does not call onSave when canSave is false', () => {
    const onSave = vi.fn()
    const onSearchFocus = vi.fn()
    renderHook(() =>
      useSettingsKeyboard({ onSave, onSearchFocus, canSave: false }),
    )
    const event = new KeyboardEvent('keydown', {
      key: 's',
      ctrlKey: true,
      bubbles: true,
    })
    document.dispatchEvent(event)
    expect(onSave).not.toHaveBeenCalled()
  })

  it('calls onSearchFocus on Ctrl+/', () => {
    const onSave = vi.fn()
    const onSearchFocus = vi.fn()
    renderHook(() =>
      useSettingsKeyboard({ onSave, onSearchFocus, canSave: false }),
    )
    const event = new KeyboardEvent('keydown', {
      key: '/',
      ctrlKey: true,
      bubbles: true,
    })
    document.dispatchEvent(event)
    expect(onSearchFocus).toHaveBeenCalledOnce()
  })

  it('cleans up event listener on unmount', () => {
    const spy = vi.spyOn(document, 'removeEventListener')
    const { unmount } = renderHook(() =>
      useSettingsKeyboard({
        onSave: vi.fn(),
        onSearchFocus: vi.fn(),
        canSave: false,
      }),
    )
    unmount()
    expect(spy).toHaveBeenCalledWith('keydown', expect.any(Function))
    spy.mockRestore()
  })
})
