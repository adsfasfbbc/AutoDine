<script setup lang="ts">
import { useMessage } from 'naive-ui'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { realtime } from '@/api'
import type { Product, ProductCategory, ProductStatus } from '@/api/types'
import BrandLogo from '@/components/BrandLogo.vue'
import CartPanel from '@/components/CartPanel.vue'
import KioskProductCard from '@/components/KioskProductCard.vue'
import { CATEGORY_LABELS } from '@/data/products'
import { useCartStore } from '@/stores/cart'
import { useMenuStore } from '@/stores/menu'
import { useOrderStore } from '@/stores/order'

const router = useRouter()
const message = useMessage()
const menu = useMenuStore()
const cart = useCartStore()
const orderStore = useOrderStore()

const activeCategory = ref<string>('ALL')
const busy = ref(false)

const categoryColors: Record<string, string> = {
  ALL: '#14293d',
  DRINK: '#087f78',
  CUP_DESSERT: '#ad456c',
  CAKE: '#8d5c25',
  HOT_FOOD: '#c45532',
  LIGHT_MEAL: '#47785a',
}

const categories = computed(() => {
  const counts = new Map<string, number>()
  for (const product of menu.products) {
    counts.set(product.category, (counts.get(product.category) ?? 0) + 1)
  }
  return [
    { key: 'ALL', label: '全部美味', hint: '今日精选', count: menu.products.length },
    ...[...counts.entries()].map(([key, count]) => ({
      key,
      label: CATEGORY_LABELS[key as ProductCategory],
      hint: key === 'DRINK' ? '清爽现制' : key === 'HOT_FOOD' ? '趁热享用' : '甜点时光',
      count,
    })),
  ]
})

const visibleProducts = computed(() =>
  activeCategory.value === 'ALL'
    ? menu.products
    : menu.products.filter((product) => product.category === activeCategory.value),
)

const activeCategoryLabel = computed(
  () => categories.value.find((category) => category.key === activeCategory.value)?.label ?? '全部美味',
)

let unsubscribe: (() => void) | undefined

onMounted(async () => {
  await menu.load()
  unsubscribe = realtime.on('menu.availability_changed', (event) => {
    menu.updateFromEvent(event.payload as { product_id: string; status: ProductStatus })
  })
})

onUnmounted(() => unsubscribe?.())

function returnToMenu(): void {
  router.push({ name: 'consumer-menu' })
}

function openAgent(): void {
  router.push({ name: 'consumer-agent' })
}

function addToCart(product: Product): void {
  cart.add(product)
  message.success(`已加入：${product.name}`)
}

