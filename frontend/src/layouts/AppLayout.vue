<script setup lang="ts">
import AppTopBar from '@/components/AppTopBar.vue'
import AppSidebar from '@/components/AppSidebar.vue'
import { useSidebar } from '@/composables/useSidebar'

const { collapsed, toggle } = useSidebar()
</script>

<template>
  <div class="app-shell">
    <AppTopBar :collapsed="collapsed" @toggle-sidebar="toggle" />
    <div class="app-body">
      <AppSidebar :collapsed="collapsed" />
      <main class="app-main">
        <RouterView v-slot="{ Component }">
          <Transition name="fade" mode="out-in">
            <component :is="Component" />
          </Transition>
        </RouterView>
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  min-width: 1024px;  /* spec YAGNI：本轮不做响应式 */
}
.app-body {
  flex: 1;
  display: flex;
  min-height: 0;
}
.app-main {
  flex: 1;
  overflow: auto;
  padding: 20px 24px;
  background: #faf8f4;
}
</style>
