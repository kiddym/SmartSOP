<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listPurchaseOrders,
  getPurchaseOrder,
  createPurchaseOrder,
  updatePurchaseOrder,
  deletePurchaseOrder,
  submitPurchaseOrder,
  approvePurchaseOrder,
  rejectPurchaseOrder,
  cancelPurchaseOrder,
  listPurchaseOrderActivities,
} from '@/api/purchaseOrders'
import type { ListPurchaseOrdersParams } from '@/api/purchaseOrders'
import { listVendorsMini } from '@/api/vendors'
import { listPartsMini } from '@/api/parts'
import PurchaseOrderCategoryManageDialog from '@/components/inventory/PurchaseOrderCategoryManageDialog.vue'
import type {
  PurchaseOrderRead,
  PurchaseOrderStatus,
  POActivityRead,
  PartMini,
  VendorMini,
} from '@/types/inventory'
import { useAuthStore } from '@/store/auth'
import { formatDateTime } from '@/utils/format'

const auth = useAuthStore()

// ── status mapping ─────────────────────────────────────────
const STATUS_LABELS: Record<PurchaseOrderStatus, string> = {
  DRAFT: '草稿',
  SUBMITTED: '已提交',
  APPROVED: '已批准',
  REJECTED: '已驳回',
  CANCELED: '已取消',
}
const STATUS_TAG: Record<PurchaseOrderStatus, string> = {
  DRAFT: 'info',
  SUBMITTED: 'warning',
  APPROVED: 'success',
  REJECTED: 'danger',
  CANCELED: 'info',
}
const STATUS_OPTIONS = (Object.keys(STATUS_LABELS) as PurchaseOrderStatus[]).map((v) => ({
  value: v,
  label: STATUS_LABELS[v],
}))
function statusLabel(s: PurchaseOrderStatus) {
  return STATUS_LABELS[s]
}
function statusTag(s: PurchaseOrderStatus) {
  return STATUS_TAG[s]
}
function activityStatusLabel(s: string | null): string {
  if (!s) return '—'
  return STATUS_LABELS[s as PurchaseOrderStatus] ?? s
}

// ── state ──────────────────────────────────────────────────
const loading = ref(false)
const orders = ref<PurchaseOrderRead[]>([])
const vendorsMini = ref<VendorMini[]>([])
const partsMini = ref<PartMini[]>([])
const filterStatus = ref<PurchaseOrderStatus | ''>('')
const filterVendor = ref('')
const categoryDialogVisible = ref(false)

// ── mapping ────────────────────────────────────────────────
function vendorName(id: string): string {
  const v = vendorsMini.value.find((x) => x.id === id)
  return v ? v.name : '—'
}

// ── fetch ──────────────────────────────────────────────────
async function fetchOrders() {
  loading.value = true
  try {
    const params: ListPurchaseOrdersParams = {}
    if (filterStatus.value) params.status = filterStatus.value
    if (filterVendor.value) params.vendor_id = filterVendor.value
    orders.value = await listPurchaseOrders(params)
  } finally {
    loading.value = false
  }
}

async function fetchVendorsMini() {
  vendorsMini.value = await listVendorsMini()
}

async function fetchPartsMini() {
  partsMini.value = await listPartsMini()
}

onMounted(async () => {
  await Promise.all([fetchOrders(), fetchVendorsMini(), fetchPartsMini()])
})

// ── dialog ─────────────────────────────────────────────────
type DialogMode = 'create' | 'edit'

const dialogVisible = ref(false)
const dialogMode = ref<DialogMode>('create')
const editingId = ref<string | null>(null)
const editingStatus = ref<PurchaseOrderStatus>('DRAFT')
const submitting = ref(false)
const actionLoading = ref(false)
const activities = ref<POActivityRead[]>([])

interface LineForm {
  part_id: string
  quantity: string
  unit_cost: string
}
interface FormState {
  vendor_id: string
  category_id: string | null
  shipping_address: string
  shipping_method: string
  terms_of_payment: string
  expected_delivery_date: string | null
  notes: string
  lines: LineForm[]
}

