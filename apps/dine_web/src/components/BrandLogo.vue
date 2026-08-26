<script setup lang="ts">
withDefaults(defineProps<{ light?: boolean; compact?: boolean }>(), {
  light: false,
  compact: false,
})
</script>

<template>
  <div class="inline-flex select-none items-center gap-2.5">
    <span
      class="grid size-9 shrink-0 place-items-center rounded-xl"
      :class="light ? 'bg-white/10 ring-1 ring-white/20' : 'bg-brand-900'"
    >
      <svg viewBox="0 0 64 64" class="size-5" aria-hidden="true">
        <path
          d="M20 44c0-10 5-18 12-18s12 8 12 18"
          fill="none"
          stroke="#E3924A"
          stroke-width="5"
          stroke-linecap="round"
        />
        <path
          d="M26 44c0-6 3-11 6-11s6 5 6 11"
          fill="none"
          stroke="#F3CFA5"
          stroke-width="5"
          stroke-linecap="round"
        />
        <circle cx="32" cy="19" r="3.6" fill="#E3924A" />
      </svg>
    </span>
    <span v-if="!compact" class="leading-none">
      <span
        class="block font-display text-lg font-semibold tracking-wide"
        :class="light ? 'text-white' : 'text-brand-900'"
        >AutoDine</span
      >
      <span class="mt-1 block text-[10px] uppercase tracking-[0.24em] text-accent-500">云边协同 · 甜品中枢</span>
    </span>
  </div>
</template>
