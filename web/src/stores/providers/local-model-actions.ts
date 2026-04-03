import {
  pullModel as apiPullModel,
  deleteModel as apiDeleteModel,
  updateModelConfig as apiUpdateModelConfig,
} from '@/api/endpoints/providers'
import { getErrorMessage } from '@/utils/errors'
import type { LocalModelParams } from '@/api/types'
import { useToastStore } from '@/stores/toast'
import type { ProvidersSet, ProvidersGet } from './types'

let _pullAbortController: AbortController | null = null

export function createLocalModelActions(set: ProvidersSet, get: ProvidersGet) {
  return {
    pullModel: async (name: string, modelName: string) => {
      _pullAbortController?.abort()
      const controller = new AbortController()
      _pullAbortController = controller
      set({ pullingModel: true, pullProgress: null })
      let lastError: string | null = null
      try {
        await apiPullModel(
          name,
          modelName,
          (event) => {
            if (controller.signal.aborted) return
            if (event.error) lastError = event.error
            set({ pullProgress: event })
          },
          controller.signal,
        )
        if (lastError) {
          useToastStore.getState().add({
            variant: 'error',
            title: 'Model pull failed',
            description: lastError,
          })
          return false
        }
        useToastStore.getState().add({
          variant: 'success',
          title: `Model "${modelName}" pulled successfully`,
        })
        await get().fetchProviders()
        const detail = get().selectedProvider
        if (detail?.name === name) {
          await get().fetchProviderDetail(name)
        }
        return true
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          useToastStore.getState().add({
            variant: 'error',
            title: 'Model pull failed',
            description: getErrorMessage(err),
          })
        }
        return false
      } finally {
        if (_pullAbortController === controller) {
          _pullAbortController = null
          set({ pullingModel: false })
        }
      }
    },

    cancelPull: () => {
      _pullAbortController?.abort()
      _pullAbortController = null
      set({ pullingModel: false, pullProgress: null })
    },

    deleteModel: async (name: string, modelId: string) => {
      set({ deletingModel: true })
      try {
        await apiDeleteModel(name, modelId)
        useToastStore.getState().add({
          variant: 'success',
          title: `Model "${modelId}" deleted`,
        })
        await get().fetchProviders()
        const detail = get().selectedProvider
        if (detail?.name === name) {
          await get().fetchProviderDetail(name)
        }
        return true
      } catch (err) {
        useToastStore.getState().add({
          variant: 'error',
          title: 'Failed to delete model',
          description: getErrorMessage(err),
        })
        return false
      } finally {
        set({ deletingModel: false })
      }
    },

    updateModelConfig: async (name: string, modelId: string, params: LocalModelParams) => {
      try {
        await apiUpdateModelConfig(name, modelId, params)
        useToastStore.getState().add({
          variant: 'success',
          title: `Model "${modelId}" config updated`,
        })
        const detail = get().selectedProvider
        if (detail?.name === name) {
          await get().fetchProviderDetail(name)
        }
        return true
      } catch (err) {
        useToastStore.getState().add({
          variant: 'error',
          title: 'Failed to update model config',
          description: getErrorMessage(err),
        })
        return false
      }
    },
  }
}
