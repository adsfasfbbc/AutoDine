<script setup lang="ts">
import { ref } from 'vue'

const props = withDefaults(defineProps<{ src?: string; alt: string; rounded?: string }>(), {
  src: undefined,
  rounded: 'rounded-2xl',
})

const failed = ref(false)
function onError(): void {
  failed.value = true
}
</script>

<template>
  <div
    class="relative grid place-items-center overflow-hidden bg-gradient-to-br from-brand-100 via-paper to-accent-100"
    :class="rounded"
  >
    <img
      v-if="src && !failed"
      :src="src"
      :alt="alt"
      class="absolute inset-0 h-full w-full object-cover transition-transform duration-500 ease-standard group-hover:scale-[1.04]"
      loading="lazy"
      @error="onError"
    />
    <span v-if="failed || !src" class="font-display text-4xl font-semibold text-brand-300">{{ alt.slice(0, 1) }}</span>
  </div>
</template>
