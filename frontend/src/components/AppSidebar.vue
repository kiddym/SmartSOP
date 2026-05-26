<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElIcon, ElMenu, ElMenuItem } from 'element-plus'
import { Document, EditPen } from '@element-plus/icons-vue'

defineProps<{
  collapsed: boolean
}>()

const route = useRoute()

// /procedures/:id, /procedures/:id/edit, /procedures/:id/view 都归"程序库"
// /procedures/drafts 独立
// ⚙ 下的页面（/settings, /settings/fields, /audit-logs, /folders）侧栏不高亮
const activeMenu = computed<string>(() => {
  if (route.path.startsWith('/procedures/drafts')) return '/procedures/drafts'
  if (route.path.startsWith('/procedures')) return '/procedures/library'
  return ''
})

defineExpose({ activeMenu })
</script>

<template>
  <aside class="app-aside" :class="{ collapsed }">
    <el-menu
      :default-active="activeMenu"
      :collapse="collapsed"
      :collapse-transition="false"
      router
      text-color="#3a3530"
      background-color="transparent"
      :style="{ '--el-menu-active-color': 'var(--accent)' }"
    >
      <div v-if="!collapsed" class="menu-group-label">内容</div>
      <el-menu-item index="/procedures/library">
        <el-icon><Document /></el-icon>
        <template #title>程序库</template>
      </el-menu-item>
      <el-menu-item index="/procedures/drafts">
        <el-icon><EditPen /></el-icon>
        <template #title>草稿箱</template>
      </el-menu-item>
    </el-menu>
  </aside>
</template>

<style scoped>
.app-aside {
  width: 240px;
  background: var(--bg-surface);
  border-right: 1px solid #e0dbd3;
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease;
  overflow: hidden;
}
.app-aside.collapsed {
  width: 64px;
}
.app-aside :deep(.el-menu) {
  border-right: none;
  background: transparent;
  flex: 1;
}
.menu-group-label {
  padding: 14px 16px 4px;
  font-size: 11px;
  color: #9a8e80;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
</style>
