<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string
    value: string
    unit?: string
    delta?: number
    tone?: 'brand' | 'accent' | 'success' | 'danger' | 'warning' | 'ink'
  }>(),
  { unit: '', delta: undefined, tone: 'brand' },
)

const toneClass: Record<string, string> = {
  brand: 'bg-brand-50 text-brand-700',
  accent: 'bg-accent-50 text-accent-600',
  success: 'bg-success-100 text-success-500',
  danger: 'bg-danger-100 text-danger-500',
  warning: 'bg-warning-100 text-warning-500',
  ink: 'bg-ink-900/5 text-ink-700',
}
</script>

<template>
  <div class="card p-5">
    <div class="flex items-center gap-2">
      <span class="size-2 rounded-full" :class="toneClass[tone]" />
      <span class="text-xs font-medium tracking-wide text-ink-400">{{ label }}</span>
    </div>
    <div class="mt-3 flex items-baseline gap-1.5">
      <span class="font-display text-3xl font-semibold text-ink-900 tabular-nums">{{ value }}</span>
      <span v-if="unit" class="text-xs text-ink-400">{{ unit }}</span>
      <span
        v-if="delta !== undefined"
        class="ml-auto rounded-full px-2 py-0.5 text-[11px] font-medium tabular-nums"
        :class="delta >= 0 ? 'bg-success-100 text-success-500' : 'bg-danger-100 text-danger-500'"
      >
        {{ delta >= 0 ? '▲' : '▼' }} {{ Math.abs(delta) }}%
      </span>
    </div>
  </div>
</template>
