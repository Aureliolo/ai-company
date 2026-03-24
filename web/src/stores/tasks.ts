import { create } from 'zustand'

// eslint-disable-next-line @typescript-eslint/no-empty-object-type
interface TasksState {}

export const useTasksStore = create<TasksState>()(() => ({}))
