<script setup lang="ts">
import { computed } from 'vue'

export interface DonutSegment {
  label: string
  value: number
  color: string
}

const props = withDefaults(
  defineProps<{
    segments: DonutSegment[]
    size?: number
    thickness?: number
    centerValue?: string
    centerLabel?: string
  }>(),
  { size: 168, thickness: 14, centerValue: '', centerLabel: '' },
)

const total = computed(() => props.segments.reduce((s, x) => s + x.value, 0))

// viewBox 100×100，r=40
const R = 40
const CIRC = 2 * Math.PI * R

const arcs = computed(() => {
  let acc = 0
  return props.segments.map((s) => {
    const start = acc
    acc += s.value
    const dash = (s.value / Math.max(1, total.value)) * CIRC
    return {
      ...s,
      dash,
      offset: -(start / Math.max(1, total.value)) * CIRC,
    }
  })
})
</script>

<template>
  <div class="flex items-center gap-6">
    <svg :width="size" :height="size" viewBox="0 0 100 100" class="shrink-0" role="img" aria-label="品类构成">
      <circle cx="50" cy="50" :r="R" fill="none" stroke="#f0eee8" :stroke-width="thickness" />
      <circle
        v-for="a in arcs"
        :key="a.label"
        cx="50"
        cy="50"
        :r="R"
        fill="none"
        :stroke="a.color"
        :stroke-width="thickness"
        :stroke-dasharray="`${a.dash} ${CIRC}`"
        :stroke-dashoffset="a.offset"
        transform="rotate(-90 50 50)"
      />
      <text v-if="centerValue" x="50" y="47" text-anchor="middle" class="fill-ink-900" style="font-size: 16px; font-weight: 600">
        {{ centerValue }}
      </text>
      <text v-if="centerLabel" x="50" y="61" text-anchor="middle" class="fill-ink-300" style="font-size: 9px">
        {{ centerLabel }}
      </text>
    </svg>
    <ul class="min-w-0 flex-1 space-y-2.5">
      <li v-for="s in segments" :key="s.label" class="flex items-center gap-2.5 text-sm">
        <span class="size-2.5 shrink-0 rounded-sm" :style="{ background: s.color }" />
        <span class="truncate text-ink-700">{{ s.label }}</span>
        <span class="ml-auto shrink-0 text-ink-400 tabular-nums">
          {{ total > 0 ? Math.round((s.value / total) * 100) : 0 }}%
        </span>
      </li>
    </ul>
  </div>
</template>
