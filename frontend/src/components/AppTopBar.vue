<script setup lang="ts">
import { ElIcon } from 'element-plus'
import { Expand, Fold } from '@element-plus/icons-vue'
import UserMenu from '@/components/UserMenu.vue'

// 设置入口（系统设置/字段管理/标题字典）已整合进侧边栏「设置」组，
// 顶栏不再承载配置/历史下拉，齿轮入口移除。
defineProps<{
  collapsed: boolean
  unreadCount?: number
}>()

defineEmits<{
  (e: 'toggle-sidebar'): void
}>()
</script>

<template>
  <header class="app-topbar">
    <button
      class="topbar-toggle"
      :aria-label="collapsed ? '展开侧栏' : '折叠侧栏'"
      @click="$emit('toggle-sidebar')"
    >
      <el-icon><Expand v-if="collapsed" /><Fold v-else /></el-icon>
    </button>
    <span class="app-brand">{{ $t('app.name') }}</span>
    <input
      class="topbar-search"
      type="text"
      disabled
      placeholder="⌕ 全库搜索（即将上线）"
      title="全库搜索 · 即将上线"
    />
    <span class="topbar-spacer" />
    <span
      v-if="(unreadCount ?? 0) > 0"
      class="topbar-unread font-mono"
    >
      待阅读 <span class="badge">{{ unreadCount }}</span>
    </span>
    <UserMenu />
  </header>
</template>

<style scoped>
.app-topbar {
  height: var(--topbar-height);
  display: flex;
  align-items: center;
  padding: 0 14px;
  gap: 14px;
  background: var(--bg-surface);
  border-bottom: 1px solid #e0dbd3;
  flex-shrink: 0;
}
.topbar-toggle {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
  color: #3a3530;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.topbar-toggle:hover {
  background: rgba(0, 0, 0, 0.04);
}
.app-brand {
  font-weight: 700;
  font-size: 14px;
  letter-spacing: 0.3px;
  color: var(--text-primary);
}
.topbar-search {
  flex: 1;
  max-width: 380px;
  height: 28px;
  background: #ece9e3;
  border: 1px solid #d4cfc6;
  border-radius: 4px;
  padding: 0 10px;
  color: #b5aa9c;
  font-style: italic;
  font-size: 12px;
  cursor: not-allowed;
}
.topbar-spacer {
  flex: 1;
}
.topbar-unread {
  font-size: 12px;
  color: #6b635a;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.topbar-unread .badge {
  padding: 1px 7px;
  background: var(--accent);
  color: #fff;
  border-radius: 9px;
  font-size: 10px;
  line-height: 1.4;
}
</style>
