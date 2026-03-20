<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useSetupStore } from '@/stores/setup'
import SetupWelcome from '@/components/setup/SetupWelcome.vue'
import SetupAdmin from '@/components/setup/SetupAdmin.vue'
import SetupProvider from '@/components/setup/SetupProvider.vue'
import SetupCompany from '@/components/setup/SetupCompany.vue'
import SetupAgent from '@/components/setup/SetupAgent.vue'
import SetupComplete from '@/components/setup/SetupComplete.vue'

const router = useRouter()
const auth = useAuthStore()
const setup = useSetupStore()

// Track created resources for the completion screen
const createdCompanyName = ref('')
const createdAgentName = ref('')
const createdProviderName = ref('')

// Whether we are showing the final "complete" screen (not part of the step flow)
const showComplete = ref(false)

interface StepDef {
  id: string
  label: string
  component: 'welcome' | 'admin' | 'provider' | 'company' | 'agent'
}

// Always show all 5 steps -- admin never disappears. Step indices stay
// consistent across refreshes so navigation doesn't break.
const steps = computed<StepDef[]>(() => [
  { id: 'welcome', label: 'Welcome', component: 'welcome' },
  { id: 'admin', label: 'Admin', component: 'admin' },
  { id: 'provider', label: 'Provider', component: 'provider' },
  { id: 'company', label: 'Company', component: 'company' },
  { id: 'agent', label: 'Agent', component: 'agent' },
])

const currentStep = computed(() => steps.value[setup.currentStep] ?? steps.value[0])

const needsLogin = computed(
  () =>
    !auth.isAuthenticated &&
    !setup.isAdminNeeded &&
    setup.currentStep > 0,
)

/** Whether a step indicator shows as completed (checkmark). */
function isStepDone(index: number): boolean {
  const step = steps.value[index]
  if (!step) return false
  return setup.isStepComplete(step.id)
}

function handleNext() {
  // Mark current step's welcome as done when advancing from it.
  if (setup.currentStep === 0) {
    setup.markStepComplete('welcome')
  }
  setup.nextStep(steps.value.length)
}

function handlePrevious() {
  setup.prevStep()
}

function handleStepClick(index: number) {
  if (isStepDone(index) || index === setup.currentStep) {
    setup.setStep(index, steps.value.length)
  }
}

async function handleAdminComplete() {
  await setup.fetchStatus()
  if (setup.statusLoaded) {
    setup.nextStep(steps.value.length)
  }
}

async function handleProviderComplete() {
  await setup.fetchStatus()
  if (setup.statusLoaded) {
    setup.nextStep(steps.value.length)
  }
}

async function handleCompanyCreated(companyName: string) {
  createdCompanyName.value = companyName
  await setup.fetchStatus()
  if (setup.statusLoaded) {
    setup.nextStep(steps.value.length)
  }
}

async function handleAgentComplete(agentName: string, providerName: string) {
  createdAgentName.value = agentName
  createdProviderName.value = providerName
  await setup.fetchStatus()
  if (setup.statusLoaded) {
    showComplete.value = true
  }
}

/**
 * Compute the correct step to resume at based on the setup status.
 * Uses backend-reported completion state to skip already-done steps.
 * Step indices are now stable (always 0-4).
 */
function computeResumeStep(): number {
  const status = setup.status
  if (!status) return 0

  // On fresh setup (admin not yet created), start at Welcome (0).
  // Only resume past Welcome if the user has already started the flow
  // (at least one step is complete).
  if (status.needs_admin) return 0

  // Admin is done -- resume at the first incomplete step.
  if (!status.has_providers) return 2 // Provider step
  if (!status.has_company) return 3 // Company step
  if (!status.has_agents) return 4 // Agent step

  // Everything is done -- shouldn't be here (redirect handles this).
  return 0
}

