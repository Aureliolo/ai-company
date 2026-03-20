<script setup lang="ts">
import { ref, computed } from 'vue'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import { useAuthStore } from '@/stores/auth'
import { useSetupStore } from '@/stores/setup'
import { getErrorMessage } from '@/utils/errors'
import { useLoginLockout } from '@/composables/useLoginLockout'

const emit = defineEmits<{
  next: []
  previous: []
}>()

const auth = useAuthStore()
const setupStore = useSetupStore()
const { locked, checkAndClearLockout, recordFailure } = useLoginLockout()

const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const showPassword = ref(false)
const showConfirmPassword = ref(false)
const error = ref<string | null>(null)

/** Whether the admin step has already been completed (reactive). */
const isComplete = computed(() => setupStore.isStepComplete('admin'))

async function handleSetup() {
  if (checkAndClearLockout()) {
    error.value = 'Too many failed attempts. Please wait before trying again.'
    return
  }
  error.value = null
  if (password.value !== confirmPassword.value) {
    error.value = 'Passwords do not match'
    return
  }
  if (password.value.length < setupStore.minPasswordLength) {
    error.value = `Password must be at least ${setupStore.minPasswordLength} characters`
    return
  }
  try {
    await auth.setup(username.value, password.value)
    emit('next')
  } catch (err) {
    const lockoutMsg = recordFailure(err)
    if (lockoutMsg) {
      error.value = lockoutMsg
      return
    }
    error.value = getErrorMessage(err)
  }
}
</script>

<template>
  <div class="mx-auto w-full max-w-sm">
    <!-- Completed state: read-only summary -->
    <template v-if="isComplete">
      <div class="mb-6 text-center">
        <h2 class="text-2xl font-semibold text-slate-100">Create Admin Account</h2>
        <p class="mt-1 text-sm text-slate-400">
          Admin account has been created.
        </p>
      </div>
      <div class="rounded-lg border border-green-500/20 bg-green-500/10 p-4 text-center">
        <i class="pi pi-check-circle mb-2 text-2xl text-green-400" />
        <p class="text-sm text-green-300">
          Admin account created. You can change the password later in Settings.
        </p>
      </div>
      <div class="mt-8 flex items-center gap-3">
        <Button
          type="button"
          label="Back"
          icon="pi pi-arrow-left"
          severity="secondary"
          outlined
          @click="emit('previous')"
        />
        <Button
          label="Next"
          icon="pi pi-arrow-right"
          icon-pos="right"
          class="flex-1"
          @click="emit('next')"
        />
      </div>
    </template>

    <!-- Creation form -->
    <template v-else>
      <div class="mb-6 text-center">
        <h2 class="text-2xl font-semibold text-slate-100">Create Admin Account</h2>
        <p class="mt-1 text-sm text-slate-400">
          Set up the first admin (CEO) account for your organization.
        </p>
      </div>

      <form class="space-y-4" @submit.prevent="handleSetup">
        <div>
          <label for="setup-username" class="mb-1 block text-sm text-slate-300">Username</label>
          <InputText
            id="setup-username"
            v-model="username"
            name="username"
            class="w-full"
            placeholder="Admin username"
            autocomplete="username"
            :aria-describedby="error ? 'setup-error' : undefined"
          />
        </div>
        <div>
          <label for="setup-password" class="mb-1 block text-sm text-slate-300">Password</label>
          <div class="relative">
            <InputText
              id="setup-password"
              v-model="password"
              name="new-password"
              :type="showPassword ? 'text' : 'password'"
              class="w-full pr-10"
              :placeholder="`Min ${setupStore.minPasswordLength} characters`"
              autocomplete="new-password"
              :aria-describedby="error ? 'setup-error' : undefined"
            />
            <button
              type="button"
              class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200"
              :title="showPassword ? 'Hide password' : 'Show password'"
              :aria-label="showPassword ? 'Hide password' : 'Show password'"
              @click="showPassword = !showPassword"
            >
              <i :class="showPassword ? 'pi pi-eye-slash' : 'pi pi-eye'" />
            </button>
          </div>
        </div>
        <div>
          <label for="setup-confirm" class="mb-1 block text-sm text-slate-300">
            Confirm Password
          </label>
          <div class="relative">
            <InputText
              id="setup-confirm"
              v-model="confirmPassword"
              name="confirm-password"
              :type="showConfirmPassword ? 'text' : 'password'"
              class="w-full pr-10"
              placeholder="Re-enter password"
              autocomplete="new-password"
              :aria-describedby="error ? 'setup-error' : undefined"
            />
            <button
              type="button"
              class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200"
              :title="showConfirmPassword ? 'Hide confirm password' : 'Show confirm password'"
              :aria-label="showConfirmPassword ? 'Hide confirm password' : 'Show confirm password'"
              @click="showConfirmPassword = !showConfirmPassword"
            >
              <i :class="showConfirmPassword ? 'pi pi-eye-slash' : 'pi pi-eye'" />
            </button>
          </div>
        </div>

        <div
          v-if="error"
          id="setup-error"
          role="alert"
          class="rounded bg-red-500/10 p-3 text-sm text-red-400"
        >
          {{ error }}
        </div>

        <div class="flex items-center gap-3">
          <Button
            type="button"
            label="Back"
            icon="pi pi-arrow-left"
            severity="secondary"
            outlined
            :disabled="auth.loading || locked"
            @click="emit('previous')"
          />
          <Button
            type="submit"
            label="Create Admin Account"
            icon="pi pi-check"
            class="flex-1"
            :loading="auth.loading"
            :disabled="!username || !password || !confirmPassword || locked"
          />
        </div>
      </form>
    </template>
  </div>
</template>
