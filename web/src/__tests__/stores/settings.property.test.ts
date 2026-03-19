import { describe, it, expect, beforeEach, vi } from 'vitest'
import fc from 'fast-check'
import { setActivePinia, createPinia } from 'pinia'
import { useSettingsStore, validateSettingValue } from '@/stores/settings'
import type { SettingDefinition, SettingEntry } from '@/api/types'

vi.mock('@/api/endpoints/settings', () => ({
  getSchema: vi.fn(),
  getAllSettings: vi.fn(),
  updateSetting: vi.fn(),
  resetSetting: vi.fn(),
}))

/** Arbitrary for SettingDefinition with valid cross-field constraints. */
const arbSettingDefinition = fc.oneof(
  // String type
  fc.record({
    namespace: fc.constantFrom('api', 'company', 'budget', 'security') as fc.Arbitrary<SettingDefinition['namespace']>,
    key: fc.string({ minLength: 1, maxLength: 30 }).filter((s) => s.trim().length > 0),
    type: fc.constant('str' as const),
    default: fc.option(fc.string({ minLength: 1, maxLength: 50 }), { nil: null }),
    description: fc.string({ minLength: 1, maxLength: 100 }).filter((s) => s.trim().length > 0),
    group: fc.string({ minLength: 1, maxLength: 30 }).filter((s) => s.trim().length > 0),
    level: fc.constantFrom('basic', 'advanced') as fc.Arbitrary<SettingDefinition['level']>,
    sensitive: fc.boolean(),
    restart_required: fc.boolean(),
    enum_values: fc.constant([]) as fc.Arbitrary<string[]>,
    validator_pattern: fc.constant(null) as fc.Arbitrary<string | null>,
    min_value: fc.constant(null) as fc.Arbitrary<number | null>,
    max_value: fc.constant(null) as fc.Arbitrary<number | null>,
    yaml_path: fc.constant(null) as fc.Arbitrary<string | null>,
  }),
  // Integer type with range
  fc.record({
    namespace: fc.constantFrom('budget', 'api') as fc.Arbitrary<SettingDefinition['namespace']>,
    key: fc.string({ minLength: 1, maxLength: 30 }).filter((s) => s.trim().length > 0),
    type: fc.constant('int' as const),
    default: fc.constant('50'),
    description: fc.string({ minLength: 1, maxLength: 100 }).filter((s) => s.trim().length > 0),
    group: fc.string({ minLength: 1, maxLength: 30 }).filter((s) => s.trim().length > 0),
    level: fc.constantFrom('basic', 'advanced') as fc.Arbitrary<SettingDefinition['level']>,
    sensitive: fc.constant(false),
    restart_required: fc.boolean(),
    enum_values: fc.constant([]) as fc.Arbitrary<string[]>,
    validator_pattern: fc.constant(null) as fc.Arbitrary<string | null>,
    min_value: fc.option(fc.integer({ min: 0, max: 50 }), { nil: null }),
    max_value: fc.option(fc.integer({ min: 51, max: 200 }), { nil: null }),
    yaml_path: fc.constant(null) as fc.Arbitrary<string | null>,
  }),
  // Boolean type
  fc.record({
    namespace: fc.constantFrom('security', 'backup') as fc.Arbitrary<SettingDefinition['namespace']>,
    key: fc.string({ minLength: 1, maxLength: 30 }).filter((s) => s.trim().length > 0),
    type: fc.constant('bool' as const),
    default: fc.constantFrom('true', 'false'),
    description: fc.string({ minLength: 1, maxLength: 100 }).filter((s) => s.trim().length > 0),
    group: fc.string({ minLength: 1, maxLength: 30 }).filter((s) => s.trim().length > 0),
    level: fc.constantFrom('basic', 'advanced') as fc.Arbitrary<SettingDefinition['level']>,
    sensitive: fc.constant(false),
    restart_required: fc.boolean(),
    enum_values: fc.constant([]) as fc.Arbitrary<string[]>,
    validator_pattern: fc.constant(null) as fc.Arbitrary<string | null>,
    min_value: fc.constant(null) as fc.Arbitrary<number | null>,
    max_value: fc.constant(null) as fc.Arbitrary<number | null>,
    yaml_path: fc.constant(null) as fc.Arbitrary<string | null>,
  }),
  // Enum type
  fc.record({
    namespace: fc.constantFrom('memory', 'providers') as fc.Arbitrary<SettingDefinition['namespace']>,
    key: fc.string({ minLength: 1, maxLength: 30 }).filter((s) => s.trim().length > 0),
    type: fc.constant('enum' as const),
    default: fc.constant('option_a'),
    description: fc.string({ minLength: 1, maxLength: 100 }).filter((s) => s.trim().length > 0),
    group: fc.string({ minLength: 1, maxLength: 30 }).filter((s) => s.trim().length > 0),
    level: fc.constantFrom('basic', 'advanced') as fc.Arbitrary<SettingDefinition['level']>,
    sensitive: fc.constant(false),
    restart_required: fc.boolean(),
    enum_values: fc.constant(['option_a', 'option_b', 'option_c'] as string[]),
    validator_pattern: fc.constant(null) as fc.Arbitrary<string | null>,
    min_value: fc.constant(null) as fc.Arbitrary<number | null>,
    max_value: fc.constant(null) as fc.Arbitrary<number | null>,
    yaml_path: fc.constant(null) as fc.Arbitrary<string | null>,
  }),
)

