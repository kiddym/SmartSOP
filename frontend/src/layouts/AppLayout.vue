<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Document, EditPen, Folder, Setting, Fold, Expand } from '@element-plus/icons-vue'
import { useSidebar } from '@/composables/useSidebar'

const route = useRoute()
const { collapsed, toggle } = useSidebar()

// 顶层菜单高亮：详情页 /procedures/:id 归到「程序库」
const activeMenu = computed(() => {
  if (route.path.startsWith('/settings/fields')) return '/settings/fields'
  if (route.path.startsWith('/settings')) return '/settings'
  if (route.path.startsWith('/audit-logs')) return '/audit-logs'
  if (route.path.startsWith('/folders')) return '/folders'
  if (route.path.startsWith('/procedures/drafts')) return '/procedures/drafts'
  return '/procedures/library'
})
</script>

<template>
  <el-container class="app-layout">
    <el-aside :width="collapsed ? '64px' : '220px'" class="app-aside">
      <div class="app-brand" :class="{ collapsed }">
        <span v-if="!collapsed" class="brand-text">Smart SOP</span>
        <span v-else class="brand-mark">S</span>
        <button
          class="brand-toggle"
          :title="collapsed ? '展开侧边栏' : '折叠侧边栏'"
          @click="toggle"
        >
          <el-icon><Expand v-if="collapsed" /><Fold v-else /></el-icon>
        </button>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="collapsed"
        :collapse-transition="false"
        router
        class="app-menu"
        text-color="#3a3530"
        active-text-color="#d97757"
        background-color="transparent"
      >
        <el-menu-item index="/procedures/library">
          <el-icon><Document /></el-icon>
          <span>程序库</span>
        </el-menu-item>
        <el-menu-item index="/procedures/drafts">
          <el-icon><EditPen /></el-icon>
          <span>草稿箱</span>
        </el-menu-item>
        <el-menu-item index="/audit-logs">
          <el-icon><Document /></el-icon>
          <span>审计日志</span>
        </el-menu-item>
        <el-menu-item index="/folders">
          <el-icon><Folder /></el-icon>
          <span>标准文件库</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span>系统设置</span>
        </el-menu-item>
        <el-menu-item index="/settings/fields">
          <el-icon><Setting /></el-icon>
          <span>字段管理</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-main class="app-main">
      <RouterView v-slot="{ Component }">
        <Transition name="fade" mode="out-in">
          <component :is="Component" />
        </Transition>
      </RouterView>
    </el-main>
  </el-container>
</template>

<style scoped>
.app-layout {
  height: 100vh;
}
.app-aside {
  background: var(--bg-surface);
  display: flex;
  flex-direction: column;
  /* 工业风：分隔靠线不靠影（docs/design-system.md §2.4）。
     原 box-shadow 已移除，单边 1px border 接管分隔。 */
  border-right: 1px solid #e0dbd3;
  transition: width 0.2s ease;
}
.app-brand {
  color: var(--text-primary);
  font-size: 18px;
  font-weight: 700;
  padding: 14px 20px;
  letter-spacing: 0.5px;
  border-bottom: 1px solid #e0dbd3;
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 56px;
  box-sizing: border-box;
}
.app-brand.collapsed {
  padding: 14px 0;
  flex-direction: column;
  gap: 6px;
  justify-content: center;
}
.brand-mark {
  font-size: 18px;
}
.brand-toggle {
  border: none;
  background: transparent;
  padding: 4px;
  cursor: pointer;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  border-radius: 4px;
}
.brand-toggle:hover {
  color: #d97757;
  background: rgba(0, 0, 0, 0.04);
}
.app-menu {
  border-right: none;
  background: transparent;
  flex: 1;
}
.app-main {
  padding: 20px 24px;
  background: #faf8f4;
  overflow: auto;
}
</style>
