<script setup lang="ts">
import { computed } from 'vue'

export interface BarDatum {
  label: string
  value: number
  color?: string
}

const props = withDefaults(
  defineProps<{
    data: BarDatum[]
    color?: string
    height?: number
    valueFormat?: (v: number) => string
  }>(),
  { color: '#3b729c', height: 180, valueFormat: (v: number) => String(v) },
)

const max = computed(() => Math.max(1, ...props.data.map((d) => d.value)))

function barHeight(value: number): string {
  return `${Math.max(2, (value / max.value) * (props.height - 28))}px`
}
</script>

<template>
  <div class="flex items-end justify-between gap-1.5" :style="{ height: `${height}px` }">
    <div
      v-for="(d, i) in data"
      :key="i"
      class="group flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-1"
    >
      <span
        class="rounded bg-ink-900/70 px-1 py-0.5 text-[10px] font-medium text-white tabular-nums opacity-0 transition-opacity group-hover:opacity-100"
      >
        {{ valueFormat(d.value) }}
      </span>
      <div
        class="w-full max-w-7 rounded-t-md transition-all duration-300 group-hover:brightness-110"
        :style="{ height: barHeight(d.value), background: d.color ?? color }"
      />
      <span class="text-[10px] text-ink-300 tabular-nums">{{ d.label }}</span>
    </div>
  </div>
</template>
