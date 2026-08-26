<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const title = computed(() => (route.meta.title as string | undefined) ?? '模块建设中')
const description = computed(() => (route.meta.description as string | undefined) ?? '该模块将在后续迭代中实现。')
const features = computed<string[]>(() => (route.meta.features as string[] | undefined) ?? [])
</script>

<template>
  <div class="anim-rise flex min-h-[62vh] items-center justify-center p-8">
    <div class="card max-w-xl p-10 text-center">
      <div class="mx-auto mb-6 grid size-14 place-items-center rounded-2xl bg-brand-50 text-brand-600">
        <svg viewBox="0 0 24 24" class="size-7" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">
          <circle cx="12" cy="12" r="8.5" />
          <path d="M12 8v4l2.6 2.6" stroke-linecap="round" />
        </svg>
      </div>
      <h2 class="font-display text-2xl font-semibold text-brand-900">{{ title }}</h2>
      <p class="mx-auto mt-3 max-w-md text-sm leading-relaxed text-ink-500">{{ description }}</p>
      <div class="mt-6 flex flex-wrap justify-center gap-2">
        <span v-for="f in features" :key="f" class="chip">{{ f }}</span>
      </div>
      <p class="mt-8 text-xs tracking-wide text-ink-300">模块建设中 · 页面与数据将在后续迭代接入</p>
    </div>
  </div>
</template>
