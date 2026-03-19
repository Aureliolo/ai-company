/**
 * Shared PrimeVue component mocks for settings tests.
 *
 * All mocks include interactive behavior (event emission) so tests can
 * simulate user input uniformly across all test files.
 */

export const InputTextMock = {
  props: ['modelValue', 'type', 'placeholder', 'disabled'],
  emits: ['update:modelValue'],
  template: '<input :type="type" :value="modelValue" :disabled="disabled" @input="$emit(\'update:modelValue\', $event.target.value)" />',
}

export const InputNumberMock = {
  props: ['modelValue', 'min', 'max', 'minFractionDigits', 'maxFractionDigits', 'useGrouping', 'disabled'],
  emits: ['update:modelValue'],
  template: '<input type="number" :value="modelValue" :disabled="disabled" @input="$emit(\'update:modelValue\', Number($event.target.value))" />',
}

export const ToggleSwitchMock = {
  props: ['modelValue', 'disabled', 'ariaLabel'],
  emits: ['update:modelValue'],
  template: '<button role="switch" :aria-checked="modelValue" :aria-label="ariaLabel" :disabled="disabled" @click="$emit(\'update:modelValue\', !modelValue)">{{ modelValue }}</button>',
}

export const SelectMock = {
  props: ['modelValue', 'options', 'disabled'],
  emits: ['update:modelValue'],
  template: '<select :value="modelValue" :disabled="disabled" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-for="o in options" :key="o" :value="o">{{ o }}</option></select>',
}

export const TextareaMock = {
  props: ['modelValue', 'rows', 'disabled'],
  emits: ['update:modelValue'],
  template: '<textarea :value="modelValue" :disabled="disabled" @input="$emit(\'update:modelValue\', $event.target.value)"></textarea>',
}

export const ButtonMock = {
  props: ['label', 'icon', 'size', 'severity', 'text', 'disabled', 'loading', 'type', 'ariaLabel'],
  template: '<button :disabled="disabled" :type="type || \'button\'">{{ label }}</button>',
}

export const TagMock = {
  props: ['value', 'severity'],
  template: '<span :data-severity="severity">{{ value }}</span>',
}

/**
 * Note: vi.mock() factories are hoisted above imports by Vitest, so these
 * exports cannot be used via a registerPrimeVueMocks() helper function.
 * Instead, copy the vi.mock() calls directly into each test file that needs
 * them, using the mock objects above as a reference for consistent behavior.
 */
