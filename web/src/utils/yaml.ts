import YAML from 'js-yaml'
import type { CompanyConfig } from '@/api/types/org'

/**
 * Serialize a CompanyConfig to a YAML string for the code editor.
 *
 * Strips readonly markers via JSON round-trip before dumping.
 */
export function serializeToYaml(config: CompanyConfig): string {
  const plain = JSON.parse(JSON.stringify(config)) as Record<string, unknown>
  return YAML.dump(plain, { indent: 2, lineWidth: 120, noRefs: true, sortKeys: false })
}

/**
 * Parse a YAML string into a plain object.
 *
 * Throws if the input is not valid YAML or not an object at the top level.
 */
export function parseYaml(yamlStr: string): Record<string, unknown> {
  const result = YAML.load(yamlStr, { schema: YAML.CORE_SCHEMA })
  if (result === null || result === undefined || typeof result !== 'object' || Array.isArray(result)) {
    throw new Error('YAML must be a mapping (object) at the top level')
  }
  return result as Record<string, unknown>
}

/**
 * Validate that a parsed YAML object has the expected CompanyConfig shape.
 *
 * Only checks top-level types (company_name, agents array, departments array).
 * Nested element validation (AgentConfig/Department structures) is deferred
 * to server-side API validation.
 *
 * Returns an error message string, or null if valid.
 */
export function validateCompanyYaml(parsed: Record<string, unknown>): string | null {
  if (typeof parsed.company_name !== 'string' || parsed.company_name.trim() === '') {
    return 'company_name must be a non-empty string'
  }
  if ('agents' in parsed && !Array.isArray(parsed.agents)) {
    return 'agents must be an array'
  }
  if ('departments' in parsed && !Array.isArray(parsed.departments)) {
    return 'departments must be an array'
  }
  if ('autonomy_level' in parsed && typeof parsed.autonomy_level !== 'string') {
    return 'autonomy_level must be a string'
  }
  if ('budget_monthly' in parsed && typeof parsed.budget_monthly !== 'number') {
    return 'budget_monthly must be a number'
  }
  if ('communication_pattern' in parsed && typeof parsed.communication_pattern !== 'string') {
    return 'communication_pattern must be a string'
  }
  return null
}
