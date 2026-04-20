import { describe, expect, it } from 'vitest'
import fc from 'fast-check'
import { parseYaml, serializeToYaml, validateCompanyYaml } from '@/utils/yaml'
import { makeCompanyConfig } from '../helpers/factories'
import type { CompanyConfig } from '@/api/types/org'

describe('serializeToYaml', () => {
  it('serializes a CompanyConfig to valid YAML', () => {
    const config = makeCompanyConfig()
    const yaml = serializeToYaml(config)
    expect(yaml).toContain('company_name: Test Corp')
    expect(yaml).toContain('agents:')
    expect(yaml).toContain('departments:')
  })

  it('produces parseable YAML that round-trips', () => {
    const config = makeCompanyConfig()
    const yaml = serializeToYaml(config)
    const parsed = parseYaml(yaml)
    expect(parsed.company_name).toBe('Test Corp')
    expect(parsed.agents).toHaveLength(3)
    expect(parsed.departments).toHaveLength(2)
  })
})

describe('parseYaml', () => {
  it('parses a valid YAML string', () => {
    const parsed = parseYaml('company_name: Acme\nagents: []\n')
    expect(parsed.company_name).toBe('Acme')
    expect(parsed.agents).toEqual([])
  })

  it('throws on non-object YAML (string)', () => {
    expect(() => parseYaml('"just a string"')).toThrow('mapping')
  })

  it('throws on non-object YAML (array)', () => {
    expect(() => parseYaml('- item1\n- item2\n')).toThrow('mapping')
  })

  it('throws on empty YAML', () => {
    expect(() => parseYaml('')).toThrow('mapping')
  })

  it('throws on invalid YAML syntax', () => {
    expect(() => parseYaml('{ bad yaml [')).toThrow()
  })
})

describe('validateCompanyYaml', () => {
  it('returns null for valid config', () => {
    const parsed = { company_name: 'Acme', agents: [], departments: [] }
    expect(validateCompanyYaml(parsed)).toBeNull()
  })

  it('rejects missing company_name', () => {
    expect(validateCompanyYaml({ agents: [] })).toContain('company_name')
  })

  it('rejects empty company_name', () => {
    expect(validateCompanyYaml({ company_name: '  ' })).toContain('company_name')
  })

  it('rejects non-array agents', () => {
    expect(validateCompanyYaml({ company_name: 'X', agents: 'bad' })).toContain('agents')
  })

  it('rejects non-array departments', () => {
    expect(validateCompanyYaml({ company_name: 'X', departments: 'bad' })).toContain('departments')
  })

  it('accepts config without agents/departments keys', () => {
    expect(validateCompanyYaml({ company_name: 'Minimal' })).toBeNull()
  })
})

describe('serializeToYaml / parseYaml property-based round-trip', () => {
  const arbAgent = fc.record({
    name: fc.string({ minLength: 1, maxLength: 20 }),
    role: fc.string({ minLength: 1, maxLength: 30 }),
    department: fc.string({ minLength: 1, maxLength: 20 }),
  })

  const arbDepartment = fc.record({
    name: fc.string({ minLength: 1, maxLength: 20 }),
    display_name: fc.string({ minLength: 1, maxLength: 30 }),
  })

  const arbCompanyConfig = fc.record({
    company_name: fc.string({ minLength: 1, maxLength: 50 }),
    agents: fc.array(arbAgent, { minLength: 0, maxLength: 5 }),
    departments: fc.array(arbDepartment, { minLength: 0, maxLength: 5 }),
  })

  it('round-trips company_name and array lengths', () => {
    fc.assert(
      fc.property(arbCompanyConfig, (config) => {
        const yaml = serializeToYaml(config as unknown as CompanyConfig)
        const parsed = parseYaml(yaml)
        expect(parsed.company_name).toBe(config.company_name)
        expect(parsed.agents).toHaveLength(config.agents.length)
        expect(parsed.departments).toHaveLength(config.departments.length)
      }),
      { numRuns: 50 },
    )
  })
})
