<script setup lang="ts">
interface Choice {
  id: string
  label: string
}

const props = defineProps<{
  questionId: string
  choices: [Choice, Choice]
  modelValue: string | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

function select(choiceId: string) {
  emit('update:modelValue', choiceId)
}
</script>

<template>
  <div class="binary-choice" role="radiogroup" :aria-labelledby="`question-${questionId}`">
    <button
      v-for="choice in choices"
      :key="choice.id"
      class="choice-card"
      :class="{ selected: modelValue === choice.id }"
      role="radio"
      :aria-checked="modelValue === choice.id"
      @click="select(choice.id)"
    >
      <span class="choice-label">{{ choice.label }}</span>
    </button>
  </div>
</template>

<style scoped>
.binary-choice {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.choice-card {
  padding: 1.5rem;
  border: 2px solid var(--color-border, #e2e8f0);
  border-radius: 0.75rem;
  background: var(--color-bg-card, #ffffff);
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: left;
  font-size: 0.95rem;
  line-height: 1.5;
}

.choice-card:hover {
  border-color: var(--color-primary, #3b82f6);
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.15);
}

.choice-card.selected {
  border-color: var(--color-primary, #3b82f6);
  background: var(--color-primary-light, #eff6ff);
  box-shadow: 0 2px 12px rgba(59, 130, 246, 0.2);
}

.choice-label {
  font-weight: 500;
}

@media (max-width: 640px) {
  .binary-choice {
    grid-template-columns: 1fr;
  }
}
</style>
