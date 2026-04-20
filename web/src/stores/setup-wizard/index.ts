import { create } from 'zustand'
import { createAgentsSlice } from './agents'
import { createCompanySlice } from './company'
import { createCompletionSlice } from './completion'
import { createNavigationSlice } from './navigation'
import { createProvidersSlice } from './providers'
import { createTemplateSlice } from './template'
import { createThemeSlice } from './theme'
import type { SetupWizardState } from './types'

export type {
  SetupWizardState,
  ThemeSettings,
  WizardMode,
  WizardStep,
} from './types'

export const useSetupWizardStore = create<SetupWizardState>()((...a) => ({
  ...createNavigationSlice(...a),
  ...createTemplateSlice(...a),
  ...createCompanySlice(...a),
  ...createAgentsSlice(...a),
  ...createProvidersSlice(...a),
  ...createThemeSlice(...a),
  ...createCompletionSlice(...a),
}))
