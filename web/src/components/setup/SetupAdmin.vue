<script setup lang="ts">
import { ref } from 'vue'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import { useAuthStore } from '@/stores/auth'
import { getErrorMessage } from '@/utils/errors'
import { MIN_PASSWORD_LENGTH } from '@/utils/constants'
import { useLoginLockout } from '@/composables/useLoginLockout'

const emit = defineEmits<{
  next: []
}>()

const auth = useAuthStore()
const { locked, checkAndClearLockout, recordFailure } = useLoginLockout()

const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const error = ref<string | null>(null)

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
  if (password.value.length < MIN_PASSWORD_LENGTH) {
    error.value = `Password must be at least ${MIN_PASSWORD_LENGTH} characters`
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
          class="w-full"
          placeholder="Admin username"
          autocomplete="username"
          :aria-describedby="error ? 'setup-error' : undefined"
        />
      </div>
      <div>
        <label for="setup-password" class="mb-1 block text-sm text-slate-300">Password</label>
        <InputText
          id="setup-password"
          v-model="password"
          type="password"
          class="w-full"
          :placeholder="`Min ${MIN_PASSWORD_LENGTH} characters`"
          autocomplete="new-password"
          :aria-describedby="error ? 'setup-error' : undefined"
        />
      </div>
      <div>
        <label for="setup-confirm" class="mb-1 block text-sm text-slate-300">
          Confirm Password
        </label>
        <InputText
          id="setup-confirm"
          v-model="confirmPassword"
          type="password"
          class="w-full"
          placeholder="Re-enter password"
          autocomplete="new-password"
          :aria-describedby="error ? 'setup-error' : undefined"
        />
      </div>

      <div
        v-if="error"
        id="setup-error"
        role="alert"
        class="rounded bg-red-500/10 p-3 text-sm text-red-400"
      >
        {{ error }}
      </div>

      <Button
        type="submit"
        label="Create Admin Account"
        icon="pi pi-check"
        class="w-full"
        :loading="auth.loading"
        :disabled="!username || !password || !confirmPassword || locked"
      />
    </form>
  </div>
</template>
