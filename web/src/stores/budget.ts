import { create } from 'zustand'

// eslint-disable-next-line @typescript-eslint/no-empty-object-type
interface BudgetState {}

export const useBudgetStore = create<BudgetState>()(() => ({}))
