import { create } from 'zustand'

// eslint-disable-next-line @typescript-eslint/no-empty-object-type
interface MessagesState {}

export const useMessagesStore = create<MessagesState>()(() => ({}))
