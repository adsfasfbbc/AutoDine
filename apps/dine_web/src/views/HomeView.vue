<script setup lang="ts">
import { useRouter } from 'vue-router'

import BrandLogo from '@/components/BrandLogo.vue'
import type { Role } from '@/router'
import { useRoleStore } from '@/stores/role'

const router = useRouter()
const role = useRoleStore()

interface Entry {
  role: Role
  name: string
  en: string
  to: string
  headline: string
  desc: string
  points: string[]
  tone: 'accent' | 'brand' | 'ink'
}

const entries: Entry[] = [
  {
    role: 'consumer',
    name: '消费者端',
    en: 'DINE',
    to: '/consumer/menu',
    headline: '智能点餐 · 实时订单',
    desc: '浏览菜单、加入购物车、排队取餐，全流程一张桌面完成。',
    points: ['40 SKU 菜单与多维度筛选', '持久购物车与一键下单', '排队与订单状态实时推进'],
    tone: 'accent',
  },
  {
    role: 'production',
    name: '生产端',
    en: 'PRODUCE',
    to: '/production/overview',
    headline: '制作履约 · 库存联动',
    desc: '制作任务、原料库存、质检与设备状态，门店执行的单一视图。',
    points: ['制作任务与 Pick List', 'BOM 驱动的可售量联动', '质检异常与设备告警'],
    tone: 'brand',
  },
  {
    role: 'admin',
    name: '管理端',
    en: 'MANAGE',
    to: '/admin/overview',
    headline: '经营分析 · 云端决策',
    desc: '订单、客流、库存、告警与经营分析，全局视角一目了然。',
    points: ['经营总览与 KPI', '客流与库存分析', '告警收敛与处置'],
    tone: 'ink',
  },
]

function enter(entry: Entry): void {
  role.enter(entry.role)
  router.push(entry.to)
}
</script>

