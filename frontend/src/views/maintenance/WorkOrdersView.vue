<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listWorkOrders, deleteWorkOrder } from '@/api/workOrders'
import type { ListWorkOrdersParams } from '@/api/workOrders'
import { listAssetsMini } from '@/api/assets'
import { listLocationsMini } from '@/api/locations'
import { listUsers } from '@/api/users'
import WorkOrderFormDialog from '@/components/workorder/WorkOrderFormDialog.vue'
import WorkOrderCategoryManageDialog from '@/components/maintenance/WorkOrderCategoryManageDialog.vue'
import { useAuthStore } from '@/store/auth'
import { formatDate } from '@/utils/format'
import type { WorkOrderRead, WorkOrderStatus, WorkOrderPriority } from '@/types/workOrder'
import type { AssetMini, LocationMini } from '@/types/maindata'
import type { UserRead } from '@/types/platform'

const router = useRouter()
const auth = useAuthStore()

// ── mappings ───────────────────────────────────────────────
const WO_STATUS_LABELS: Record<WorkOrderStatus, string> = {
  OPEN: '待处理',
  IN_PROGRESS: '进行中',
  ON_HOLD: '挂起',
  COMPLETE: '已完成',
  CANCELED: '已取消',
}
const WO_STATUS_TAG: Record<WorkOrderStatus, string> = {
  OPEN: 'info',
  IN_PROGRESS: 'primary',
  ON_HOLD: 'warning',
  COMPLETE: 'success',
  CANCELED: 'info',
}
const PRIORITY_LABELS: Record<WorkOrderPriority, string> = {
  NONE: '无',
  LOW: '低',
  MEDIUM: '中',
  HIGH: '高',
}

const WO_STATUS_OPTIONS = (Object.keys(WO_STATUS_LABELS) as WorkOrderStatus[]).map((v) => ({
  value: v,
  label: WO_STATUS_LABELS[v],
}))
const PRIORITY_OPTIONS = (Object.keys(PRIORITY_LABELS) as WorkOrderPriority[]).map((v) => ({
  value: v,
  label: PRIORITY_LABELS[v],
}))

function statusLabel(s: WorkOrderStatus): string {
  return WO_STATUS_LABELS[s]
}
function statusTag(s: WorkOrderStatus): string {
  return WO_STATUS_TAG[s]
}
function priorityLabel(p: WorkOrderPriority): string {
  return PRIORITY_LABELS[p]
}

// ── state ──────────────────────────────────────────────────
const loading = ref(false)
const workOrders = ref<WorkOrderRead[]>([])
const assetsMini = ref<AssetMini[]>([])
const locationsMini = ref<LocationMini[]>([])
const users = ref<UserRead[]>([])

const filterStatus = ref<WorkOrderStatus | ''>('')
const filterPriority = ref<WorkOrderPriority | ''>('')
const filterAsset = ref('')
const filterLocation = ref('')
const filterAssignee = ref('')
const filterProcedure = ref<'' | 'true' | 'false'>('')

// ── dialog state ───────────────────────────────────────────
const formVisible = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const editingWO = ref<WorkOrderRead | null>(null)
const categoryDialogVisible = ref(false)

// ── mapping helpers ────────────────────────────────────────
function assetName(id: string | null): string {
  if (!id) return '—'
  const a = assetsMini.value.find((x) => x.id === id)
  return a ? a.name : '—'
}
function locationName(id: string | null): string {
  if (!id) return '—'
  const l = locationsMini.value.find((x) => x.id === id)
  return l ? l.name : '—'
}
function userName(id: string | null): string {
  if (!id) return '—'
  const u = users.value.find((x) => x.id === id)
  return u ? u.name : '—'
}

// ── fetch ──────────────────────────────────────────────────
async function fetchWorkOrders() {
  loading.value = true
  try {
    const params: ListWorkOrdersParams = {}
    if (filterStatus.value) params.status = filterStatus.value
    if (filterPriority.value) params.priority = filterPriority.value
    if (filterAsset.value) params.asset_id = filterAsset.value
    if (filterLocation.value) params.location_id = filterLocation.value
    if (filterAssignee.value) params.assignee_id = filterAssignee.value
    if (filterProcedure.value) params.procedure_attached = filterProcedure.value === 'true'
    workOrders.value = await listWorkOrders(params)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await Promise.all([
    fetchWorkOrders(),
    listAssetsMini().then((v) => (assetsMini.value = v)),
    listLocationsMini().then((v) => (locationsMini.value = v)),
    listUsers().then((v) => (users.value = v)),
  ])
})

// ── actions ────────────────────────────────────────────────
function openCreate() {
  editingWO.value = null
  formMode.value = 'create'
  formVisible.value = true
}

