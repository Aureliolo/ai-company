import { create } from 'zustand'
import type { SinkInfo, TestSinkResult } from '@/api/types'
import { getNamespaceSettings, listSinks, testSinkConfig, updateSetting } from '@/api/endpoints/settings'

interface SinksState {
  sinks: SinkInfo[]
  loading: boolean
  error: string | null
  fetchSinks: () => Promise<void>
  saveSink: (sink: SinkInfo) => Promise<void>
  testConfig: (data: { sink_overrides: string; custom_sinks: string }) => Promise<TestSinkResult>
}

function buildOverrideForSink(sink: SinkInfo): Record<string, unknown> {
  const override: Record<string, unknown> = { level: sink.level, json_format: sink.json_format, enabled: sink.enabled }
  if (sink.rotation) {
    override.rotation = { strategy: sink.rotation.strategy, max_bytes: sink.rotation.max_bytes, backup_count: sink.rotation.backup_count }
  }
  return override
}

export const useSinksStore = create<SinksState>((set, get) => ({
  sinks: [],
  loading: false,
  error: null,

  fetchSinks: async () => {
    set({ loading: true, error: null })
    try {
      const sinks = await listSinks()
      set({ sinks, loading: false })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load sinks'
      set({ error: message, loading: false })
    }
  },

  saveSink: async (sink) => {
    set({ error: null })
    try {
      if (sink.is_default) {
        const overrides: Record<string, unknown> = {}
        overrides[sink.identifier] = buildOverrideForSink(sink)
        await updateSetting('observability', 'sink_overrides', { value: JSON.stringify(overrides) })
      } else {
        const custom: Record<string, unknown> = { file_path: sink.identifier, ...buildOverrideForSink(sink) }
        if (sink.routing_prefixes.length > 0) {
          custom.routing_prefixes = [...sink.routing_prefixes]
        }
        // Merge with existing custom sinks instead of overwriting
        let existing: Record<string, unknown>[] = []
        try {
          const settings = await getNamespaceSettings('observability')
          const entry = settings.find((s) => s.definition.key === 'custom_sinks')
          if (entry?.value) {
            const parsed: unknown = JSON.parse(entry.value)
            if (Array.isArray(parsed)) existing = parsed as Record<string, unknown>[]
          }
        } catch { /* proceed with empty */ }
        const merged = existing.filter((s) => s.file_path !== sink.identifier)
        merged.push(custom)
        await updateSetting('observability', 'custom_sinks', { value: JSON.stringify(merged) })
      }
      await get().fetchSinks()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to save sink'
      set({ error: message })
      throw err
    }
  },

  testConfig: async (data) => {
    try {
      return await testSinkConfig(data)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Test request failed'
      set({ error: message })
      throw err
    }
  },
}))
