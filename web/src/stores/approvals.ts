import { create } from 'zustand'

// eslint-disable-next-line @typescript-eslint/no-empty-object-type
interface ApprovalsState {}

export const useApprovalsStore = create<ApprovalsState>()(() => ({}))
