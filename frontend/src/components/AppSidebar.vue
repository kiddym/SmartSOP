<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMenu, ElMenuItem } from 'element-plus'

defineProps<{ collapsed: boolean }>()
const route = useRoute()

interface NavItem {
  label: string
  path?: string
  soon?: boolean
}
interface NavGroup {
  label: string
  items: NavItem[]
}

const groups: NavGroup[] = [
  {
    label: 'SOP',
    items: [
      { label: '程序库', path: '/procedures/library' },
      { label: '草稿箱', path: '/procedures/drafts' },
      { label: '文件夹', path: '/folders' },
      { label: '审计日志', path: '/audit-logs' },
    ],
  },
  {
    label: '维护',
    items: [
      { label: '工单', soon: true },
      { label: '资产', soon: true },
      { label: '位置', soon: true },
      { label: '请求', soon: true },
      { label: '预防性维护', soon: true },
      { label: '计量', soon: true },
    ],
  },
  {
    label: '供应',
    items: [
      { label: '备件库存', soon: true },
      { label: '采购单', soon: true },
      { label: '供应商', soon: true },
      { label: '客户', soon: true },
    ],
  },
  {
    label: '洞察',
    items: [
      { label: '分析仪表盘', soon: true },
      { label: '通知中心', soon: true },
    ],
  },
  {
    label: '平台',
    items: [
      { label: '用户', soon: true },
      { label: '角色', soon: true },
      { label: '团队', soon: true },
      { label: '公司设置', soon: true },
    ],
  },
]

const activeMenu = computed<string>(() => {
  if (route.path.startsWith('/procedures/drafts')) return '/procedures/drafts'
  if (route.path.startsWith('/procedures')) return '/procedures/library'
  if (route.path.startsWith('/folders')) return '/folders'
  if (route.path.startsWith('/audit-logs')) return '/audit-logs'
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
      <template v-for="g in groups" :key="g.label">
        <div v-if="!collapsed" class="menu-group-label">{{ g.label }}</div>
        <el-menu-item
          v-for="it in g.items"
          :key="it.label"
          :index="it.path ?? `soon:${it.label}`"
          :disabled="it.soon"
        >
          <template #title>
            {{ it.label }}<span v-if="it.soon" class="soon-tag">即将上线</span>
          </template>
        </el-menu-item>
      </template>
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
.soon-tag {
  margin-left: 6px;
  font-size: 10px;
  color: #bbb;
}
</style>
