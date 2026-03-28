import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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

  it('resets to defaults', async () => {
    const user = userEvent.setup()

    // Change some settings first
    useThemeStore.getState().setColorPalette('neon')
    useThemeStore.getState().setDensity('sparse')

    render(<ThemeToggle />)
    await user.click(screen.getByRole('button', { name: 'Theme preferences' }))
    await user.click(screen.getByRole('button', { name: 'Reset to defaults' }))

    const state = useThemeStore.getState()
    expect(state.colorPalette).toBe('warm-ops')
    expect(state.density).toBe('balanced')
  })

  it('changes typography via select', async () => {
    const user = userEvent.setup()
    render(<ThemeToggle />)
    await user.click(screen.getByRole('button', { name: 'Theme preferences' }))

    const fontSelect = screen.getByLabelText('Font')
    await user.selectOptions(fontSelect, 'ibm-plex')

    expect(useThemeStore.getState().typography).toBe('ibm-plex')
  })
})
