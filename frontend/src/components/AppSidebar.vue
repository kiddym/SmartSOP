<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMenu, ElMenuItem } from 'element-plus'
import { useAuthStore } from '@/store/auth'

defineProps<{ collapsed: boolean }>()
const route = useRoute()
const auth = useAuthStore()

interface NavItem {
  label: string
  path?: string
  soon?: boolean
}
interface NavGroup {
  label: string
  items: NavItem[]
}

// 货币管理仅 super_admin 可见；其余平台项不受限。
const platformItems = computed<NavItem[]>(() => {
  const items: NavItem[] = [
    { label: '用户', path: '/platform/users' },
    { label: '角色', path: '/platform/roles' },
    { label: '团队', path: '/platform/teams' },
    { label: '公司设置', path: '/platform/settings' },
    { label: '货币', path: '/platform/currencies' },
  ]
  if (auth.user?.role_code !== 'super_admin') {
    return items.filter((it) => it.path !== '/platform/currencies')
  }
  return items
})

const groups = computed<NavGroup[]>(() => [
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
      { label: '资产', path: '/maindata/assets' },
      { label: '位置', path: '/maindata/locations' },
      { label: '请求', path: '/maintenance/requests' },
      { label: '预防性维护', path: '/maintenance/preventive-maintenances' },
      { label: '计量', path: '/maintenance/meters' },
    ],
  },
  {
    label: '供应',
    items: [
      { label: '备件库存', path: '/inventory/parts' },
      { label: '采购单', path: '/inventory/purchase-orders' },
      { label: '供应商', path: '/inventory/vendors' },
      { label: '客户', path: '/inventory/customers' },
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
    items: platformItems.value,
  },
])

const activeMenu = computed<string>(() => {
  if (route.path.startsWith('/platform/')) return route.path
  if (route.path.startsWith('/maindata/')) return route.path
  if (route.path.startsWith('/inventory/')) return route.path
  if (route.path.startsWith('/maintenance/')) return route.path
  if (route.path.startsWith('/procedures/drafts')) return '/procedures/drafts'
  if (route.path.startsWith('/procedures')) return '/procedures/library'
  if (route.path.startsWith('/folders')) return '/folders'
  if (route.path.startsWith('/audit-logs')) return '/audit-logs'
  return ''
})

defineExpose({ activeMenu, platformItems })
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
