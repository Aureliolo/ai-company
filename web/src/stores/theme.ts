import { create } from 'zustand'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ColorPalette = 'warm-ops' | 'ice-station' | 'stealth' | 'signal' | 'neon'
export type Density = 'dense' | 'balanced' | 'medium' | 'sparse'
export type Typography = 'geist' | 'jetbrains' | 'ibm-plex'
export type AnimationPreset = 'minimal' | 'spring' | 'instant' | 'status-driven' | 'aggressive'
export type SidebarMode = 'rail' | 'collapsible' | 'hidden' | 'persistent' | 'compact'

export interface ThemePreferences {
  colorPalette: ColorPalette
  density: Density
  typography: Typography
  animation: AnimationPreset
  sidebarMode: SidebarMode
}

export interface ThemeState extends ThemePreferences {
  popoverOpen: boolean
  reducedMotionDetected: boolean
  setColorPalette: (value: ColorPalette) => void
  setDensity: (value: Density) => void
  setTypography: (value: Typography) => void
  setAnimation: (value: AnimationPreset) => void
  setSidebarMode: (value: SidebarMode) => void
  setPopoverOpen: (open: boolean) => void
  reset: () => void
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STORAGE_KEY = 'so_theme_preferences'

export const COLOR_PALETTES = ['warm-ops', 'ice-station', 'stealth', 'signal', 'neon'] as const satisfies readonly ColorPalette[]
export const DENSITIES = ['dense', 'balanced', 'medium', 'sparse'] as const satisfies readonly Density[]
export const TYPOGRAPHIES = ['geist', 'jetbrains', 'ibm-plex'] as const satisfies readonly Typography[]
export const ANIMATION_PRESETS = ['minimal', 'spring', 'instant', 'status-driven', 'aggressive'] as const satisfies readonly AnimationPreset[]
export const SIDEBAR_MODES = ['rail', 'collapsible', 'hidden', 'persistent', 'compact'] as const satisfies readonly SidebarMode[]

// CSS classes for each axis (applied to <html>)
const THEME_CLASSES = COLOR_PALETTES.map((p) => `theme-${p}`)
const DENSITY_CLASSES = DENSITIES.filter((d) => d !== 'balanced').map((d) => `density-${d}`)
const TYPOGRAPHY_CLASSES = TYPOGRAPHIES.filter((t) => t !== 'geist').map((t) => `typography-${t}`)
const ANIMATION_CLASSES = ANIMATION_PRESETS.map((a) => `animation-${a}`)
const SIDEBAR_CLASSES = SIDEBAR_MODES.filter((s) => s !== 'collapsible').map((s) => `sidebar-${s}`)

const ALL_THEME_CLASSES = [
  ...THEME_CLASSES,
  ...DENSITY_CLASSES,
  ...TYPOGRAPHY_CLASSES,
  ...ANIMATION_CLASSES,
  ...SIDEBAR_CLASSES,
]

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function detectReducedMotion(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function getDefaultPreferences(): ThemePreferences {
  return {
    colorPalette: 'warm-ops',
    density: 'balanced',
    typography: 'geist',
    animation: detectReducedMotion() ? 'minimal' : 'status-driven',
    sidebarMode: 'collapsible',
  }
}

function isValid<T extends string>(value: unknown, allowed: readonly T[]): value is T {
  return typeof value === 'string' && (allowed as readonly string[]).includes(value)
}

/** Exported for testing only -- the store already calls this at creation time. */
export function loadPreferences(): ThemePreferences {
  const defaults = getDefaultPreferences()
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return defaults
    const parsed: unknown = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return defaults
    const obj = parsed as Record<string, unknown>
    return {
      colorPalette: isValid(obj.colorPalette, COLOR_PALETTES) ? obj.colorPalette : defaults.colorPalette,
      density: isValid(obj.density, DENSITIES) ? obj.density : defaults.density,
      typography: isValid(obj.typography, TYPOGRAPHIES) ? obj.typography : defaults.typography,
      animation: isValid(obj.animation, ANIMATION_PRESETS) ? obj.animation : defaults.animation,
      sidebarMode: isValid(obj.sidebarMode, SIDEBAR_MODES) ? obj.sidebarMode : defaults.sidebarMode,
    }
  } catch (err) {
    console.warn('[theme] Failed to load preferences, using defaults:', err)
    return defaults
  }
}

function savePreferences(prefs: ThemePreferences): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs))
  } catch (err) {
    console.warn('[theme] Failed to save preferences (localStorage may be unavailable):', err)
  }
}

