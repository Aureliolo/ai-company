import type { SliceCreator, ThemeSettings, ThemeSlice } from './types'

export const DEFAULT_THEME: ThemeSettings = {
  palette: 'warm-ops',
  density: 'balanced',
  animation: 'status-driven',
  sidebar: 'collapsible',
  typography: 'default',
}

export const createThemeSlice: SliceCreator<ThemeSlice> = (set) => ({
  themeSettings: { ...DEFAULT_THEME },

  setThemeSetting(key, value) {
    set((s) => ({ themeSettings: { ...s.themeSettings, [key]: value } }))
  },
})
