<script setup lang="ts">
import { useRouter } from 'vue-router'

import BrandLogo from '@/components/BrandLogo.vue'
import { NAV_ICONS } from '@/components/nav-icons'
import { useCartStore } from '@/stores/cart'
import { useRoleStore } from '@/stores/role'

const router = useRouter()
const cart = useCartStore()
const role = useRoleStore()

type ViewTransitionDocument = Document & {
  startViewTransition?: (update: () => void | Promise<void>) => unknown
}

const navItems = [
  { to: '/consumer/menu', label: '菜单', icon: 'menu' },
  { to: '/consumer/agent', label: '智能点餐', icon: 'agent' },
  { to: '/consumer/queue', label: '排队', icon: 'users' },
  { to: '/consumer/orders', label: '我的订单', icon: 'receipt' },
]

function exitRole(): void {
  role.exit()
  router.push('/')
}

function enterKiosk(): void {
  const transitionDocument = document as ViewTransitionDocument
  if (transitionDocument.startViewTransition) {
    transitionDocument.startViewTransition(async () => {
      await router.push({ name: 'consumer-kiosk' })
    })
    return
  }
  router.push({ name: 'consumer-kiosk' })
}
</script>

<template>
  <div class="min-h-screen bg-paper">
    <header class="sticky top-0 z-40 border-b border-line bg-surface/85 backdrop-blur">
      <div class="mx-auto flex h-16 max-w-[1440px] items-center gap-6 px-6">
        <button class="shrink-0 cursor-pointer" aria-label="返回首页" @click="exitRole">
          <BrandLogo />
        </button>

        <nav class="flex items-center gap-1 rounded-full border border-line bg-paper p-1" aria-label="用户端导航">
          <RouterLink
            v-for="item in navItems"
            :key="item.to"
            :to="item.to"
            class="flex items-center gap-1.5 rounded-full px-4 py-1.5 text-sm font-medium transition-colors"
            active-class="bg-brand-900 text-white"
            exact-active-class="bg-brand-900 text-white"
          >
            <svg viewBox="0 0 24 24" class="size-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path v-for="(p, i) in NAV_ICONS[item.icon]" :key="i" :d="p" />
            </svg>
            {{ item.label }}
          </RouterLink>
        </nav>

        <div class="ml-auto flex items-center gap-3">
          <button class="btn-accent !py-1.5" @click="enterKiosk">
            <svg viewBox="0 0 24 24" class="size-4" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
              <rect x="3" y="4" width="18" height="13" rx="2" />
              <path d="M8 21h8M12 17v4" stroke-linecap="round" />
            </svg>
            进入自助点餐
          </button>
          <button
            class="flex cursor-pointer items-center gap-2 rounded-full border border-line bg-surface py-1.5 pl-1.5 pr-4 text-sm transition-colors hover:border-brand-300"
            @click="router.push('/consumer/menu')"
          >
            <span class="relative grid size-7 place-items-center rounded-full bg-accent-50 text-accent-600">
              <svg viewBox="0 0 24 24" class="size-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M4 7h16l-1.5 11a2 2 0 0 1-2 1.8H7.5a2 2 0 0 1-2-1.8L4 7Z" />
                <path d="M8.5 10V6a3.5 3.5 0 0 1 7 0v4" />
              </svg>
              <span
                v-if="cart.totalCount > 0"
                data-cart-count
                class="absolute -right-1 -top-1 grid size-4 place-items-center rounded-full bg-accent-500 text-[10px] font-semibold text-white tabular-nums"
              >
                {{ cart.totalCount }}
              </span>
            </span>
            <span class="font-medium text-ink-700 tabular-nums">¥{{ (cart.totalPriceCent / 100).toFixed(2) }}</span>
          </button>
          <button class="btn-ghost !py-1.5 text-xs" @click="exitRole">切换角色</button>
        </div>
      </div>
    </header>

    <main class="mx-auto max-w-[1440px] px-6 py-6">
      <RouterView />
    </main>
  </div>
</template>
