import { create } from 'zustand'

// eslint-disable-next-line @typescript-eslint/no-empty-object-type
interface MeetingsState {}

export const useMeetingsStore = create<MeetingsState>()(() => ({}))