function openEdit(row: WorkOrderRead) {
  editingWO.value = row
  formMode.value = 'edit'
  formVisible.value = true
}

function goDetail(row: WorkOrderRead) {
  router.push('/maintenance/work-orders/' + row.id)
}

async function handleDelete(row: WorkOrderRead) {
  try {
    await ElMessageBox.confirm(`确认删除工单「${row.custom_id}」？`, '提示', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteWorkOrder(row.id)
    ElMessage.success('已删除')
    await fetchWorkOrders()
  } catch {
    // cancelled or error handled by interceptor
  }
}

defineExpose({ openCreate, goDetail, handleDelete, fetchWorkOrders, filterStatus, filterProcedure })
</script>

<template>
  <div class="page">
    <h2 class="page-title">工单管理</h2>

    <!-- toolbar -->
    <div class="toolbar">
      <el-button v-if="auth.hasPermission('work_order.create')" type="primary" @click="openCreate">
        新建工单
      </el-button>
      <el-button
        v-if="auth.hasPermission('work_order_category.view')"
        @click="categoryDialogVisible = true"
      >
        管理分类
      </el-button>
      <el-select
        v-model="filterStatus"
        placeholder="按状态筛选"
        clearable
        style="width: 160px"
        @change="fetchWorkOrders"
      >
        <el-option
          v-for="s in WO_STATUS_OPTIONS"
          :key="s.value"
          :label="s.label"
          :value="s.value"
        />
      </el-select>
      <el-select
        v-model="filterPriority"
        placeholder="按优先级筛选"
        clearable
        style="width: 160px"
        @change="fetchWorkOrders"
      >
        <el-option v-for="p in PRIORITY_OPTIONS" :key="p.value" :label="p.label" :value="p.value" />
      </el-select>
      <el-select
        v-model="filterAsset"
        placeholder="按资产筛选"
        clearable
        filterable
        style="width: 200px"
        @change="fetchWorkOrders"
      >
        <el-option v-for="a in assetsMini" :key="a.id" :label="a.name" :value="a.id" />
      </el-select>
      <el-select
        v-model="filterLocation"
        placeholder="按位置筛选"
        clearable
        filterable
        style="width: 200px"
        @change="fetchWorkOrders"
      >
        <el-option v-for="l in locationsMini" :key="l.id" :label="l.name" :value="l.id" />
      </el-select>
      <el-select
        v-model="filterAssignee"
        placeholder="按负责人筛选"
        clearable
        filterable
        style="width: 160px"
        @change="fetchWorkOrders"
      >
        <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
      </el-select>
      <el-select
        v-model="filterProcedure"
        placeholder="SOP 挂接"
        clearable
        style="width: 140px"
        @change="fetchWorkOrders"
      >
        <el-option label="已挂接" value="true" />
        <el-option label="未挂接" value="false" />
      </el-select>
    </div>

    <!-- work orders table -->
    <el-table
      v-loading="loading"
      :data="workOrders"
      row-key="id"
      border
      style="width: 100%; margin-top: 16px"
    >
      <el-table-column prop="custom_id" label="编号" min-width="110" />
      <el-table-column prop="title" label="标题" min-width="160" />
      <el-table-column label="状态" min-width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.status)">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="优先级" min-width="90" align="center">
        <template #default="{ row }">{{ priorityLabel(row.priority) }}</template>
      </el-table-column>
      <el-table-column label="资产" min-width="140">
        <template #default="{ row }">{{ assetName(row.asset_id) }}</template>
      </el-table-column>
      <el-table-column label="位置" min-width="140">
        <template #default="{ row }">{{ locationName(row.location_id) }}</template>
      </el-table-column>
      <el-table-column label="负责人" min-width="120">
        <template #default="{ row }">{{ userName(row.primary_user_id) }}</template>
      </el-table-column>
      <el-table-column label="到期" min-width="120">
        <template #default="{ row }">{{ row.due_date ? formatDate(row.due_date) : '—' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="220" align="center" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="goDetail(row)">详情</el-button>
          <el-button
            v-if="auth.hasPermission('work_order.edit')"
            link
            type="primary"
            @click="openEdit(row)"
          >
            编辑
          </el-button>
          <el-button
            v-if="auth.hasPermission('work_order.delete')"
            link
            type="danger"
            @click="handleDelete(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- form dialog -->
    <WorkOrderFormDialog
      v-model:visible="formVisible"
      :mode="formMode"
      :editing="editingWO"
      @saved="fetchWorkOrders"
    />

    <!-- category manage dialog -->
    <WorkOrderCategoryManageDialog v-model:visible="categoryDialogVisible" />
  </div>
</template>

<style scoped>
.page {
  max-width: 1200px;
  padding: 20px 24px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 20px;
  color: var(--text-primary, #1a1a1a);
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
</style>
