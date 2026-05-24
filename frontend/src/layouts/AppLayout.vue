<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Document, EditPen, Folder, Setting } from '@element-plus/icons-vue'

const route = useRoute()
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
    <el-aside width="220px" class="app-aside">
      <div class="app-brand">Smart SOP</div>
      <el-menu
        :default-active="activeMenu"
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
      <RouterView />
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
  border-right: 1px solid #e0dbd3;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.04);
}
.app-brand {
  color: var(--text-primary);
  font-size: 18px;
  font-weight: 700;
  padding: 18px 20px;
  letter-spacing: 0.5px;
  border-bottom: 1px solid #e0dbd3;
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
