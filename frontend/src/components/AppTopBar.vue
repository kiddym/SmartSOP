<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElIcon,
} from 'element-plus'
import { Expand, Fold, Setting } from '@element-plus/icons-vue'
import UserMenu from '@/components/UserMenu.vue'

defineProps<{
  collapsed: boolean
  unreadCount?: number
}>()

defineEmits<{
  (e: 'toggle-sidebar'): void
}>()

interface MenuCommand {
  group: '配置' | '历史'
  label: string
  path: string
}

// 暴露给测试做契约断言（避开 el-dropdown 在 jsdom 不渲染 menu 的坑）。
// 顺序 / label / path 任何修改请同步 AppTopBar.spec.ts。
const MENU_COMMANDS: readonly MenuCommand[] = [
  { group: '配置', label: '文件夹配置', path: '/folders' },
  { group: '配置', label: '系统设置', path: '/settings' },
  { group: '配置', label: '字段管理', path: '/settings/fields' },
  { group: '配置', label: '标题字典', path: '/settings/heading-rules' },
  { group: '历史', label: '审计日志', path: '/audit-logs' },
]

const configCommands = computed(() => MENU_COMMANDS.filter((c) => c.group === '配置'))
const historyCommands = computed(() => MENU_COMMANDS.filter((c) => c.group === '历史'))

const router = useRouter()
function onCommand(path: string): void {
  void router.push(path)
}

defineExpose({ MENU_COMMANDS, onCommand })
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
    <el-dropdown trigger="click" popper-class="app-topbar-cog-popper" @command="onCommand">
      <button class="topbar-cog" aria-label="设置菜单">
        <el-icon><Setting /></el-icon><span class="caret">▾</span>
      </button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item disabled class="group-label">配置</el-dropdown-item>
          <el-dropdown-item
            v-for="cmd in configCommands"
            :key="cmd.path"
            :command="cmd.path"
          >
            {{ cmd.label }}
          </el-dropdown-item>
          <el-dropdown-item disabled divided class="group-label">历史</el-dropdown-item>
          <el-dropdown-item
            v-for="cmd in historyCommands"
            :key="cmd.path"
            :command="cmd.path"
          >
            {{ cmd.label }}
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
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
.topbar-cog {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
  color: #3a3530;
  display: inline-flex;
  align-items: center;
  gap: 1px;
}
.topbar-cog .caret {
  font-size: 9px;
  color: #9a8e80;
}
.topbar-cog:hover {
  background: rgba(0, 0, 0, 0.04);
}

/* ⚙ 下拉菜单中作为分组标题的 disabled item。
   通过 popper-class 命名空间隔离，避免污染其它 el-dropdown。 */
:global(.app-topbar-cog-popper .el-dropdown-menu__item.group-label.is-disabled) {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #9a8e80;
  padding: 6px 14px 2px;
  cursor: default;
  background: transparent;
  /* 抑制 EP 默认的 disabled hover 视觉 */
  pointer-events: none;
}
:global(.app-topbar-cog-popper .el-dropdown-menu__item.group-label.is-disabled:hover) {
  background: transparent;
}
</style>