/** Guard against CSS class name injection -- only lowercase alphanumeric and hyphens. */
const CSS_CLASS_SAFE = /^[a-z0-9-]+$/

function safeClass(cls: string): string {
  if (!CSS_CLASS_SAFE.test(cls)) {
    throw new Error(`Unsafe CSS class name blocked (length=${cls.length})`)
  }
  return cls
}

/** Apply theme classes to document.documentElement. */
export function applyThemeClasses(prefs: ThemePreferences): void {
  if (typeof document === 'undefined') return
  const el = document.documentElement

  // Remove all existing theme classes
  el.classList.remove(...ALL_THEME_CLASSES)

  // Add current classes (skip defaults that have no class)
  if (prefs.colorPalette !== 'warm-ops') {
    el.classList.add(safeClass(`theme-${prefs.colorPalette}`))
  }
  if (prefs.density !== 'balanced') {
    el.classList.add(safeClass(`density-${prefs.density}`))
  }
  if (prefs.typography !== 'geist') {
    el.classList.add(safeClass(`typography-${prefs.typography}`))
  }
  el.classList.add(safeClass(`animation-${prefs.animation}`))
  if (prefs.sidebarMode !== 'collapsible') {
    el.classList.add(safeClass(`sidebar-${prefs.sidebarMode}`))
  }
}

function getPrefs(state: ThemeState): ThemePreferences {
  return {
    colorPalette: state.colorPalette,
    density: state.density,
    typography: state.typography,
    animation: state.animation,
    sidebarMode: state.sidebarMode,
  }
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useThemeStore = create<ThemeState>()((set, get) => {
  const initial = loadPreferences()
  const reducedMotion = detectReducedMotion()

  // Apply initial theme classes synchronously (wrapped for resilience --
  // a corrupted localStorage value that bypasses isValid would crash the app)
  try {
    applyThemeClasses(initial)
  } catch (err) {
    console.warn('[theme] Failed to apply initial theme classes:', err)
  }

  // Listen for reduced-motion changes
  if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
    const mql = window.matchMedia('(prefers-reduced-motion: reduce)')
    mql.addEventListener('change', (e) => {
      set({ reducedMotionDetected: e.matches })
      // Follow OS reduced-motion preference: always switch to minimal when
      // OS requests it; revert to default when OS lifts the preference
      // (unless user already chose minimal).
      const state = get()
      const defaults = getDefaultPreferences()
      if (state.animation === defaults.animation || (e.matches && state.animation !== 'minimal')) {
        const newAnimation: AnimationPreset = e.matches ? 'minimal' : 'status-driven'
        const prefs = { ...getPrefs(state), animation: newAnimation }
        savePreferences(prefs)
        applyThemeClasses(prefs)
        set({ animation: newAnimation })
      }
    })
  }

  return {
    ...initial,
    popoverOpen: false,
    reducedMotionDetected: reducedMotion,

    setColorPalette: (colorPalette) => {
      set({ colorPalette })
      const prefs = { ...getPrefs(get()), colorPalette }
      savePreferences(prefs)
      applyThemeClasses(prefs)
    },

    setDensity: (density) => {
      set({ density })
      const prefs = { ...getPrefs(get()), density }
      savePreferences(prefs)
      applyThemeClasses(prefs)
    },

    setTypography: (typography) => {
      set({ typography })
      const prefs = { ...getPrefs(get()), typography }
      savePreferences(prefs)
      applyThemeClasses(prefs)
    },

    setAnimation: (animation) => {
      set({ animation })
      const prefs = { ...getPrefs(get()), animation }
      savePreferences(prefs)
      applyThemeClasses(prefs)
    },

    setSidebarMode: (sidebarMode) => {
      set({ sidebarMode })
      const prefs = { ...getPrefs(get()), sidebarMode }
      savePreferences(prefs)
      applyThemeClasses(prefs)
    },

    setPopoverOpen: (popoverOpen) => set({ popoverOpen }),

    reset: () => {
      const defaults = getDefaultPreferences()
      set({ ...defaults })
      applyThemeClasses(defaults)
      try {
        localStorage.removeItem(STORAGE_KEY)
      } catch (err) {
        console.warn('[theme] Failed to clear stored preferences:', err)
      }
    },
  }
})
