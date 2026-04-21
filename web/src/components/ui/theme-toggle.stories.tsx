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
    (Story) => (
      <div className="flex h-[500px] w-[400px] items-start justify-end p-8">
        <Story />
      </div>
    ),
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

export const ColorPaletteStealth: Story = {
  decorators: [
    (Story) => (
      <>
        <ApplyTheme palette="stealth" />
        <Story />
      </>
    ),
  ],
}

export const ColorPaletteNeon: Story = {
  decorators: [
    (Story) => (
      <>
        <ApplyTheme palette="neon" />
        <Story />
      </>
    ),
  ],
}

export const DensityDense: Story = {
  decorators: [
    (Story) => (
      <>
        <ApplyTheme density="dense" />
        <Story />
      </>
    ),
  ],
}

export const DensitySparse: Story = {
  decorators: [
    (Story) => (
      <>
        <ApplyTheme density="sparse" />
        <Story />
      </>
    ),
  ],
}

export const AnimationInstant: Story = {
  decorators: [
    (Story) => (
      <>
        <ApplyTheme animation="instant" />
        <Story />
      </>
    ),
  ],
}

export const AnimationMinimal: Story = {
  decorators: [
    (Story) => (
      <>
        <ApplyTheme animation="minimal" />
        <Story />
      </>
    ),
  ],
}

export const TypographyJetbrains: Story = {
  decorators: [
    (Story) => (
      <>
        <ApplyTheme typography="jetbrains" />
        <Story />
      </>
    ),
  ],
}

export const SidebarRail: Story = {
  decorators: [
    (Story) => (
      <>
        <ApplyTheme sidebar="rail" />
        <Story />
      </>
    ),
  ],
}
