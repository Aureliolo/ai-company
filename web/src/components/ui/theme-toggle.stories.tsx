import { useEffect } from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { useThemeStore } from '@/stores/theme'
import { ThemeToggle } from './theme-toggle'

const meta = {
  title: 'UI/ThemeToggle',
  component: ThemeToggle,
  tags: ['autodocs'],
  parameters: { layout: 'centered' },
  decorators: [
    (Story) => {
      // Snapshot + restore the theme-store state on every story mount so
      // variant decorators (ColorPalette*, Density*, ...) never leak into
      // subsequent stories rendered in the same page navigation.
      useEffect(() => {
        const initial = useThemeStore.getState()
        const snapshot = {
          colorPalette: initial.colorPalette,
          density: initial.density,
          animation: initial.animation,
          typography: initial.typography,
          sidebarMode: initial.sidebarMode,
          popoverOpen: initial.popoverOpen,
        }
        return () => {
          const s = useThemeStore.getState()
          s.setColorPalette(snapshot.colorPalette)
          s.setDensity(snapshot.density)
          s.setAnimation(snapshot.animation)
          s.setTypography(snapshot.typography)
          s.setSidebarMode(snapshot.sidebarMode)
          s.setPopoverOpen(snapshot.popoverOpen)
        }
      }, [])
      return (
        <div className="flex h-[30rem] w-96 items-start justify-end p-8">
          <Story />
        </div>
      )
    },
  ],
} satisfies Meta<typeof ThemeToggle>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}

function PopoverOpenDecorator({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    useThemeStore.getState().setPopoverOpen(true)
  }, [])
  return <>{children}</>
}

export const PopoverOpen: Story = {
  decorators: [
    (Story) => (
      <PopoverOpenDecorator>
        <Story />
      </PopoverOpenDecorator>
    ),
  ],
}

type ThemeStoreState = ReturnType<typeof useThemeStore.getState>
type PaletteArg = Parameters<ThemeStoreState['setColorPalette']>[0]
type DensityArg = Parameters<ThemeStoreState['setDensity']>[0]
type AnimationArg = Parameters<ThemeStoreState['setAnimation']>[0]
type TypographyArg = Parameters<ThemeStoreState['setTypography']>[0]
type SidebarArg = Parameters<ThemeStoreState['setSidebarMode']>[0]

interface ApplyThemeProps {
  palette?: PaletteArg
  density?: DensityArg
  animation?: AnimationArg
  typography?: TypographyArg
  sidebar?: SidebarArg
}

function ApplyTheme({ palette, density, animation, typography, sidebar }: ApplyThemeProps) {
  useEffect(() => {
    const s = useThemeStore.getState()
    if (palette) s.setColorPalette(palette)
    if (density) s.setDensity(density)
    if (animation) s.setAnimation(animation)
    if (typography) s.setTypography(typography)
    if (sidebar) s.setSidebarMode(sidebar)
    s.setPopoverOpen(true)
  }, [palette, density, animation, typography, sidebar])
  return null
}

function variantStory(props: ApplyThemeProps): Story {
  return {
    decorators: [
      (Story) => (
        <>
          <ApplyTheme {...props} />
          <Story />
        </>
      ),
    ],
  }
}

export const ColorPaletteStealth: Story = variantStory({ palette: 'stealth' })
export const ColorPaletteNeon: Story = variantStory({ palette: 'neon' })
export const DensityDense: Story = variantStory({ density: 'dense' })
export const DensitySparse: Story = variantStory({ density: 'sparse' })
export const AnimationInstant: Story = variantStory({ animation: 'instant' })
export const AnimationMinimal: Story = variantStory({ animation: 'minimal' })
export const TypographyJetbrains: Story = variantStory({ typography: 'jetbrains' })
export const SidebarRail: Story = variantStory({ sidebar: 'rail' })
