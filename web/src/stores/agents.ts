import { create } from 'zustand'

// eslint-disable-next-line @typescript-eslint/no-empty-object-type
interface AgentsState {}

export const useAgentsStore = create<AgentsState>()(() => ({}))
