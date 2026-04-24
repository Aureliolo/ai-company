import {
  createFromPreset,
  createProvider as apiCreateProvider,
  discoverModels,
  getProvider,
  listPresets,
  listProviders,
  probePreset,
  testConnection,
} from '@/api/endpoints/providers'
import { createLogger } from '@/lib/logger'
import type { ProbePresetResponse, ProviderPreset } from '@/api/types/providers'
import { getErrorMessage } from '@/utils/errors'
import { useToastStore } from '@/stores/toast'
import type { ProvidersSlice, SliceCreator } from './types'

const log = createLogger('setup-wizard:providers')

interface ProbeOutcome {
  results: Record<string, ProbePresetResponse>
  errors: Record<string, string>
}

async function runProbeAll(
  presets: readonly ProviderPreset[],
  label: string,
): Promise<ProbeOutcome> {
  const entries = await Promise.allSettled(
    presets.map(async (preset) => {
      const result = await probePreset(preset.name)
      return { name: preset.name, result }
    }),
  )
  const results: Record<string, ProbePresetResponse> = {}
  const errors: Record<string, string> = {}
  entries.forEach((entry, i) => {
    const preset = presets[i]
    if (!preset) return
    if (entry.status === 'fulfilled') {
      results[entry.value.name] = entry.value.result
    } else {
      const message = getErrorMessage(entry.reason)
      log.error(`${label} failed for ${preset.name}:`, message)
      errors[preset.name] = message
    }
  })
  return { results, errors }
}

export const createProvidersSlice: SliceCreator<ProvidersSlice> = (set, get) => ({
  providers: {},
  presets: [],
  presetsLoading: false,
  presetsError: null,
  probeResults: {},
  probeErrors: {},
  probeGlobalError: null,
  probing: false,
  providersLoading: false,
  providersError: null,

  async fetchProviders() {
    set({ providersLoading: true, providersError: null })
    try {
      const providers = await listProviders()
      set({ providers, providersLoading: false })
    } catch (err) {
      log.error('fetchProviders failed:', getErrorMessage(err))
      set({ providersError: getErrorMessage(err), providersLoading: false })
    }
  },

  async fetchPresets() {
    set({ presetsLoading: true, presetsError: null })
    try {
      const presets = await listPresets()
      set({ presets, presetsLoading: false })
    } catch (err) {
      log.error('fetchPresets failed:', getErrorMessage(err))
      set({ presetsError: getErrorMessage(err), presetsLoading: false })
    }
  },

  async createProviderFromPreset(presetName, name, apiKey, baseUrl) {
    set({ providersError: null })
    try {
      const provider = await createFromPreset({
        preset_name: presetName,
        name,
        api_key: apiKey,
        base_url: baseUrl,
      })
      set((s) => ({ providers: { ...s.providers, [name]: provider } }))

      if (provider.models.length === 0) {
        try {
          await discoverModels(name, presetName)
          const refreshed = await getProvider(name)
          set((s) => ({ providers: { ...s.providers, [name]: refreshed } }))
          if (refreshed.models.length === 0) {
            set({
              providersError:
                `Provider '${name}' created but no models were discovered. ` +
                'Ensure the provider is running with models available, then refresh.',
            })
          }
        } catch (discoveryErr) {
          const msg = getErrorMessage(discoveryErr)
          log.error('Model discovery failed for', name, msg)
          set({
            providersError:
              `Provider '${name}' created but model discovery failed: ${msg}. ` +
              'Ensure the provider is running, then refresh the providers list.',
          })
        }
      }
    } catch (err) {
      log.error('createProviderFromPreset failed:', getErrorMessage(err))
      set({ providersError: getErrorMessage(err) })
      throw err
    }
  },

  async createProviderFromPresetFull(data) {
    set({ providersError: null })
    try {
      const provider = await createFromPreset(data)
      set((s) => ({ providers: { ...s.providers, [data.name]: provider } }))

      if (provider.models.length === 0) {
        try {
          await discoverModels(data.name, data.preset_name)
          const refreshed = await getProvider(data.name)
          set((s) => ({ providers: { ...s.providers, [data.name]: refreshed } }))
          if (refreshed.models.length === 0) {
            set({
              providersError:
                `Provider '${data.name}' created but no models were discovered. ` +
                'Ensure the provider is running with models available, then refresh.',
            })
          }
          return refreshed
        } catch (discoveryErr) {
          const msg = getErrorMessage(discoveryErr)
          log.error('Model discovery failed for', data.name, msg)
          set({
            providersError:
              `Provider '${data.name}' created but model discovery failed: ${msg}. ` +
              'Ensure the provider is running, then refresh.',
          })
        }
      }
      return provider
    } catch (err) {
      log.error('createProviderFromPresetFull failed:', getErrorMessage(err))
      set({ providersError: getErrorMessage(err) })
      return null
    }
  },

  async createProviderCustom(data) {
    set({ providersError: null })
    try {
      const provider = await apiCreateProvider(data)
      set((s) => ({ providers: { ...s.providers, [data.name]: provider } }))
      return provider
    } catch (err) {
      log.error('createProviderCustom failed:', getErrorMessage(err))
      set({ providersError: getErrorMessage(err) })
      return null
    }
  },

  async testProviderConnection(name) {
    set({ providersError: null })
    try {
      return await testConnection(name)
    } catch (err) {
      log.error('testProviderConnection failed:', getErrorMessage(err))
      set({ providersError: getErrorMessage(err) })
      throw err
    }
  },

  async probeAllPresets() {
    const { presets } = get()
    set({ probing: true, probeErrors: {}, probeGlobalError: null })
    try {
      const { results, errors } = await runProbeAll(presets, 'probe')
      set({ probeResults: results, probeErrors: errors })
      if (Object.keys(errors).length > 0) {
        const failedCount = Object.keys(errors).length
        useToastStore.getState().add({
          variant: 'warning',
          title: `Provider probe failed for ${failedCount} preset${failedCount === 1 ? '' : 's'}`,
          description: 'See the Providers step for retry options or skip to configure manually.',
        })
      }
    } catch (err) {
      const message = getErrorMessage(err)
      log.error('probeAllPresets failed:', message)
      set({ probeGlobalError: message })
      useToastStore.getState().add({
        variant: 'error',
        title: 'Provider probe failed',
        description: message,
      })
    } finally {
      set({ probing: false })
    }
  },

  async reprobePresets() {
    set({ probeResults: {}, probeErrors: {}, probeGlobalError: null, probing: true })
    try {
      const { presets } = get()
      const { results, errors } = await runProbeAll(presets, 'reprobe')
      set({ probeResults: results, probeErrors: errors })
      if (Object.keys(errors).length > 0) {
        const failedCount = Object.keys(errors).length
        useToastStore.getState().add({
          variant: 'warning',
          title: `Re-probe failed for ${failedCount} preset${failedCount === 1 ? '' : 's'}`,
          description: 'See the Providers step for retry options or skip to configure manually.',
        })
      }
    } catch (err) {
      const message = getErrorMessage(err)
      log.error('reprobePresets failed:', message)
      set({ probeGlobalError: message })
      useToastStore.getState().add({
        variant: 'error',
        title: 'Provider re-probe failed',
        description: message,
      })
    } finally {
      set({ probing: false })
    }
  },
})
