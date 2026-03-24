import { createContext, useContext, useMemo } from "react"
import { useParams } from "react-router-dom"
import type { ThemeConfig, VariationSlug } from "./types.ts"
import { themes } from "./index.ts"

const ThemeContext = createContext<ThemeConfig | null>(null)

function buildCssVariables(theme: ThemeConfig): React.CSSProperties {
  return {
    "--theme-bg-base": theme.colors.bgBase,
    "--theme-bg-surface": theme.colors.bgSurface,
    "--theme-bg-card": theme.colors.bgCard,
    "--theme-bg-card-hover": theme.colors.bgCardHover,
    "--theme-border": theme.colors.border,
    "--theme-border-bright": theme.colors.borderBright,
    "--theme-accent": theme.colors.accent,
    "--theme-accent-dim": theme.colors.accentDim,
    "--theme-accent-glow": theme.colors.accentGlow,
    "--theme-success": theme.colors.success,
    "--theme-warning": theme.colors.warning,
    "--theme-danger": theme.colors.danger,
    "--theme-text-primary": theme.colors.textPrimary,
    "--theme-text-secondary": theme.colors.textSecondary,
    "--theme-text-muted": theme.colors.textMuted,
    "--theme-font-mono": theme.typography.fontMono,
    "--theme-font-sans": theme.typography.fontSans,
  } as React.CSSProperties
}

interface ThemeProviderProps {
  children: React.ReactNode
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const { variation } = useParams<{ variation: string }>()

  const theme = useMemo(() => {
    const slug = (variation ?? "a") as VariationSlug
    return themes[slug] ?? themes.a
  }, [variation])

  const cssVariables = useMemo(() => buildCssVariables(theme), [theme])

  return (
    <ThemeContext value={theme}>
      <div
        style={cssVariables}
        className="min-h-screen"
        data-theme={theme.id}
      >
        {children}
      </div>
    </ThemeContext>
  )
}

export function useTheme(): ThemeConfig {
  const ctx = useContext(ThemeContext)
  if (ctx === null) {
    throw new Error("useTheme must be used within a ThemeProvider")
  }
  return ctx
}
