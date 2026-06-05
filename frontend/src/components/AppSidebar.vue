<script setup lang="ts">
import { computed, type Component } from 'vue'
import { useRoute } from 'vue-router'
import { ElIcon, ElMenu, ElMenuItem, ElSubMenu } from 'element-plus'
import {
  Lock,
  // SOP
  Document,
  EditPen,
  Folder,
  List,
  // 维护
  Tickets,
  ChatDotRound,
  Timer,
  Odometer,
  Avatar,
  // 资产
  Box,
  Location,
  // 库存采购
  Goods,
  ShoppingCart,
  Shop,
  // 分析
  DataAnalysis,
  // 管理：人员与权限
  User,
  UserFilled,
  Connection,
  // 管理：组织配置
  OfficeBuilding,
  Coin,
  // 管理：系统配置
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
  requiredPermission?: string
  // 已挂 feature gate 的高级模块对应功能码；未解锁时菜单项显示锁标。
  feature?: string
  // 折叠态侧栏只显示图标（el-menu 折叠时隐藏 #title 文字），每项必须配一个。
  icon?: Component
}
interface NavSubGroup {
  label: string
  icon?: Component
  items: NavItem[]
}
type NavEntry = NavItem | NavSubGroup
interface NavGroup {
  label: string
  entries: NavEntry[]
}

function isSubGroup(e: NavEntry): e is NavSubGroup {
  return (e as NavSubGroup).items !== undefined
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

// 货币管理仅 super_admin 可见；其余组织配置项不受限。
const orgConfigItems = computed<NavItem[]>(() => {
  const items: NavItem[] = [{ label: '公司设置', path: '/admin/company', icon: OfficeBuilding }]
  if (auth.user?.role_code === 'super_admin') {
    items.push({ label: '货币', path: '/admin/currencies', icon: Coin })
  }
  return items
})

// 「分析仪表盘」按 analytics.view 门控：有权限才显示并可点；无权限则整组隐藏。
const analyticsItems = computed<NavItem[]>(() => {
  if (auth.hasPermission('analytics.view')) {
    return [
      {
        label: '分析仪表盘',
        path: '/analytics',
        requiredPermission: 'analytics.view',
        feature: 'analytics',
        icon: DataAnalysis,
      },
    ]
  }
  return []
})

const groups = computed<NavGroup[]>(() => [
  {
    label: 'SOP',
    entries: [
      { label: '程序库', path: '/procedures/library', feature: 'sop', icon: Document },
      { label: '草稿箱', path: '/procedures/drafts', feature: 'sop', icon: EditPen },
      { label: '文件夹', path: '/procedures/folders', feature: 'sop', icon: Folder },
    ],
  },
  {
    label: '维护',
    entries: [
      { label: '工单', path: '/maintenance/work-orders', icon: Tickets },
      { label: '请求', path: '/maintenance/requests', icon: ChatDotRound },
      {
        label: '预防性维护',
        path: '/maintenance/preventive-maintenances',
        feature: 'preventive_maintenance',
        icon: Timer,
      },
      { label: '计量', path: '/maintenance/meters', feature: 'meters', icon: Odometer },
      { label: '客户', path: '/maintenance/customers', icon: Avatar },
    ],
  },
  {
    label: '资产',
    entries: [
      { label: '资产', path: '/assets', icon: Box },
      { label: '位置', path: '/assets/locations', icon: Location },
    ],
  },
  {
    label: '库存采购',
    entries: [
      { label: '备件库存', path: '/inventory/parts', icon: Goods },
      {
        label: '采购单',
        path: '/inventory/purchase-orders',
        feature: 'purchasing',
        icon: ShoppingCart,
      },
      { label: '供应商', path: '/inventory/vendors', icon: Shop },
    ],
  },
  {
    label: '分析',
    entries: analyticsItems.value,
  },
  {
    label: '管理',
    entries: [
      {
        label: '人员与权限',
        icon: User,
        items: [
          { label: '用户', path: '/admin/users', icon: User },
          { label: '角色', path: '/admin/roles', icon: UserFilled },
          { label: '团队', path: '/admin/teams', icon: Connection },
        ],
      },
      { label: '组织配置', icon: OfficeBuilding, items: orgConfigItems.value },
      {
        label: '系统配置',
        icon: Setting,
        items: [
          { label: '系统设置', path: '/admin/settings', icon: Setting },
          { label: '字段管理', path: '/admin/fields', icon: Grid },
          { label: '标题字典', path: '/admin/heading-rules', icon: Collection },
        ],
      },
      {
        label: '审计',
        icon: List,
        items: [{ label: '审计日志', path: '/admin/audit-logs', icon: List }],
      },
    ],
  },
])

const activeMenu = computed<string>(() => {
  const p = route.path
  if (p.startsWith('/admin/')) return p
  if (p.startsWith('/assets/locations')) return '/assets/locations'
  if (p.startsWith('/assets')) return '/assets'
  if (p.startsWith('/inventory/parts')) return '/inventory/parts'
  if (p.startsWith('/inventory/')) return p
  if (p.startsWith('/maintenance/work-orders')) return '/maintenance/work-orders'
  if (p.startsWith('/maintenance/')) return p
  if (p.startsWith('/analytics')) return '/analytics'
  if (p.startsWith('/procedures/drafts')) return '/procedures/drafts'
  if (p.startsWith('/procedures/folders')) return '/procedures/folders'
  if (p.startsWith('/procedures')) return '/procedures/library'
  return ''
})

defineExpose({ activeMenu, groups })
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
        <div v-if="!collapsed && g.entries.length" class="menu-group-label">{{ g.label }}</div>
        <template v-for="entry in g.entries" :key="entry.label">
          <el-sub-menu v-if="isSubGroup(entry)" :index="`grp:${entry.label}`">
            <template #title>
              <el-icon v-if="entry.icon" class="nav-icon"><component :is="entry.icon" /></el-icon>
              <span>{{ entry.label }}</span>
            </template>
            <el-menu-item v-for="it in entry.items" :key="it.label" :index="menuIndex(it)">
              <el-icon v-if="it.icon" class="nav-icon"><component :is="it.icon" /></el-icon>
              <template #title>
                {{ it.label }}
                <el-icon v-if="isLocked(it)" class="lock-icon"><Lock /></el-icon>
              </template>
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item v-else :index="menuIndex(entry)">
            <!-- 默认 slot 的图标在折叠态仍显示（#title 文字此时被 el-menu 隐藏）。 -->
            <el-icon v-if="entry.icon" class="nav-icon"><component :is="entry.icon" /></el-icon>
            <template #title>
              {{ entry.label }}
              <el-icon v-if="isLocked(entry)" class="lock-icon"><Lock /></el-icon>
            </template>
          </el-menu-item>
        </template>
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
.lock-icon {
  margin-left: 6px;
  font-size: 12px;
  color: var(--text-disabled);
  vertical-align: middle;
}

/* 选中态：左 3px 陶土橙竖条 + accent-bg 底（design-system.md §3.2）。
   EP 默认仅给激活项换文字色，这里补足竖条与底色，强化层级辨识。
   :deep 选择器同样覆盖 el-sub-menu 内嵌的激活叶子项。 */
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