onMounted(async () => {
  await setup.fetchStatus()
  // If setup is already complete, redirect to dashboard.
  if (setup.statusLoaded && !setup.isSetupNeeded) {
    router.replace('/')
    return
  }
  // Resume at the correct step based on what is already completed.
  if (setup.statusLoaded && setup.isSetupNeeded) {
    const resumeStep = computeResumeStep()
    if (resumeStep > 0) {
      setup.setStep(resumeStep, steps.value.length)
    }
  }
})
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-slate-950 p-4">
    <div class="w-full max-w-2xl">
      <!-- Loading state -->
      <div v-if="setup.loading && !setup.status" class="text-center">
        <i class="pi pi-spin pi-spinner text-2xl text-slate-400" />
        <p class="mt-2 text-sm text-slate-400">Loading setup status...</p>
      </div>

      <!-- Setup error -->
      <div
        v-else-if="setup.error && !setup.status"
        role="alert"
        class="rounded bg-red-500/10 p-4 text-center text-sm text-red-400"
      >
        {{ setup.error }}
      </div>

      <!-- Needs login message -->
      <div v-else-if="needsLogin" class="text-center">
        <i class="pi pi-lock mb-4 text-3xl text-slate-500" />
        <h2 class="mb-2 text-xl font-semibold text-slate-100">Authentication Required</h2>
        <p class="mb-4 text-sm text-slate-400">
          Please log in with your admin account to continue setup.
        </p>
        <RouterLink
          to="/login"
          class="text-sm text-brand-400 hover:text-brand-300"
        >
          Go to Login
        </RouterLink>
      </div>

      <!-- Complete screen -->
      <template v-else-if="showComplete">
        <SetupComplete
          :company-name="createdCompanyName"
          :agent-name="createdAgentName"
          :provider-name="createdProviderName"
        />
      </template>

      <!-- Wizard flow -->
      <template v-else-if="setup.status">
        <!-- Step indicator -->
        <div class="mb-8 flex items-center justify-center gap-2">
          <template v-for="(step, index) in steps" :key="step.id">
            <div
              data-testid="step-indicator"
              class="flex h-8 w-8 items-center justify-center rounded-full text-xs font-medium transition-colors"
              :class="[
                index === setup.currentStep
                  ? 'border-2 border-brand-600 text-brand-400'
                  : isStepDone(index)
                    ? 'bg-brand-600 text-white cursor-pointer hover:bg-brand-500'
                    : 'border border-slate-700 text-slate-500',
              ]"
              :role="isStepDone(index) || index === setup.currentStep ? 'button' : undefined"
              :tabindex="isStepDone(index) || index === setup.currentStep ? 0 : undefined"
              :title="isStepDone(index) && index !== setup.currentStep ? `Go back to ${step.label}` : step.label"
              @click="handleStepClick(index)"
              @keydown.enter="handleStepClick(index)"
              @keydown.space.prevent="handleStepClick(index)"
            >
              <span>{{ index + 1 }}</span>
            </div>
            <div
              v-if="index < steps.length - 1"
              class="h-px w-8"
              :class="isStepDone(index) ? 'bg-brand-600' : 'bg-slate-700'"
            />
          </template>
        </div>

        <!-- Step labels -->
        <div class="mb-8 flex justify-center">
          <span class="text-xs text-slate-500">
            Step {{ setup.currentStep + 1 }} of {{ steps.length }}
            -- {{ currentStep.label }}
          </span>
        </div>

        <!-- Step content -->
        <SetupWelcome
          v-if="currentStep.component === 'welcome'"
          @next="handleNext"
        />
        <SetupAdmin
          v-else-if="currentStep.component === 'admin'"
          @next="handleAdminComplete"
          @previous="handlePrevious"
        />
        <SetupProvider
          v-else-if="currentStep.component === 'provider'"
          @next="handleProviderComplete"
          @previous="handlePrevious"
        />
        <SetupCompany
          v-else-if="currentStep.component === 'company'"
          @next="handleCompanyCreated"
          @previous="handlePrevious"
        />
        <SetupAgent
          v-else-if="currentStep.component === 'agent'"
          @complete="handleAgentComplete"
          @previous="handlePrevious"
        />
      </template>
    </div>
  </div>
</template>
