import { create } from 'zustand'

// eslint-disable-next-line @typescript-eslint/no-empty-object-type
interface AnalyticsState {}

export const useAnalyticsStore = create<AnalyticsState>()(() => ({}))
