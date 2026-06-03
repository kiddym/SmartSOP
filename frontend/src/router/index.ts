import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { authGuard } from './guard'

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    requiresAuth?: boolean
    requiredPermission?: string // 预留：权限框架就位但当前守卫不强制
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/auth/LoginView.vue'),
    meta: { title: '登录' },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/auth/RegisterView.vue'),
    meta: { title: '注册' },
  },
  { path: '/', redirect: '/procedures/library' },
  {
    path: '/procedures/library',
    name: 'procedure-library',
    component: () => import('@/views/procedures/ProcedureLibraryView.vue'),
    meta: { title: '程序库', requiresAuth: true },
  },
  {
    path: '/procedures/drafts',
    name: 'procedure-drafts',
    component: () => import('@/views/procedures/ProcedureDraftsView.vue'),
    meta: { title: '草稿箱', requiresAuth: true },
  },
  {
    path: '/procedures/:id/edit',
    name: 'procedure-edit',
    component: () => import('@/views/procedures/ProcedureEditorView.vue'),
    meta: { title: '编辑程序', requiresAuth: true },
  },
  {
    path: '/procedures/:id/view',
    name: 'procedure-view',
    component: () => import('@/views/procedures/ProcedureEditorView.vue'),
    meta: { title: '查看程序', requiresAuth: true },
  },
  {
    path: '/procedures/batch-review/:jobId',
    name: 'batch-review',
    component: () => import('@/views/procedures/BatchReviewView.vue'),
    meta: { title: '批量审阅台', requiresAuth: true },
  },
  {
    path: '/procedures/:id',
    name: 'procedure-detail',
    component: () => import('@/views/procedures/ProcedureDetailView.vue'),
    meta: { title: '程序详情', requiresAuth: true },
  },
  {
    path: '/folders',
    name: 'folder-manage',
    component: () => import('@/views/folders/FolderManageView.vue'),
    meta: { title: '文件夹配置', requiresAuth: true },
  },
  {
    path: '/audit-logs',
    name: 'audit-logs',
    component: () => import('@/views/audit/AuditLogsView.vue'),
    meta: { title: '审计日志', requiresAuth: true },
  },
  {
    path: '/settings',
    name: 'global-settings',
    component: () => import('@/views/settings/SettingsView.vue'),
    meta: { title: '系统设置', requiresAuth: true },
  },
  {
    path: '/settings/fields',
    name: 'field-manage',
    component: () => import('@/views/settings/FieldManageView.vue'),
    meta: { title: '字段管理', requiresAuth: true },
  },
  {
    path: '/settings/heading-rules',
    name: 'heading-rules',
    component: () => import('@/views/settings/HeadingRulesView.vue'),
    meta: { title: '标题字典', requiresAuth: true },
  },
  {
    path: '/platform/users',
    name: 'platform-users',
    component: () => import('@/views/platform/UsersView.vue'),
    meta: { title: '用户', requiresAuth: true, requiredPermission: 'user.view' },
  },
  {
    path: '/platform/roles',
    name: 'platform-roles',
    component: () => import('@/views/platform/RolesView.vue'),
    meta: { title: '角色', requiresAuth: true, requiredPermission: 'role.view' },
  },
  {
    path: '/platform/teams',
    name: 'platform-teams',
    component: () => import('@/views/platform/TeamsView.vue'),
    meta: { title: '团队', requiresAuth: true, requiredPermission: 'team.view' },
  },
  {
    path: '/platform/settings',
    name: 'platform-settings',
    component: () => import('@/views/platform/CompanySettingsView.vue'),
    meta: { title: '公司设置', requiresAuth: true },
  },
  {
    path: '/platform/currencies',
    name: 'platform-currencies',
    component: () => import('@/views/platform/CurrenciesView.vue'),
    meta: { title: '货币', requiresAuth: true, requiredPermission: 'currency.manage' },
  },
  {
    path: '/maindata/locations',
    name: 'maindata-locations',
    component: () => import('@/views/maindata/LocationsView.vue'),
    meta: { title: '位置', requiresAuth: true, requiredPermission: 'location.view' },
  },
  {
    path: '/maindata/assets',
    name: 'maindata-assets',
    component: () => import('@/views/maindata/AssetsView.vue'),
    meta: { title: '资产', requiresAuth: true, requiredPermission: 'asset.view' },
  },
  {
    path: '/inventory/parts',
    name: 'inventory-parts',
    component: () => import('@/views/inventory/PartsView.vue'),
    meta: { title: '备件库存', requiresAuth: true, requiredPermission: 'part.view' },
  },
  {
    path: '/inventory/purchase-orders',
    name: 'inventory-purchase-orders',
    component: () => import('@/views/inventory/PurchaseOrdersView.vue'),
    meta: { title: '采购单', requiresAuth: true, requiredPermission: 'purchase_order.view' },
  },
  {
    path: '/inventory/vendors',
    name: 'inventory-vendors',
    component: () => import('@/views/inventory/VendorsView.vue'),
    meta: { title: '供应商', requiresAuth: true, requiredPermission: 'vendor.view' },
  },
  {
    path: '/inventory/customers',
    name: 'inventory-customers',
    component: () => import('@/views/inventory/CustomersView.vue'),
    meta: { title: '客户', requiresAuth: true, requiredPermission: 'customer.view' },
  },
  {
    path: '/maintenance/requests',
    name: 'maintenance-requests',
    component: () => import('@/views/maintenance/RequestsView.vue'),
    meta: { title: '请求', requiresAuth: true, requiredPermission: 'request.view' },
  },
  {
    path: '/maintenance/preventive-maintenances',
    name: 'maintenance-preventive-maintenances',
    component: () => import('@/views/maintenance/PreventiveMaintenancesView.vue'),
    meta: {
      title: '预防性维护',
      requiresAuth: true,
      requiredPermission: 'preventive_maintenance.view',
    },
  },
  {
    path: '/maintenance/meters',
    name: 'maintenance-meters',
    component: () => import('@/views/maintenance/MetersView.vue'),
    meta: { title: '计量', requiresAuth: true, requiredPermission: 'meter.view' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(authGuard)

export default router
