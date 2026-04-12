import { create } from 'zustand'
import {
  getTunnelStatus,
  startTunnel as apiStartTunnel,
  stopTunnel as apiStopTunnel,
} from '@/api/endpoints/tunnel'
import { createLogger } from '@/lib/logger'
import { useToastStore } from '@/stores/toast'
import { getErrorMessage } from '@/utils/errors'

const log = createLogger('tunnel-store')

export type TunnelPhase =
  | 'stopped'
  | 'enabling'
  | 'on'
  | 'disabling'
  | 'error'

export interface TunnelState {
  phase: TunnelPhase
  publicUrl: string | null
  error: string | null
  autoStop: boolean

  fetchStatus: () => Promise<void>
  start: () => Promise<void>
  stop: () => Promise<void>
  setAutoStop: (enabled: boolean) => void
  reset: () => void
}

const INITIAL_STATE = {
  phase: 'stopped' as const,
  publicUrl: null,
  error: null,
  autoStop: true,
}

let _operationGeneration = 0

export const useTunnelStore = create<TunnelState>()((set) => ({
  ...INITIAL_STATE,

  fetchStatus: async () => {
    const gen = ++_operationGeneration
    try {
      const status = await getTunnelStatus()
      if (gen !== _operationGeneration) return
      set({
        publicUrl: status.public_url,
        phase: status.public_url ? 'on' : 'stopped',
        error: null,
      })
    } catch (err) {
      if (gen !== _operationGeneration) return
      const message = getErrorMessage(err)
      log.warn('Tunnel status fetch failed:', message)
      set({ phase: 'error', error: message, publicUrl: null })
    }
  },

  start: async () => {
    const gen = ++_operationGeneration
    set({ phase: 'enabling', error: null })
    try {
      const { public_url } = await apiStartTunnel()
      if (gen !== _operationGeneration) return
      set({ phase: 'on', publicUrl: public_url, error: null })
      useToastStore.getState().add({
        variant: 'success',
        title: 'Tunnel started',
        description: public_url,
      })
    } catch (err) {
      if (gen !== _operationGeneration) return
      const message = getErrorMessage(err)
      log.error('Failed to start tunnel:', message)
      set({ phase: 'error', error: message, publicUrl: null })
      useToastStore.getState().add({
        variant: 'error',
        title: 'Failed to start tunnel',
        description: message,
      })
    }
  },

  stop: async () => {
    const gen = ++_operationGeneration
    set({ phase: 'disabling' })
    try {
      await apiStopTunnel()
      if (gen !== _operationGeneration) return
      set({ phase: 'stopped', publicUrl: null, error: null })
      useToastStore.getState().add({
        variant: 'info',
        title: 'Tunnel stopped',
      })
    } catch (err) {
      if (gen !== _operationGeneration) return
      const message = getErrorMessage(err)
      log.error('Failed to stop tunnel:', message)
      set({ phase: 'error', error: message })
      useToastStore.getState().add({
        variant: 'error',
        title: 'Failed to stop tunnel',
        description: message,
      })
    }
  },

  setAutoStop: (enabled: boolean) => set({ autoStop: enabled }),
  reset: () => {
    ++_operationGeneration
    set({ ...INITIAL_STATE })
  },
}))
