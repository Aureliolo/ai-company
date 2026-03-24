import { create } from 'zustand'

// eslint-disable-next-line @typescript-eslint/no-empty-object-type
interface CompanyState {}

export const useCompanyStore = create<CompanyState>()(() => ({}))
