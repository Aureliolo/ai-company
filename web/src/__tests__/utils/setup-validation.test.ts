import {
  validateAccountStep,
  validateTemplateStep,
  validateCompanyStep,
  validateAgentsStep,
  validateProvidersStep,
  validateThemeStep,
} from '@/utils/setup-validation'
import type { SetupAgentSummary, SetupCompanyResponse, ProviderConfig } from '@/api/types'

const makeAgent = (overrides: Partial<SetupAgentSummary> = {}): SetupAgentSummary => ({
  name: 'Test Agent',
  role: 'Developer',
  department: 'engineering',
  level: 'mid',
  model_provider: 'test-provider',
  model_id: 'test-model-001',
  tier: 'medium',
  personality_preset: null,
  ...overrides,
})

const makeCompanyResponse = (
  overrides: Partial<SetupCompanyResponse> = {},
): SetupCompanyResponse => ({
  company_name: 'Acme Corp',
  description: null,
  template_applied: 'startup',
  department_count: 3,
  agent_count: 5,
  agents: [],
  ...overrides,
})

const makeProvider = (overrides: Partial<ProviderConfig> = {}): ProviderConfig => ({
  driver: 'test-provider',
  litellm_provider: null,
  auth_type: 'api_key',
  base_url: null,
  models: [],
  has_api_key: true,
  has_oauth_credentials: false,
  has_custom_header: false,
  has_subscription_token: false,
  tos_accepted_at: null,
  oauth_token_url: null,
  oauth_client_id: null,
  oauth_scope: null,
  custom_header_name: null,
  ...overrides,
})

describe('validateAccountStep', () => {
  it('returns valid when accountCreated is true', () => {
    const result = validateAccountStep({ accountCreated: true, needsAdmin: true })
    expect(result.valid).toBe(true)
    expect(result.errors).toHaveLength(0)
  })

  it('returns valid when needsAdmin is false (skip account step)', () => {
    const result = validateAccountStep({ accountCreated: false, needsAdmin: false })
    expect(result.valid).toBe(true)
  })

  it('returns invalid when needsAdmin and account not created', () => {
    const result = validateAccountStep({ accountCreated: false, needsAdmin: true })
    expect(result.valid).toBe(false)
    expect(result.errors.length).toBeGreaterThan(0)
  })
})

describe('validateTemplateStep', () => {
  it('returns valid when template is selected', () => {
    const result = validateTemplateStep({ selectedTemplate: 'startup' })
    expect(result.valid).toBe(true)
    expect(result.errors).toHaveLength(0)
  })

  it('returns invalid when no template selected', () => {
    const result = validateTemplateStep({ selectedTemplate: null })
    expect(result.valid).toBe(false)
    expect(result.errors).toContain('Please select a template')
  })
})

describe('validateCompanyStep', () => {
  it('returns valid with company name and response', () => {
    const result = validateCompanyStep({
      companyName: 'Acme Corp',
      companyDescription: '',
      companyResponse: makeCompanyResponse(),
    })
    expect(result.valid).toBe(true)
    expect(result.errors).toHaveLength(0)
  })

  it('returns invalid when company name is empty', () => {
    const result = validateCompanyStep({
      companyName: '',
      companyDescription: '',
      companyResponse: null,
    })
    expect(result.valid).toBe(false)
    expect(result.errors).toContain('Company name is required')
  })

  it('returns invalid when company name is only whitespace', () => {
    const result = validateCompanyStep({
      companyName: '   ',
      companyDescription: '',
      companyResponse: null,
    })
    expect(result.valid).toBe(false)
    expect(result.errors).toContain('Company name is required')
  })

  it('returns invalid when company name exceeds 200 characters', () => {
    const result = validateCompanyStep({
      companyName: 'A'.repeat(201),
      companyDescription: '',
      companyResponse: null,
    })
    expect(result.valid).toBe(false)
    expect(result.errors.some((e) => e.includes('200'))).toBe(true)
  })

  it('returns invalid when description exceeds 1000 characters', () => {
    const result = validateCompanyStep({
      companyName: 'Acme',
      companyDescription: 'A'.repeat(1001),
      companyResponse: null,
    })
    expect(result.valid).toBe(false)
    expect(result.errors.some((e) => e.includes('1000'))).toBe(true)
  })

  it('returns invalid when template not yet applied (no response)', () => {
    const result = validateCompanyStep({
      companyName: 'Acme',
      companyDescription: '',
      companyResponse: null,
    })
    expect(result.valid).toBe(false)
    expect(result.errors).toContain('Apply the template to continue')
  })
})

describe('validateAgentsStep', () => {
  it('returns valid when agents have required fields', () => {
    const result = validateAgentsStep({
      agents: [makeAgent(), makeAgent({ name: 'Agent 2' })],
    })
    expect(result.valid).toBe(true)
    expect(result.errors).toHaveLength(0)
  })

  it('returns invalid when agent list is empty', () => {
    const result = validateAgentsStep({ agents: [] })
    expect(result.valid).toBe(false)
    expect(result.errors).toContain('At least one agent is required')
  })

  it('returns invalid when an agent has no model_provider', () => {
    const result = validateAgentsStep({
      agents: [makeAgent({ model_provider: '' })],
    })
    expect(result.valid).toBe(false)
    expect(result.errors.some((e) => e.includes('model'))).toBe(true)
  })

  it('returns invalid when an agent has no model_id', () => {
    const result = validateAgentsStep({
      agents: [makeAgent({ model_id: '' })],
    })
    expect(result.valid).toBe(false)
    expect(result.errors.some((e) => e.includes('model'))).toBe(true)
  })
})

describe('validateProvidersStep', () => {
  it('returns valid when all agent providers are configured', () => {
    const result = validateProvidersStep({
      agents: [makeAgent({ model_provider: 'test-provider' })],
      providers: { 'test-provider': makeProvider() },
    })
    expect(result.valid).toBe(true)
    expect(result.errors).toHaveLength(0)
  })

  it('returns invalid when no providers configured', () => {
    const result = validateProvidersStep({
      agents: [makeAgent()],
      providers: {},
    })
    expect(result.valid).toBe(false)
    expect(result.errors).toContain('At least one provider is required')
  })

  it('returns invalid when an agent references a missing provider', () => {
    const result = validateProvidersStep({
      agents: [makeAgent({ model_provider: 'missing-provider' })],
      providers: { 'other-provider': makeProvider() },
    })
    expect(result.valid).toBe(false)
    expect(result.errors.some((e) => e.includes('missing-provider'))).toBe(true)
  })

  it('returns valid with multiple agents using different providers', () => {
    const result = validateProvidersStep({
      agents: [
        makeAgent({ model_provider: 'provider-a' }),
        makeAgent({ model_provider: 'provider-b' }),
      ],
      providers: {
        'provider-a': makeProvider(),
        'provider-b': makeProvider(),
      },
    })
    expect(result.valid).toBe(true)
  })
})

describe('validateThemeStep', () => {
  it('always returns valid (all settings have defaults)', () => {
    const result = validateThemeStep()
    expect(result.valid).toBe(true)
    expect(result.errors).toHaveLength(0)
  })
})