const form = reactive<FormState>({
  vendor_id: '',
  category_id: null,
  shipping_address: '',
  shipping_method: '',
  terms_of_payment: '',
  expected_delivery_date: null,
  notes: '',
  lines: [],
})

const dialogTitle = computed(() => (dialogMode.value === 'create' ? '新建采购单' : '采购单详情'))

const readonly = computed(() => dialogMode.value === 'edit' && editingStatus.value !== 'DRAFT')

// ── line operations ────────────────────────────────────────
function addLine() {
  form.lines.push({ part_id: '', quantity: '1', unit_cost: '0' })
}
function removeLine(idx: number) {
  form.lines.splice(idx, 1)
}
function lineSubtotal(line: { quantity: string; unit_cost: string }): string {
  const q = Number(line.quantity) || 0
  const c = Number(line.unit_cost) || 0
  return (q * c).toFixed(2)
}

function resetForm() {
  form.vendor_id = ''
  form.category_id = null
  form.shipping_address = ''
  form.shipping_method = ''
  form.terms_of_payment = ''
  form.expected_delivery_date = null
  form.notes = ''
  form.lines = []
}

function openCreate() {
  resetForm()
  dialogMode.value = 'create'
  editingId.value = null
  editingStatus.value = 'DRAFT'
  activities.value = []
  dialogVisible.value = true
}

async function openEdit(row: PurchaseOrderRead) {
  resetForm()
  try {
    const full = await getPurchaseOrder(row.id)
    dialogMode.value = 'edit'
    editingId.value = row.id
    editingStatus.value = full.status
    Object.assign(form, {
      vendor_id: full.vendor_id,
      category_id: full.category_id,
      shipping_address: full.shipping_address,
      shipping_method: full.shipping_method,
      terms_of_payment: full.terms_of_payment,
      expected_delivery_date: full.expected_delivery_date,
      notes: full.notes,
      lines: full.lines.map((l) => ({
        part_id: l.part_id,
        quantity: l.quantity,
        unit_cost: l.unit_cost,
      })),
    })
    activities.value = await listPurchaseOrderActivities(row.id)
    dialogVisible.value = true
  } catch {
    ElMessage.error('加载采购单详情失败，请重试')
  }
}

async function submitForm() {
  if (!form.vendor_id) {
    ElMessage.warning('请选择供应商')
    return
  }

  submitting.value = true
  try {
    const payload = {
      vendor_id: form.vendor_id,
      category_id: form.category_id,
      notes: form.notes,
      shipping_address: form.shipping_address,
      shipping_method: form.shipping_method,
      terms_of_payment: form.terms_of_payment,
      expected_delivery_date: form.expected_delivery_date || null,
      lines: form.lines.map((l) => ({
        part_id: l.part_id,
        quantity: l.quantity,
        unit_cost: l.unit_cost,
      })),
    }
    if (dialogMode.value === 'create') {
      await createPurchaseOrder(payload)
      ElMessage.success('采购单创建成功')
    } else {
      if (!editingId.value) return
      await updatePurchaseOrder(editingId.value, payload)
      ElMessage.success('采购单更新成功')
    }
    dialogVisible.value = false
    await fetchOrders()
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    submitting.value = false
  }
}

// ── status transitions ─────────────────────────────────────
async function runAction(fn: () => Promise<unknown>) {
  try {
    actionLoading.value = true
    await fn()
    ElMessage.success('操作成功')
    dialogVisible.value = false
    await fetchOrders()
  } catch {
    ElMessage.error('操作失败，请重试')
  } finally {
    actionLoading.value = false
  }
}

function handleSubmit() {
  if (!editingId.value) return
  const id = editingId.value
  runAction(() => submitPurchaseOrder(id))
}

async function handleApprove() {
  if (!editingId.value) return
  const id = editingId.value
  try {
    await ElMessageBox.confirm('批准后将按明细自动入库，确认？', '提示', { type: 'warning' })
  } catch {
    return
  }
  runAction(() => approvePurchaseOrder(id, { note: '' }))
}