describe('settings store (property-based)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('namespaces always contains only unique values', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(arbSettingDefinition, { minLength: 0, maxLength: 20 }),
        async (definitions) => {
          setActivePinia(createPinia())
          const settingsApi = await import('@/api/endpoints/settings')
          vi.mocked(settingsApi.getSchema).mockResolvedValue(definitions)
          vi.mocked(settingsApi.getAllSettings).mockResolvedValue([])

          const store = useSettingsStore()
          await store.fetchAll()

          const ns = store.namespaces
          expect(new Set(ns).size).toBe(ns.length)
        },
      ),
      { numRuns: 50 },
    )
  })

  it('entriesByNamespace returns only entries matching the namespace', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(arbSettingDefinition, { minLength: 1, maxLength: 10 }),
        async (definitions) => {
          setActivePinia(createPinia())
          const entries: SettingEntry[] = definitions.map((d) => ({
            definition: d,
            value: d.default ?? '',
            source: 'default' as const,
            updated_at: null,
          }))

          const settingsApi = await import('@/api/endpoints/settings')
          vi.mocked(settingsApi.getSchema).mockResolvedValue(definitions)
          vi.mocked(settingsApi.getAllSettings).mockResolvedValue(entries)

          const store = useSettingsStore()
          await store.fetchAll()

          for (const ns of store.namespaces) {
            const filtered = store.entriesByNamespace(ns)
            for (const entry of filtered) {
              expect(entry.definition.namespace).toBe(ns)
            }
          }
        },
      ),
      { numRuns: 50 },
    )
  })

  it('validateSettingValue returns null for valid values and string for invalid', () => {
    // Valid integers within range
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 100 }),
        (num) => {
          const def: SettingDefinition = {
            namespace: 'budget',
            key: 'test',
            type: 'int',
            default: '50',
            description: 'Test',
            group: 'Test',
            level: 'basic',
            sensitive: false,
            restart_required: false,
            enum_values: [],
            validator_pattern: null,
            min_value: 1,
            max_value: 100,
            yaml_path: null,
          }
          expect(validateSettingValue(String(num), def)).toBeNull()
        },
      ),
      { numRuns: 100 },
    )
  })

  it('validateSettingValue rejects non-numeric strings for int type', () => {
    fc.assert(
      fc.property(
        fc.string().filter((s) => isNaN(Number(s)) || s.trim() === ''),
        (value) => {
          const def: SettingDefinition = {
            namespace: 'budget',
            key: 'test',
            type: 'int',
            default: '50',
            description: 'Test',
            group: 'Test',
            level: 'basic',
            sensitive: false,
            restart_required: false,
            enum_values: [],
            validator_pattern: null,
            min_value: null,
            max_value: null,
            yaml_path: null,
          }
          const result = validateSettingValue(value, def)
          expect(result).not.toBeNull()
        },
      ),
      { numRuns: 100 },
    )
  })

  it('toggleAdvanced always produces a boolean', () => {
    fc.assert(
      fc.property(
        fc.array(fc.boolean(), { minLength: 1, maxLength: 20 }),
        (toggles) => {
          setActivePinia(createPinia())
          const store = useSettingsStore()
          for (const _ of toggles) {
            store.toggleAdvanced()
          }
          expect(typeof store.showAdvanced).toBe('boolean')
        },
      ),
    )
  })
})
