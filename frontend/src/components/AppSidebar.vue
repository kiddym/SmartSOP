<script setup lang="ts">
import { computed, type Component } from 'vue'
import { useRoute } from 'vue-router'
import { ElIcon, ElMenu, ElMenuItem } from 'element-plus'
import {
  Lock,
  // SOP
  Document,
  EditPen,
  Folder,
  List,
  // 维护
  Tickets,
  Box,
  Location,
  ChatDotRound,
  Timer,
  Odometer,
  // 供应
  Goods,
  ShoppingCart,
  Shop,
  Avatar,
  // 洞察
  DataAnalysis,
  Bell,
  // 平台
  User,
  UserFilled,
  Connection,
  OfficeBuilding,
  Coin,
  // 设置
  Setting,
  Grid,
  Collection,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/store/auth'
import { useBillingStore } from '@/store/billing'

defineProps<{ collapsed: boolean }>()
const route = useRoute()
const auth = useAuthStore()
const billing = useBillingStore()

// 套餐对比页路径（锁定项点击引导至此，而非进入会满屏 402 的模块）。
const PLANS_PATH = '/billing/plans'

interface NavItem {
  label: string
  path?: string
  soon?: boolean
  requiredPermission?: string
  // 已挂 feature gate 的高级模块对应功能码；未解锁时菜单项显示锁标。
  feature?: string
  // 折叠态侧栏只显示图标（el-menu 折叠时隐藏 #title 文字），每项必须配一个。
  icon?: Component
}

// 菜单项是否因套餐未解锁而锁定。
function isLocked(it: NavItem): boolean {
  if (!it.feature) return false
  // 订阅未知（未加载/拉取失败 → subscription=null）时不显示锁：/billing/subscription 是
  // 自查端点，free 也会返回对象，故 null 只代表"未知"。后端 402 仍是真闸门，避免一次拉取
  // 失败把已付费用户的整张菜单锁死。仅在订阅已知且不含该 feature 时锁。
  if (!billing.subscription) return false
  return !billing.hasFeature(it.feature)
}

// 锁定项的导航目标改为套餐页；其余照常。
function menuIndex(it: NavItem): string {
  if (isLocked(it)) return PLANS_PATH
  return it.path ?? `soon:${it.label}`
}
interface NavGroup {
  label: string
  items: NavItem[]
}

// 货币管理仅 super_admin 可见；其余平台项不受限。
const platformItems = computed<NavItem[]>(() => {
  const items: NavItem[] = [
    { label: '用户', path: '/platform/users', icon: User },
    { label: '角色', path: '/platform/roles', icon: UserFilled },
    { label: '团队', path: '/platform/teams', icon: Connection },
    { label: '公司设置', path: '/platform/settings', icon: OfficeBuilding },
    { label: '货币', path: '/platform/currencies', icon: Coin },
  ]
  if (auth.user?.role_code !== 'super_admin') {
    return items.filter((it) => it.path !== '/platform/currencies')
  }
  return items
})

// 「分析仪表盘」按 analytics.view 门控：有权限才显示并可点；无权限则隐藏。
const insightItems = computed<NavItem[]>(() => {
  const items: NavItem[] = []
  if (auth.hasPermission('analytics.view')) {
    items.push({
      label: '分析仪表盘',
      path: '/analytics',
      requiredPermission: 'analytics.view',
      feature: 'analytics',
      icon: DataAnalysis,
    })
  }
  items.push({ label: '通知中心', soon: true, icon: Bell })
  return items
})

const groups = computed<NavGroup[]>(() => [
  {
    label: 'SOP',
    items: [
      { label: '程序库', path: '/procedures/library', feature: 'sop', icon: Document },
      { label: '草稿箱', path: '/procedures/drafts', feature: 'sop', icon: EditPen },
      { label: '文件夹', path: '/folders', feature: 'sop', icon: Folder },
      { label: '审计日志', path: '/audit-logs', icon: List },
    ],
  },
  {
    label: '维护',
    items: [
      { label: '工单', path: '/maintenance/work-orders', icon: Tickets },
      { label: '资产', path: '/maindata/assets', icon: Box },
      { label: '位置', path: '/maindata/locations', icon: Location },
      { label: '请求', path: '/maintenance/requests', icon: ChatDotRound },
      {
        label: '预防性维护',
        path: '/maintenance/preventive-maintenances',
        feature: 'preventive_maintenance',
        icon: Timer,
      },
      { label: '计量', path: '/maintenance/meters', feature: 'meters', icon: Odometer },
    ],
  },
  {
    label: '供应',
    items: [
      { label: '备件库存', path: '/inventory/parts', icon: Goods },
      { label: '采购单', path: '/inventory/purchase-orders', feature: 'purchasing', icon: ShoppingCart },
      { label: '供应商', path: '/inventory/vendors', icon: Shop },
      { label: '客户', path: '/inventory/customers', icon: Avatar },
    ],
  },
  {
    label: '洞察',
    items: insightItems.value,
  },
  {
    label: '平台',
    items: platformItems.value,
  },
  {
    label: '设置',
    items: [
      { label: '系统设置', path: '/settings', icon: Setting },
      { label: '字段管理', path: '/settings/fields', icon: Grid },
      { label: '标题字典', path: '/settings/heading-rules', icon: Collection },
    ],
  },
])

const activeMenu = computed<string>(() => {
  if (route.path.startsWith('/platform/')) return route.path
  if (route.path.startsWith('/maindata/')) return route.path
  if (route.path.startsWith('/inventory/')) return route.path
  if (route.path.startsWith('/maintenance/work-orders')) return '/maintenance/work-orders'
  if (route.path.startsWith('/maintenance/')) return route.path
  if (route.path.startsWith('/analytics')) return route.path
  if (route.path.startsWith('/procedures/drafts')) return '/procedures/drafts'
  if (route.path.startsWith('/procedures')) return '/procedures/library'
  if (route.path.startsWith('/folders')) return '/folders'
  if (route.path.startsWith('/audit-logs')) return '/audit-logs'
  if (route.path.startsWith('/settings/fields')) return '/settings/fields'
  if (route.path.startsWith('/settings/heading-rules')) return '/settings/heading-rules'
  if (route.path.startsWith('/settings')) return '/settings'
  return ''
})

defineExpose({ activeMenu, platformItems, insightItems, groups })
</script>

<template>
  <aside class="app-aside" :class="{ collapsed }">
    <el-menu
      :default-active="activeMenu"
      :collapse="collapsed"
      :collapse-transition="false"
      router
      text-color="var(--text-regular)"
      background-color="transparent"
      :style="{ '--el-menu-active-color': 'var(--accent)' }"
    >
      <template v-for="g in groups" :key="g.label">
        <div v-if="!collapsed" class="menu-group-label">{{ g.label }}</div>
        <el-menu-item
          v-for="it in g.items"
          :key="it.label"
          :index="menuIndex(it)"
          :disabled="it.soon"
        >
          <!-- 默认 slot 的图标在折叠态仍显示（#title 文字此时被 el-menu 隐藏）。 -->
          <el-icon v-if="it.icon" class="nav-icon"><component :is="it.icon" /></el-icon>
          <template #title>
            {{ it.label }}<span v-if="it.soon" class="soon-tag">即将上线</span>
            <el-icon v-else-if="isLocked(it)" class="lock-icon"><Lock /></el-icon>
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
  border-right: 1px solid var(--border-subtle);
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
  /* 菜单项超出可视高度时纵向滚动，横向裁切避免折叠动画溢出 */
  overflow-y: auto;
  overflow-x: hidden;
}
.menu-group-label {
  padding: 14px 16px 4px;
  font-size: 11px;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.soon-tag {
  margin-left: 6px;
  font-size: 10px;
  color: var(--text-disabled);
}
.lock-icon {
  margin-left: 6px;
  font-size: 12px;
  color: var(--text-disabled);
  vertical-align: middle;
}

/* 选中态：左 3px 陶土橙竖条 + accent-bg 底（design-system.md §3.2）。
   EP 默认仅给激活项换文字色，这里补足竖条与底色，强化层级辨识。 */
.app-aside :deep(.el-menu-item.is-active) {
  position: relative;
  background: var(--accent-bg);
}
.app-aside :deep(.el-menu-item.is-active)::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--accent);
}
/* hover 不盖过选中底色 */
.app-aside :deep(.el-menu-item.is-active:hover) {
  background: var(--accent-bg-hover);
}
</style>