async function checkout(): Promise<void> {
  if (cart.isEmpty || busy.value) return
  busy.value = true
  try {
    const items = cart.lines.map((line) => ({
      product_id: line.product.product_id,
      quantity: line.quantity,
    }))
    const order = await orderStore.placeOrder(items)
    cart.clear()
    message.success(`订单 ${order.order_id} 已提交，正在排队`)
    router.push({ name: 'consumer-orders' })
  } catch (error) {
    message.error(error instanceof Error ? error.message : '下单失败，请重试')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="kiosk-enter-wash min-h-screen bg-[#f3eee6]">
    <header class="sticky top-0 z-40 border-b border-white/10 bg-brand-950 text-white shadow-[0_16px_50px_-34px_rgba(0,0,0,0.9)]">
      <div class="mx-auto flex h-20 max-w-[1800px] items-center gap-5 px-6">
        <button class="rounded-xl bg-white px-3 py-2" aria-label="AutoDine 普通点餐首页" @click="returnToMenu">
          <BrandLogo />
        </button>

        <div class="h-8 w-px bg-white/15" />
        <div>
          <p class="text-[10px] font-semibold uppercase tracking-[0.24em] text-accent-300">In-store ordering</p>
          <h1 class="font-display text-2xl font-semibold">自助点餐</h1>
        </div>

        <div class="ml-auto flex items-center gap-3">
          <div class="hidden items-center gap-2 rounded-full border border-white/15 bg-white/5 px-4 py-2 text-xs text-brand-100 xl:flex">
            <span class="size-2 rounded-full bg-success-500 shadow-[0_0_0_4px_rgba(62,142,95,0.18)]" />
            菜单实时同步 · 自助点餐已就绪
          </div>
          <button class="flex min-h-11 items-center gap-2 rounded-full border border-white/15 px-4 text-sm font-medium transition-colors hover:bg-white/10" @click="returnToMenu">
            <svg viewBox="0 0 24 24" class="size-4" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
              <path d="m15 18-6-6 6-6" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            返回普通页面
          </button>
          <button class="kiosk-stamp flex min-h-11 items-center gap-2 rounded-full bg-accent-500 px-5 text-sm font-semibold text-white transition-colors hover:bg-accent-600" @click="openAgent">
            <svg viewBox="0 0 24 24" class="size-4" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
              <path d="M12 3a7 7 0 0 0-7 7v3a4 4 0 0 0 4 4h1v-6H7v-1a5 5 0 0 1 10 0v1h-3v6h3.5A2.5 2.5 0 0 1 15 19.5h-2" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            帮我选
          </button>
        </div>
      </div>
    </header>

    <main class="kiosk-canvas mx-auto grid max-w-[1800px] grid-cols-[144px_minmax(0,1fr)_360px] items-start gap-5 px-6 py-6">
      <nav class="sticky top-26 space-y-3" aria-label="自助点餐分类">
        <p class="px-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-400">Choose</p>
        <button
          v-for="category in categories"
          :key="category.key"
          :aria-pressed="activeCategory === category.key"
          class="group relative min-h-[88px] w-full overflow-hidden rounded-[22px] border px-4 py-3 text-left transition-all"
          :class="activeCategory === category.key ? 'border-transparent text-white shadow-[0_18px_34px_-20px_rgba(12,27,41,0.65)]' : 'border-white/80 bg-white/80 text-brand-950 hover:border-brand-200 hover:bg-white'"
          :style="activeCategory === category.key ? { backgroundColor: categoryColors[category.key] } : undefined"
          @click="activeCategory = category.key"
        >
          <span class="block font-display text-base font-semibold">{{ category.label }}</span>
          <span class="mt-1 block text-[11px]" :class="activeCategory === category.key ? 'text-white/70' : 'text-ink-400'">{{ category.hint }}</span>
          <span
            class="absolute bottom-3 right-3 grid size-7 place-items-center rounded-full text-[11px] font-semibold tabular-nums"
            :class="activeCategory === category.key ? 'bg-white/15 text-white' : 'bg-brand-50 text-brand-700'"
          >
            {{ category.count }}
          </span>
        </button>
      </nav>

      <section class="min-w-0" aria-live="polite">
        <div class="flex items-end justify-between gap-6 rounded-[28px] bg-brand-900 px-6 py-5 text-white shadow-[0_20px_55px_-38px_rgba(12,27,41,0.9)]">
          <div>
            <p class="text-[10px] font-semibold uppercase tracking-[0.22em] text-accent-300">Freshly made for you</p>
            <h2 class="mt-1 font-display text-3xl font-semibold">{{ activeCategoryLabel }}</h2>
          </div>
          <p class="max-w-[330px] text-right text-xs leading-5 text-brand-200">照片、热量与制作时间一眼看清；点击加入后，右侧订单会立即同步。</p>
        </div>

        <div v-if="menu.loading && !menu.loaded" class="mt-5 grid grid-cols-3 gap-4">
          <div v-for="index in 6" :key="index" class="h-80 animate-pulse rounded-[26px] bg-white/75" />
        </div>

        <div v-else-if="menu.error" class="mt-5 rounded-[26px] border border-danger-100 bg-white p-10 text-center">
          <p class="font-medium text-danger-500">菜单暂时没有加载成功</p>
          <p class="mt-1 text-sm text-ink-400">{{ menu.error }}</p>
          <button class="btn-ghost mt-5" @click="menu.load(true)">重新加载</button>
        </div>

        <div v-else-if="visibleProducts.length === 0" class="mt-5 rounded-[26px] bg-white p-12 text-center text-ink-400">
          当前分类暂无在售商品，请看看其他分类。
        </div>

        <div v-else class="mt-5 grid grid-cols-3 gap-4 2xl:grid-cols-4">
          <KioskProductCard
            v-for="product in visibleProducts"
            :key="product.product_id"
            :product="product"
            @add="addToCart"
          />
        </div>
      </section>

      <div class="sticky top-[104px] min-w-0 self-start [&_.card]:border-white/80 [&_.card]:shadow-[0_22px_60px_-38px_rgba(12,27,41,0.55)]">
        <CartPanel class="!static !max-h-[calc(100vh-128px)]" title="自助订单" :busy="busy" @checkout="checkout" />
        <p class="mt-3 px-3 text-center text-[11px] leading-5 text-ink-400">下单即代表已确认菜品、过敏原与预计制作时间</p>
      </div>
    </main>
  </div>
</template>

<style scoped>
.kiosk-canvas {
  background-image:
    radial-gradient(circle at 72% 5%, rgba(217, 122, 46, 0.11), transparent 28rem),
    radial-gradient(circle at 5% 72%, rgba(59, 114, 156, 0.11), transparent 24rem);
}
</style>
