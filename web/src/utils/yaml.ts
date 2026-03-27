import YAML from 'js-yaml'
import type { CompanyConfig } from '@/api/types'

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
  const result = YAML.load(yamlStr)
  if (result === null || result === undefined || typeof result !== 'object' || Array.isArray(result)) {
    throw new Error('YAML must be a mapping (object) at the top level')
  }
  return result as Record<string, unknown>
}

/**
 * Validate that a parsed YAML object has the expected CompanyConfig shape.
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
  return null
}
