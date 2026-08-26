<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'

import BrandLogo from '@/components/BrandLogo.vue'
import { NAV_ICONS } from '@/components/nav-icons'
import { useRoleStore } from '@/stores/role'

const route = useRoute()
const router = useRouter()
const role = useRoleStore()

const navItems = [
  { to: '/production/overview', label: '生产总览', icon: 'activity' },
  { to: '/production/agent', label: '生产助手', icon: 'agent' },
  { to: '/production/tasks', label: '制作任务', icon: 'list' },
  { to: '/production/inventory', label: '库存', icon: 'box' },
  { to: '/production/quality', label: '质检', icon: 'check' },
  { to: '/production/devices', label: '设备', icon: 'cpu' },
]

function exitRole(): void {
  role.exit()
  router.push('/')
}
</script>

<template>
  <div class="flex min-h-screen bg-[#f3f5f8]">
    <aside class="sticky top-0 flex h-screen w-60 shrink-0 flex-col bg-brand-950 px-4 py-6 text-white">
      <div class="px-2">
        <BrandLogo light />
      </div>

      <nav class="mt-8 flex flex-1 flex-col gap-1" aria-label="生产端导航">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-brand-200 transition-colors hover:bg-white/5 hover:text-white"
          active-class="bg-white/10 text-white"
          exact-active-class="bg-white/10 text-white"
        >
          <svg viewBox="0 0 24 24" class="size-[18px]" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
            <path v-for="(p, i) in NAV_ICONS[item.icon]" :key="i" :d="p" />
          </svg>
          {{ item.label }}
        </RouterLink>
      </nav>

      <button
        class="flex cursor-pointer items-center gap-2 rounded-xl border border-white/10 px-3 py-2.5 text-sm text-brand-200 transition-colors hover:bg-white/5 hover:text-white"
        @click="exitRole"
      >
        <svg viewBox="0 0 24 24" class="size-[18px]" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
          <path v-for="(p, i) in NAV_ICONS.home" :key="i" :d="p" />
        </svg>
        返回首页
      </button>
    </aside>

    <div class="flex min-w-0 flex-1 flex-col">
      <header class="sticky top-0 z-40 flex h-16 items-center gap-3 border-b border-line-cool bg-surface/85 px-6 backdrop-blur">
        <h1 class="font-display text-lg font-semibold text-brand-900">{{ route.meta.title }}</h1>
        <span class="ml-auto flex items-center gap-2 rounded-full bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700">
          <span class="size-1.5 rounded-full bg-success-500" />
          store-main · 门店演示
        </span>
        <button class="btn-ghost !py-1.5 text-xs" @click="exitRole">切换角色</button>
      </header>
      <main class="flex-1 p-6">
        <RouterView />
      </main>
    </div>
  </div>
</template>
