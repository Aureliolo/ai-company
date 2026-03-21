import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as setupApi from '@/api/endpoints/setup'
import { getErrorMessage } from '@/utils/errors'
import { MIN_PASSWORD_LENGTH } from '@/utils/constants'
import type { SetupStatusResponse, TemplateInfoResponse } from '@/api/types'

export const useSetupStore = defineStore('setup', () => {
  const status = ref<SetupStatusResponse | null>(null)
  /** True once fetchStatus has completed successfully at least once. */
  const statusLoaded = ref(false)
  const currentStep = ref(0)
  const templates = ref<TemplateInfoResponse[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  /** Per-step completion state, synced from backend status. */
  const completedSteps = ref<Record<string, boolean>>({
    welcome: false,
    admin: false,
    provider: false,
    company: false,
    agent: false,
  })

  // Fail-closed: if status hasn't loaded, assume setup IS needed.
  const isSetupNeeded = computed(() =>
    statusLoaded.value ? !!status.value?.needs_setup : true,
  )
  const isAdminNeeded = computed(() =>
    statusLoaded.value ? !!status.value?.needs_admin : true,
  )
  const minPasswordLength = computed(() =>
    Math.max(MIN_PASSWORD_LENGTH, status.value?.min_password_length ?? MIN_PASSWORD_LENGTH),
  )

  /** Check whether a step has been completed. */
  function isStepComplete(stepId: string): boolean {
    return completedSteps.value[stepId] ?? false
  }

  /** Sync completion map from the backend status response.
   *
   * Enforces sequential ordering: a step is only marked complete
   * if all prior steps are also complete.  This prevents a stale
   * backend flag (e.g. company from a previous attempt) from
   * lighting up a later step while an earlier one is incomplete.
   */
  function syncCompletionFromStatus(): void {
    if (!status.value) return
    const adminDone = !status.value.needs_admin
    const providerDone = adminDone && status.value.has_providers
    const companyDone = providerDone && status.value.has_company
    const agentDone = companyDone && status.value.has_agents
    completedSteps.value = {
      welcome: currentStep.value > 0,
      admin: adminDone,
      provider: providerDone,
      company: companyDone,
      agent: agentDone,
    }
  }

  /** Mark a single step as complete (immutable update).
   *
   * This bypasses the sequential ordering enforced by
   * ``syncCompletionFromStatus``.  Only use for steps that are
   * completed locally without a backend round-trip (currently
   * only ``'welcome'``).
   */
  function markStepComplete(stepId: string): void {
    completedSteps.value = { ...completedSteps.value, [stepId]: true }
  }

  async function fetchStatus() {
    loading.value = true
    error.value = null
    try {
      status.value = await setupApi.getSetupStatus()
      statusLoaded.value = true
      syncCompletionFromStatus()
    } catch (err) {
      error.value = getErrorMessage(err)
      // statusLoaded stays false -- isSetupNeeded/isAdminNeeded
      // default to true (fail-closed).
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

  function nextStep(maxSteps: number) {
    if (currentStep.value < maxSteps - 1) {
      currentStep.value++
    }
  }

  function prevStep() {
    if (currentStep.value > 0) {
      currentStep.value--
    }
  }

  function setStep(n: number, maxSteps?: number) {
    const upper = maxSteps != null ? maxSteps - 1 : n
    currentStep.value = Math.max(0, Math.min(n, upper))
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
    statusLoaded,
    currentStep,
    completedSteps,
    templates,
    loading,
    error,
    isSetupNeeded,
    isAdminNeeded,
    minPasswordLength,
    isStepComplete,
    markStepComplete,
    syncCompletionFromStatus,
    fetchStatus,
    fetchTemplates,
    nextStep,
    prevStep,
    setStep,
    markComplete,
  }
})
