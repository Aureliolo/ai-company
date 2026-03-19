<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
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

const steps = computed<StepDef[]>(() => {
  const s: StepDef[] = [
    { id: 'welcome', label: 'Welcome', component: 'welcome' },
  ]
  if (setup.isAdminNeeded) {
    s.push({ id: 'admin', label: 'Admin', component: 'admin' })
  }
  s.push(
    { id: 'provider', label: 'Provider', component: 'provider' },
    { id: 'company', label: 'Company', component: 'company' },
    { id: 'agent', label: 'Agent', component: 'agent' },
  )
  return s
})

const currentStep = computed(() => steps.value[setup.currentStep] ?? steps.value[0])

const needsLogin = computed(
  () =>
    !auth.isAuthenticated &&
    !setup.isAdminNeeded &&
    setup.currentStep > 0,
)

function handleNext() {
  setup.nextStep(steps.value.length)
}

function handleCompanyCreated(companyName: string) {
  createdCompanyName.value = companyName
  setup.nextStep(steps.value.length)
}

function handleAgentComplete(agentName: string, providerName: string) {
  createdAgentName.value = agentName
  createdProviderName.value = providerName
  showComplete.value = true
}

onMounted(async () => {
  await setup.fetchStatus()
  // If setup is already complete, redirect to dashboard.
  if (setup.statusLoaded && !setup.isSetupNeeded) {
    router.replace('/')
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
              class="flex h-8 w-8 items-center justify-center rounded-full text-xs font-medium transition-colors"
              :class="
                index < setup.currentStep
                  ? 'bg-brand-600 text-white'
                  : index === setup.currentStep
                    ? 'border-2 border-brand-600 text-brand-400'
                    : 'border border-slate-700 text-slate-500'
              "
            >
              <i
                v-if="index < setup.currentStep"
                class="pi pi-check text-xs"
              />
              <span v-else>{{ index + 1 }}</span>
            </div>
            <div
              v-if="index < steps.length - 1"
              class="h-px w-8"
              :class="index < setup.currentStep ? 'bg-brand-600' : 'bg-slate-700'"
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
          @next="handleNext"
        />
        <SetupProvider
          v-else-if="currentStep.component === 'provider'"
          @next="handleNext"
        />
        <SetupCompany
          v-else-if="currentStep.component === 'company'"
          @next="handleCompanyCreated"
        />
        <SetupAgent
          v-else-if="currentStep.component === 'agent'"
          @complete="handleAgentComplete"
        />
      </template>
    </div>
  </div>
</template>
