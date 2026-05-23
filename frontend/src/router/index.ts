import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/procedures/library' },
  {
    path: '/procedures/library',
    name: 'procedure-library',
    component: () => import('@/views/procedures/ProcedureLibraryView.vue'),
    meta: { title: '程序库' },
  },
  {
    path: '/procedures/drafts',
    name: 'procedure-drafts',
    component: () => import('@/views/procedures/ProcedureDraftsView.vue'),
    meta: { title: '草稿箱' },
  },
  {
    path: '/procedures/import',
    name: 'procedure-import',
    component: () => import('@/views/procedures/ImportWizardView.vue'),
    meta: { title: '导入程序' },
  },
  {
    path: '/procedures/import-v2',
    name: 'procedure-import-v2',
    component: () => import('@/views/procedures/ImportDialogView.vue'),
    meta: { title: '导入程序 (v2)' },
  },
  {
    path: '/procedures/:id/edit',
    name: 'procedure-edit',
    component: () => import('@/views/procedures/ProcedureEditorView.vue'),
    meta: { title: '编辑程序' },
  },
  {
    path: '/procedures/:id/view',
    name: 'procedure-view',
    component: () => import('@/views/procedures/ProcedureEditorView.vue'),
    meta: { title: '查看程序' },
  },
  {
    path: '/procedures/:id',
    name: 'procedure-detail',
    component: () => import('@/views/procedures/ProcedureDetailView.vue'),
    meta: { title: '程序详情' },
  },
  {
    path: '/folders',
    name: 'folder-manage',
    component: () => import('@/views/folders/FolderManageView.vue'),
    meta: { title: '标准文件库' },
  },
  {
    path: '/audit-logs',
    name: 'audit-logs',
    component: () => import('@/views/audit/AuditLogsView.vue'),
    meta: { title: '审计日志' },
  },
  {
    path: '/settings',
    name: 'global-settings',
    component: () => import('@/views/settings/SettingsView.vue'),
    meta: { title: '系统设置' },
  },
  {
    path: '/settings/fields',
    name: 'field-manage',
    component: () => import('@/views/settings/FieldManageView.vue'),
    meta: { title: '字段管理' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
