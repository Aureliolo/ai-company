<script setup lang="ts">
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'

defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  confirm: []
  cancel: []
}>()

function handleConfirm() {
  emit('confirm')
  emit('update:visible', false)
}

function handleCancel() {
  emit('cancel')
  emit('update:visible', false)
}
</script>

<template>
  <Dialog
    :visible="visible"
    header="Enable Advanced Settings"
    modal
    :closable="false"
    class="w-full max-w-md"
    @update:visible="emit('update:visible', $event)"
  >
    <div class="space-y-3">
      <div class="flex items-start gap-3">
        <i class="pi pi-exclamation-triangle mt-0.5 text-xl text-amber-400" aria-hidden="true" />
        <p class="text-sm text-slate-300">
          Advanced settings can affect system stability and security.
          Only modify these if you understand their impact.
        </p>
      </div>
    </div>

    <template #footer>
      <div class="flex justify-end gap-2">
        <Button
          label="Cancel"
          severity="secondary"
          text
          size="small"
          @click="handleCancel"
        />
        <Button
          label="I understand, continue"
          severity="warn"
          size="small"
          @click="handleConfirm"
        />
      </div>
    </template>
  </Dialog>
</template>
