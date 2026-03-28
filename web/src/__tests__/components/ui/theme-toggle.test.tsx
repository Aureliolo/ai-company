import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import fc from 'fast-check'
import { describe, it, expect, beforeEach } from 'vitest'
import { ThemeToggle } from '@/components/ui/theme-toggle'
import { useThemeStore } from '@/stores/theme'

describe('ThemeToggle', () => {
  beforeEach(() => {
    useThemeStore.getState().reset()
    useThemeStore.getState().setPopoverOpen(false)
  })

  it('renders the trigger button', () => {
    render(<ThemeToggle />)
    expect(screen.getByRole('button', { name: 'Theme preferences' })).toBeInTheDocument()
  })

  it('opens popover on click', async () => {
    const user = userEvent.setup()
    render(<ThemeToggle />)

    await user.click(screen.getByRole('button', { name: 'Theme preferences' }))
    expect(screen.getByText('Theme Preferences')).toBeInTheDocument()
  })

  it('displays all 5 axis controls when open', async () => {
    const user = userEvent.setup()
    render(<ThemeToggle />)
    await user.click(screen.getByRole('button', { name: 'Theme preferences' }))

    // Color (select) + Font (select) labels
    expect(screen.getByLabelText('Color')).toBeInTheDocument()
    expect(screen.getByLabelText('Font')).toBeInTheDocument()

    // Density, Motion, Sidebar segmented controls (visible labels -- multiple matches due to sr-only legend)
    expect(screen.getAllByText('Density').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Motion')).toBeInTheDocument()
    expect(screen.getAllByText('Sidebar').length).toBeGreaterThanOrEqual(1)
  })

  it('changes color palette via select', async () => {
    const user = userEvent.setup()
    render(<ThemeToggle />)
    await user.click(screen.getByRole('button', { name: 'Theme preferences' }))

    const colorSelect = screen.getByLabelText('Color')
    await user.selectOptions(colorSelect, 'ice-station')

    expect(useThemeStore.getState().colorPalette).toBe('ice-station')
  })

  it('changes density via segmented control', async () => {
    const user = userEvent.setup()
    render(<ThemeToggle />)
    await user.click(screen.getByRole('button', { name: 'Theme preferences' }))

    await user.click(screen.getByRole('radio', { name: 'Dense' }))
    expect(useThemeStore.getState().density).toBe('dense')
  })

  it('resets all 5 axes to defaults', async () => {
    const user = userEvent.setup()

    // Change all 5 axes
    useThemeStore.getState().setColorPalette('neon')
    useThemeStore.getState().setDensity('sparse')
    useThemeStore.getState().setTypography('ibm-plex')
    useThemeStore.getState().setAnimation('aggressive')
    useThemeStore.getState().setSidebarMode('rail')

    render(<ThemeToggle />)
    await user.click(screen.getByRole('button', { name: 'Theme preferences' }))
    await user.click(screen.getByRole('button', { name: 'Reset to defaults' }))

    const state = useThemeStore.getState()
    expect(state.colorPalette).toBe('warm-ops')
    expect(state.density).toBe('balanced')
    expect(state.typography).toBe('geist')
    expect(['minimal', 'status-driven']).toContain(state.animation)
    expect(state.sidebarMode).toBe('collapsible')
  })

  it('changes typography via select', async () => {
    const user = userEvent.setup()
    render(<ThemeToggle />)
    await user.click(screen.getByRole('button', { name: 'Theme preferences' }))

    const fontSelect = screen.getByLabelText('Font')
    await user.selectOptions(fontSelect, 'ibm-plex')

    expect(useThemeStore.getState().typography).toBe('ibm-plex')
  })

  it('changes animation via segmented control', async () => {
    const user = userEvent.setup()
    render(<ThemeToggle />)
    await user.click(screen.getByRole('button', { name: 'Theme preferences' }))

    await user.click(screen.getByRole('radio', { name: 'Instant' }))
    expect(useThemeStore.getState().animation).toBe('instant')
  })

  it('changes sidebar mode via segmented control', async () => {
    const user = userEvent.setup()
    render(<ThemeToggle />)
    await user.click(screen.getByRole('button', { name: 'Theme preferences' }))

    await user.click(screen.getByRole('radio', { name: 'Rail' }))
    expect(useThemeStore.getState().sidebarMode).toBe('rail')
  })

  // Property test exercises the store layer that ThemeToggle wires to.
  // UI-level axis tests above (color, density, typography, animation, sidebar)
  // already verify the wiring; this confirms the store contract for all values.
  it('synchronizes random palette changes via store', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('warm-ops' as const, 'ice-station' as const, 'stealth' as const, 'signal' as const, 'neon' as const),
        (palette) => {
          useThemeStore.getState().setColorPalette(palette)
          expect(useThemeStore.getState().colorPalette).toBe(palette)
        },
      ),
    )
  })
})
