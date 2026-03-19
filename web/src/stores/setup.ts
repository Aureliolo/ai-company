import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as setupApi from '@/api/endpoints/setup'
import { getErrorMessage } from '@/utils/errors'
import type { SetupStatusResponse, TemplateInfoResponse } from '@/api/types'

export const useSetupStore = defineStore('setup', () => {
  const status = ref<SetupStatusResponse | null>(null)
  const currentStep = ref(0)
  const templates = ref<TemplateInfoResponse[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const MAX_STEPS = 10

  const isSetupNeeded = computed(() => !!status.value?.needs_setup)
  const isAdminNeeded = computed(() => !!status.value?.needs_admin)

  async function fetchStatus() {
    loading.value = true
    error.value = null
    try {
      status.value = await setupApi.getSetupStatus()
    } catch (err) {
      error.value = getErrorMessage(err)
    } finally {
      loading.value = false
    }
  }

  async function fetchTemplates() {
    error.value = null
    try {
      templates.value = await setupApi.listTemplates()
    } catch (err) {
      error.value = getErrorMessage(err)
    }
  }

  function nextStep() {
    if (currentStep.value < MAX_STEPS) {
      currentStep.value++
    }
  }

  function prevStep() {
    if (currentStep.value > 0) {
      currentStep.value--
    }
  }

  function setStep(n: number) {
    currentStep.value = n
  }

  async function markComplete() {
    loading.value = true
    error.value = null
    try {
      await setupApi.completeSetup()
      if (status.value) {
        status.value = { ...status.value, needs_setup: false }
      }
    } catch (err) {
      error.value = getErrorMessage(err)
      throw err
    } finally {
      loading.value = false
    }
  }

  return {
    status,
    currentStep,
    templates,
    loading,
    error,
    isSetupNeeded,
    isAdminNeeded,
    fetchStatus,
    fetchTemplates,
    nextStep,
    prevStep,
    setStep,
    markComplete,
  }
})
