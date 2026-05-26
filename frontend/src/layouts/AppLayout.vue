<script setup lang="ts">
import { watch } from 'vue'
import { useRoute } from 'vue-router'
import AppTopBar from '@/components/AppTopBar.vue'
import AppSidebar from '@/components/AppSidebar.vue'
import { useSidebar } from '@/composables/useSidebar'
import { decideAutoCollapse } from '@/utils/sidebarAutoCollapse'

const { collapsed, toggle } = useSidebar()
const route = useRoute()

// 自动折叠 / 用户接管追踪：
// - preEnterCollapsed 记入 library 之前的折叠态，用于离开时恢复
// - userOverride 标志位：用户在 library 内手动 toggle 视为接管，此后不再自动管
let preEnterCollapsed = collapsed.value
let userOverride = false

function onToggle(): void {
  // library 路径下用户手动 toggle → 接管
  if (route.path.startsWith('/procedures/library')) {
    userOverride = true
  }
  toggle()
}

watch(
  () => route.path,
  (to, from) => {
    const decision = decideAutoCollapse(from ?? '', to, userOverride)
    if (decision === 'collapse') {
      preEnterCollapsed = collapsed.value
      if (!collapsed.value) collapsed.value = true  // 已折叠就不重复
    } else if (decision === 'restore') {
      collapsed.value = preEnterCollapsed
      userOverride = false  // 离开 library 清接管标志
    }
  },
  { immediate: true },
)
</script>

<template>
  <div class="app-shell">
    <AppTopBar :collapsed="collapsed" @toggle-sidebar="onToggle" />
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
  /* padding 下放到各 view 根容器（让 FolderTreePane 能贴 .app-main 左缘） */
  padding: 0;
  background: #faf8f4;
}
</style>