function handleReject() {
  if (!editingId.value) return
  const id = editingId.value
  runAction(() => rejectPurchaseOrder(id, { note: '' }))
}

function handleCancel() {
  if (!editingId.value) return
  const id = editingId.value
  runAction(() => cancelPurchaseOrder(id, { note: '' }))
}

// ── delete ─────────────────────────────────────────────────
async function handleDelete(row: PurchaseOrderRead) {
  try {
    await ElMessageBox.confirm(`确认删除采购单「${row.custom_id}」？`, '提示', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deletePurchaseOrder(row.id)
    ElMessage.success('已删除')
    await fetchOrders()
  } catch {
    // cancelled or error handled by interceptor
  }
}

// expose for tests (drive form / lines / dialogs directly)
defineExpose({ form, addLine, removeLine, openEdit, openCreate })
</script>

<template>
  <div class="page">
    <h2 class="page-title">采购单</h2>

    <!-- toolbar -->
    <div class="toolbar">
      <el-button
        v-if="auth.hasPermission('purchase_order.create')"
        type="primary"
        @click="openCreate"
      >
        新建采购单
      </el-button>
      <el-button
        v-if="auth.hasPermission('purchase_order_category.view')"
        @click="categoryDialogVisible = true"
      >
        管理分类
      </el-button>
      <el-select
        v-model="filterStatus"
        placeholder="按状态筛选"
        clearable
        style="width: 160px"
        @change="fetchOrders"
      >
        <el-option v-for="s in STATUS_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
      </el-select>
      <el-select
        v-model="filterVendor"
        placeholder="按供应商筛选"
        clearable
        filterable
        style="width: 200px"
        @change="fetchOrders"
      >
        <el-option v-for="v in vendorsMini" :key="v.id" :label="v.name" :value="v.id" />
      </el-select>
    </div>

    <!-- purchase orders table -->
    <el-table
      v-loading="loading"
      :data="orders"
      row-key="id"
      border
      style="width: 100%; margin-top: 16px"
    >
      <el-table-column prop="custom_id" label="编号" min-width="120" />
      <el-table-column label="供应商" min-width="160">
        <template #default="{ row }">{{ vendorName(row.vendor_id) }}</template>
      </el-table-column>
      <el-table-column label="状态" min-width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.status)">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="明细行数" min-width="100" align="center">
        <template #default="{ row }">{{ row.lines.length }}</template>
      </el-table-column>
      <el-table-column prop="total_cost" label="总额" min-width="100" />
      <el-table-column label="预计交付" min-width="120">
        <template #default="{ row }">{{ row.expected_delivery_date ?? '—' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="160" align="center" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="auth.hasPermission('purchase_order.view')"
            link
            type="primary"
            @click="openEdit(row)"
          >
            编辑/详情
          </el-button>
          <el-button
            v-if="auth.hasPermission('purchase_order.delete')"
            link
            type="danger"
            @click="handleDelete(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- create / edit dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="900px"
      :close-on-click-modal="false"
    >
      <el-divider content-position="left">基本信息</el-divider>
      <el-form label-width="100px" @submit.prevent="submitForm">
        <el-form-item label="供应商" required>
          <el-select
            v-model="form.vendor_id"
            placeholder="请选择供应商"
            filterable
            :disabled="readonly"
            style="width: 100%"
          >
            <el-option v-for="v in vendorsMini" :key="v.id" :label="v.name" :value="v.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="运输地址">
          <el-input
            v-model="form.shipping_address"
            placeholder="请输入运输地址"
            :disabled="readonly"
          />
        </el-form-item>
        <el-form-item label="运输方式">
          <el-input
            v-model="form.shipping_method"
            placeholder="请输入运输方式"
            :disabled="readonly"
          />
        </el-form-item>
        <el-form-item label="付款条款">
          <el-input
            v-model="form.terms_of_payment"
            placeholder="请输入付款条款"
            :disabled="readonly"
          />
        </el-form-item>
        <el-form-item label="预计交付">
          <el-date-picker
            v-model="form.expected_delivery_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="请选择预计交付日期"
            :disabled="readonly"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="form.notes"
            type="textarea"
            placeholder="请输入备注"
            :disabled="readonly"
          />
        </el-form-item>
      </el-form>

      <el-divider content-position="left">明细行</el-divider>
      <el-table :data="form.lines" border style="width: 100%">
        <el-table-column label="备件" min-width="200">
          <template #default="{ row }">
            <el-select
              v-model="row.part_id"
              placeholder="请选择备件"
              filterable
              :disabled="readonly"
              style="width: 100%"
            >
              <el-option v-for="p in partsMini" :key="p.id" :label="p.name" :value="p.id" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="数量" min-width="120">
          <template #default="{ row }">
            <el-input v-model="row.quantity" :disabled="readonly" />
          </template>
        </el-table-column>
        <el-table-column label="单价" min-width="120">
          <template #default="{ row }">
            <el-input v-model="row.unit_cost" :disabled="readonly" />
          </template>
        </el-table-column>
        <el-table-column label="小计" min-width="100">
          <template #default="{ row }">{{ lineSubtotal(row) }}</template>
        </el-table-column>
        <el-table-column v-if="!readonly" label="操作" width="90" align="center">
          <template #default="{ $index }">
            <el-button link type="danger" @click="removeLine($index)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="!readonly" class="add-line">
        <el-button link type="primary" @click="addLine">+ 添加明细行</el-button>
      </div>

      <template v-if="dialogMode === 'edit'">
        <el-divider content-position="left">活动时间线</el-divider>
        <el-timeline>
          <el-timeline-item
            v-for="a in activities"
            :key="a.id"
            :timestamp="formatDateTime(a.created_at)"
          >
            {{ activityStatusLabel(a.from_status) }} → {{ activityStatusLabel(a.to_status) }}
            <span v-if="a.comment"> {{ a.comment }}</span>
          </el-timeline-item>
        </el-timeline>
      </template>

      <template #footer>
        <el-button
          v-if="
            (dialogMode === 'create' || editingStatus === 'DRAFT') &&
            (auth.hasPermission('purchase_order.create') ||
              auth.hasPermission('purchase_order.edit'))
          "
          type="primary"
          :loading="submitting"
          @click="submitForm"
        >
          保存
        </el-button>
        <el-button
          v-if="
            dialogMode === 'edit' &&
            editingStatus === 'DRAFT' &&
            auth.hasPermission('purchase_order.edit')
          "
          type="success"
          :loading="actionLoading"
          @click="handleSubmit"
        >
          提交
        </el-button>
        <el-button
          v-if="
            dialogMode === 'edit' &&
            editingStatus === 'SUBMITTED' &&
            auth.hasPermission('purchase_order.approve')
          "
          type="success"
          :loading="actionLoading"
          @click="handleApprove"
        >
          批准
        </el-button>
        <el-button
          v-if="
            dialogMode === 'edit' &&
            editingStatus === 'SUBMITTED' &&
            auth.hasPermission('purchase_order.approve')
          "
          type="danger"
          :loading="actionLoading"
          @click="handleReject"
        >
          驳回
        </el-button>
        <el-button
          v-if="
            dialogMode === 'edit' &&
            (editingStatus === 'DRAFT' || editingStatus === 'SUBMITTED') &&
            auth.hasPermission('purchase_order.edit')
          "
          :loading="actionLoading"
          @click="handleCancel"
        >
          取消
        </el-button>
        <el-button @click="dialogVisible = false">关闭对话框</el-button>
      </template>
    </el-dialog>

    <!-- category manage dialog -->
    <PurchaseOrderCategoryManageDialog v-model:visible="categoryDialogVisible" />
  </div>
</template>

<style scoped>
.page {
  max-width: 1100px;
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
.add-line {
  margin-top: 8px;
}
</style>