<template>
  <section class="relative flex min-h-screen flex-col overflow-hidden bg-paper">
    <!-- 背景氛围光 -->
    <div
      class="pointer-events-none absolute -left-40 -top-40 size-[480px] rounded-full bg-accent-200/50 blur-[120px]"
      aria-hidden="true"
    />
    <div
      class="pointer-events-none absolute -bottom-48 -right-32 size-[520px] rounded-full bg-brand-200/60 blur-[130px]"
      aria-hidden="true"
    />

    <header class="relative z-10 mx-auto flex w-full max-w-[1440px] items-center justify-between px-8 pt-8">
      <BrandLogo />
      <span class="flex items-center gap-2 rounded-full border border-line bg-surface/80 px-3 py-1.5 text-xs text-ink-400 backdrop-blur">
        <span class="size-1.5 rounded-full bg-success-500" />
        演示模式 · 示例数据 · 接口可替换
      </span>
    </header>

    <div class="relative z-10 mx-auto flex w-full max-w-[1440px] flex-1 flex-col justify-center px-8 py-10">
      <div class="anim-rise max-w-2xl">
        <p class="eyebrow">AutoDine · 云边协同无人餐厅</p>
        <h1 class="mt-4 font-display text-[44px] font-semibold leading-[1.2] tracking-tight text-brand-950">
          同一家门店，
          <br />
          三个角色，一条业务链路
        </h1>
        <p class="mt-5 max-w-xl text-[15px] leading-relaxed text-ink-500">
          把点餐、生产履约与经营管理放进一个统一体验中，让消费者、生产与管理者看到同一业务链路的对应视图——
          云端做经营决策，边缘门店实时执行。
        </p>
      </div>

      <div class="mt-10 grid grid-cols-3 gap-6">
        <button
          v-for="(entry, i) in entries"
          :key="entry.role"
          class="anim-plate group cursor-pointer overflow-hidden rounded-3xl border border-line bg-surface text-left transition-all duration-300 hover:-translate-y-1.5 hover:shadow-[0_24px_48px_-20px_rgba(20,41,61,0.28)]"
          :style="{ animationDelay: `${i * 110}ms` }"
          @click="enter(entry)"
        >
          <!-- 顶部图带 -->
          <div class="relative h-40 overflow-hidden" :class="entry.tone === 'accent' ? 'bg-gradient-to-br from-accent-300 via-accent-400 to-accent-600' : entry.tone === 'brand' ? 'bg-gradient-to-br from-brand-500 via-brand-700 to-brand-900' : 'bg-gradient-to-br from-ink-500 via-ink-700 to-ink-900'">
            <div class="absolute inset-0 opacity-25 [background-image:radial-gradient(circle_at_20%_20%,white_1px,transparent_1px)] [background-size:18px_18px]" aria-hidden="true" />
            <!-- 消费者：杯与托盘 -->
            <svg v-if="entry.tone === 'accent'" viewBox="0 0 120 80" class="absolute -bottom-6 right-6 size-40 text-white/90 transition-transform duration-500 group-hover:rotate-[-4deg] group-hover:scale-105" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round">
              <path d="M28 18h44v22a14 14 0 0 1-14 14H42a14 14 0 0 1-14-14V18Z" />
              <path d="M72 24h10a8 8 0 0 1 0 16H72" />
              <path d="M34 60h32M50 54v6" />
            </svg>
            <!-- 生产：传送带与工位 -->
            <svg v-else-if="entry.tone === 'brand'" viewBox="0 0 120 80" class="absolute -bottom-6 right-4 size-40 text-white/90 transition-transform duration-500 group-hover:translate-x-1" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round">
              <circle cx="30" cy="52" r="10" />
              <circle cx="30" cy="52" r="3.5" />
              <circle cx="62" cy="52" r="10" />
              <circle cx="62" cy="52" r="3.5" />
              <path d="M40 52h12M76 52h18M92 42v20" />
              <path d="M20 24h64v10H20z" />
              <path d="M84 24v10" />
            </svg>
            <!-- 管理：柱状图 -->
            <svg v-else viewBox="0 0 120 80" class="absolute -bottom-4 right-5 size-40 text-white/90 transition-transform duration-500 group-hover:scale-105" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round">
              <path d="M18 64h84" />
              <path d="M32 64V42M52 64V30M72 64V36M92 64V22" />
              <path d="M28 46l8-6 10 8 12-12 10 6 12-10" stroke-width="2.2" />
            </svg>
          </div>

          <!-- 文字区 -->
          <div class="p-6">
            <div class="flex items-baseline justify-between">
              <span class="text-[11px] font-semibold uppercase tracking-[0.22em]" :class="entry.tone === 'accent' ? 'text-accent-600' : entry.tone === 'brand' ? 'text-brand-600' : 'text-ink-500'">
                {{ entry.en }}
              </span>
              <span class="font-display text-xl font-semibold text-ink-900">{{ entry.name }}</span>
            </div>
            <h2 class="mt-1 font-display text-lg font-semibold text-brand-950">{{ entry.headline }}</h2>
            <p class="mt-2 text-[13px] leading-relaxed text-ink-500">{{ entry.desc }}</p>
            <ul class="mt-4 space-y-1.5">
              <li v-for="p in entry.points" :key="p" class="flex items-center gap-2 text-[12.5px] text-ink-700">
                <svg viewBox="0 0 24 24" class="size-3.5 shrink-0" :class="entry.tone === 'accent' ? 'text-accent-500' : 'text-brand-500'" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
                  <path d="m5 13 4 4L19 7" />
                </svg>
                {{ p }}
              </li>
            </ul>
            <div class="mt-5 flex items-center gap-1.5 text-sm font-semibold" :class="entry.tone === 'accent' ? 'text-accent-600' : 'text-brand-700'">
              进入{{ entry.name }}
              <svg viewBox="0 0 24 24" class="size-4 transition-transform duration-300 group-hover:translate-x-1" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            </div>
          </div>
        </button>
      </div>
    </div>

    <footer class="relative z-10 mx-auto flex w-full max-w-[1440px] items-center justify-between px-8 pb-6 text-xs text-ink-300">
      <span>AutoDine · Vue 3 + Vite + TypeScript · 三端统一桌面 SPA</span>
      <span>1440×900 / 1920×1080 桌面横屏适配</span>
    </footer>
  </section>
</template>
