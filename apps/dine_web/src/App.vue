<script setup lang="ts">
import { NConfigProvider, NMessageProvider, darkTheme } from 'naive-ui'
import type { GlobalThemeOverrides } from 'naive-ui'
import { computed } from 'vue'

// 主题覆盖与 main.ts 中 app.use(naive, ...) 保持一致
const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#2c5a80',
    primaryColorHover: '#3b729c',
    primaryColorPressed: '#244a6a',
    primaryColorSuppl: '#3b729c',
    borderRadius: '8px',
  },
  Button: {
    borderRadiusMedium: '999px',
    borderRadiusSmall: '999px',
  },
}

const prefersDark = computed(() => false) // 预留深色模式开关
</script>

<template>
  <NConfigProvider :theme="prefersDark ? darkTheme : undefined" :theme-overrides="themeOverrides">
    <NMessageProvider placement="top">
      <RouterView v-slot="{ Component }">
        <Transition name="page" mode="out-in">
          <component :is="Component" />
        </Transition>
      </RouterView>
    </NMessageProvider>
  </NConfigProvider>
</template>
