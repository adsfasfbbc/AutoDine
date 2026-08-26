import { ref } from 'vue'
import { defineStore } from 'pinia'

import type { Role } from '@/router'

/** 当前角色：决定进入哪个端（消费者 / 生产 / 管理） */
export const useRoleStore = defineStore('role', () => {
  const current = ref<Role | null>(null)

  function enter(role: Role): void {
    current.value = role
  }

  function exit(): void {
    current.value = null
  }

  return { current, enter, exit }
})
