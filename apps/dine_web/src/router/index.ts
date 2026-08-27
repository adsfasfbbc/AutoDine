import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

export type Role = 'consumer' | 'production' | 'admin'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
    meta: { title: 'AutoDine' },
  },
  {
    path: '/consumer/kiosk',
    name: 'consumer-kiosk',
    component: () => import('@/views/consumer/KioskView.vue'),
    meta: { title: '自助点餐', role: 'consumer' },
  },
  {
    path: '/consumer',
    component: () => import('@/layouts/ConsumerLayout.vue'),
    meta: { role: 'consumer', title: '用户端' },
    children: [
      { path: '', redirect: { name: 'consumer-menu' } },
      {
        path: 'menu',
        name: 'consumer-menu',
        component: () => import('@/views/consumer/MenuView.vue'),
        meta: { title: '菜单', role: 'consumer' },
      },
      {
        path: 'agent',
        name: 'consumer-agent',
        component: () => import('@/views/consumer/AgentView.vue'),
        meta: { title: '智能点餐', role: 'consumer' },
      },
      {
        path: 'queue',
        name: 'consumer-queue',
        component: () => import('@/views/consumer/QueueView.vue'),
        meta: { title: '排队', role: 'consumer' },
      },
      {
        path: 'orders',
        name: 'consumer-orders',
        component: () => import('@/views/consumer/OrderView.vue'),
        meta: { title: '我的订单', role: 'consumer' },
      },
    ],
  },
  {
    path: '/production',
    component: () => import('@/layouts/ProductionLayout.vue'),
    meta: { role: 'production', title: '生产端' },
    children: [
      { path: '', redirect: { name: 'production-overview' } },
      {
        path: 'overview',
        name: 'production-overview',
        component: () => import('@/views/production/OverviewView.vue'),
        meta: { title: '生产总览', role: 'production' },
      },
      {
        path: 'agent',
        name: 'production-agent',
        component: () => import('@/views/production/AgentView.vue'),
        meta: { title: '生产助手', role: 'production' },
      },
      {
        path: 'tasks',
        name: 'production-tasks',
        component: () => import('@/views/production/TasksView.vue'),
        meta: { title: '制作任务', role: 'production' },
      },
      {
        path: 'inventory',
        name: 'production-inventory',
        component: () => import('@/views/production/InventoryView.vue'),
        meta: { title: '库存', role: 'production' },
      },
      {
        path: 'quality',
        name: 'production-quality',
        component: () => import('@/views/production/QualityView.vue'),
        meta: { title: '质检', role: 'production' },
      },
      {
        path: 'devices',
        name: 'production-devices',
        component: () => import('@/views/production/DevicesView.vue'),
        meta: { title: '设备', role: 'production' },
      },
    ],
  },
  {
    path: '/admin',
    component: () => import('@/layouts/AdminLayout.vue'),
    meta: { role: 'admin', title: '管理端' },
    children: [
      { path: '', redirect: { name: 'admin-overview' } },
      {
        path: 'overview',
        name: 'admin-overview',
        component: () => import('@/views/admin/OverviewView.vue'),
        meta: { title: '经营总览', role: 'admin' },
      },
      {
        path: 'agent',
        name: 'admin-agent',
        component: () => import('@/views/admin/AgentView.vue'),
        meta: { title: '管理助手', role: 'admin' },
      },
      {
        path: 'orders',
        name: 'admin-orders',
        component: () => import('@/views/admin/OrdersView.vue'),
        meta: { title: '订单管理', role: 'admin' },
      },
      {
        path: 'traffic',
        name: 'admin-traffic',
        component: () => import('@/views/admin/TrafficView.vue'),
        meta: { title: '客流分析', role: 'admin' },
      },
      {
        path: 'inventory',
        name: 'admin-inventory',
        component: () => import('@/views/admin/InventoryView.vue'),
        meta: { title: '库存管理', role: 'admin' },
      },
      {
        path: 'alarms',
        name: 'admin-alarms',
        component: () => import('@/views/admin/AlarmsView.vue'),
        meta: { title: '告警中心', role: 'admin' },
      },
      {
        path: 'analytics',
        name: 'admin-analytics',
        component: () => import('@/views/admin/AnalyticsView.vue'),
        meta: { title: '经营分析', role: 'admin' },
      },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: { name: 'home' } },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.afterEach((to) => {
  const title = to.meta.title as string | undefined
  document.title = title ? `${title} · AutoDine` : 'AutoDine · 无人餐厅与甜品店中枢'
})

export default router
