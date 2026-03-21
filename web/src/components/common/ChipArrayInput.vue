<script setup lang="ts">
import { ref } from 'vue'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import Tag from 'primevue/tag'

const props = withDefaults(
  defineProps<{
    modelValue: string[]
    placeholder?: string
    disabled?: boolean
  }>(),
  { placeholder: 'Add item...', disabled: false },
)

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

const inputValue = ref('')

function addItem() {
  const trimmed = inputValue.value.trim()
  if (!trimmed || props.modelValue.includes(trimmed)) return
  emit('update:modelValue', [...props.modelValue, trimmed])
  inputValue.value = ''
}

function removeItem(index: number) {
  const updated = props.modelValue.filter((_, i) => i !== index)
  emit('update:modelValue', updated)
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter') {
    event.preventDefault()
    addItem()
  } else if (
    event.key === 'Backspace' &&
    inputValue.value === '' &&
    props.modelValue.length > 0
  ) {
    removeItem(props.modelValue.length - 1)
  }
}
</script>

<template>
  <div>
    <!-- Chip display -->
    <div v-if="modelValue.length > 0" class="mb-2 flex flex-wrap gap-1.5">
      <Tag
        v-for="(item, index) in modelValue"
        :key="item"
        severity="info"
        class="cursor-default"
      >
        <span class="text-xs">{{ item }}</span>
        <button
          v-if="!disabled"
          type="button"
          class="ml-1.5 text-xs opacity-60 hover:opacity-100"
          :aria-label="`Remove ${item}`"
          @click="removeItem(index)"
        >
          <i class="pi pi-times text-[0.625rem]" aria-hidden="true" />
        </button>
      </Tag>
    </div>

    <!-- Add input -->
    <div v-if="!disabled" class="flex gap-2">
      <InputText
        v-model="inputValue"
        :placeholder="placeholder"
        class="flex-1"
        size="small"
        @keydown="handleKeydown"
      />
      <Button
        label="Add"
        size="small"
        severity="secondary"
        :disabled="!inputValue.trim()"
        @click="addItem"
      />
    </div>
  </div>
</template>
