import { create } from 'zustand'

// eslint-disable-next-line @typescript-eslint/no-empty-object-type
interface ProvidersState {}

export const useProvidersStore = create<ProvidersState>()(() => ({}))
