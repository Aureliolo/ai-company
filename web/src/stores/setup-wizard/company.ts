import { createCompany } from '@/api/endpoints/setup'
import { createLogger } from '@/lib/logger'
import { DEFAULT_CURRENCY } from '@/utils/currencies'
import { getErrorMessage } from '@/utils/errors'
import type { CompanySlice, SliceCreator } from './types'

const log = createLogger('setup-wizard:company')

export const createCompanySlice: SliceCreator<CompanySlice> = (set, get) => ({
  companyName: '',
  companyDescription: '',
  currency: DEFAULT_CURRENCY,
  budgetCapEnabled: false,
  budgetCap: null,
  companyResponse: null,
  companyLoading: false,
  companyError: null,

  setCompanyName(name) {
    set({ companyName: name })
  },

  setCompanyDescription(desc) {
    set({ companyDescription: desc })
  },

  setCurrency(currency) {
    set({ currency })
  },

  setBudgetCapEnabled(enabled) {
    set({ budgetCapEnabled: enabled })
  },

  setBudgetCap(cap) {
    set({ budgetCap: cap })
  },

  async submitCompany() {
    const { companyName, companyDescription, selectedTemplate } = get()
    set({ companyLoading: true, companyError: null })
    try {
      const response = await createCompany({
        company_name: companyName.trim(),
        description: companyDescription.trim() || null,
        template_name: selectedTemplate,
      })
      set({
        companyResponse: response,
        agents: [...response.agents],
        companyLoading: false,
      })
    } catch (err) {
      log.error('submitCompany failed:', getErrorMessage(err))
      set({ companyError: getErrorMessage(err), companyLoading: false })
    }
  },
})
