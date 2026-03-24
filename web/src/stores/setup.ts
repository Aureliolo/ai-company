import { create } from 'zustand'

// eslint-disable-next-line @typescript-eslint/no-empty-object-type
interface SetupState {}

export const useSetupStore = create<SetupState>()(() => ({}))
