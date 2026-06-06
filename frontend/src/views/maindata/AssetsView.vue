<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listAssets, createAsset, updateAsset, deleteAsset } from '@/api/assets'
import { listAssetCategories } from '@/api/assetCategories'
import { listLocationsMini } from '@/api/locations'
import { listUsers } from '@/api/users'
import { listTeams } from '@/api/teams'
import { listVendorsMini } from '@/api/vendors'
import { listCustomersMini } from '@/api/customers'
import { listPartsMini } from '@/api/parts'
import type {
  AssetRead,
  AssetCreate,
  AssetUpdate,
  AssetStatus,
  AssetCategoryRead,
  LocationMini,
} from '@/types/maindata'
import type { VendorMini, CustomerMini, PartMini } from '@/types/inventory'
import type { UserRead, TeamRead } from '@/types/platform'
import { useAuthStore } from '@/store/auth'
import { buildTree, collectDescendantIds } from '@/utils/tree'
import AssetCategoryManageDialog from '@/components/maindata/AssetCategoryManageDialog.vue'
import AssetDowntimeDialog from '@/components/maindata/AssetDowntimeDialog.vue'

const auth = useAuthStore()
const router = useRouter()

function openDetail(row: AssetRead) {
  router.push(`/assets/${row.id}`)
}

// ── status mapping ─────────────────────────────────────────
const STATUS_LABELS: Record<AssetStatus, string> = {
  OPERATIONAL: '运行中',
  STANDBY: '待机',
  MODERNIZATION: '改造中',
  INSPECTION_SCHEDULED: '待检',
  COMMISSIONING: '调试中',
  EMERGENCY_SHUTDOWN: '紧急停机',
  DOWN: '停机',
}
const UP_STATUSES = new Set<AssetStatus>([
  'OPERATIONAL',
  'STANDBY',
  'INSPECTION_SCHEDULED',
  'COMMISSIONING',
])
const STATUS_OPTIONS = (Object.keys(STATUS_LABELS) as AssetStatus[]).map((v) => ({
  value: v,
  label: STATUS_LABELS[v],
}))

function statusTagType(status: AssetStatus): 'success' | 'danger' {
  return UP_STATUSES.has(status) ? 'success' : 'danger'
}
function statusLabel(status: AssetStatus): string {
  return STATUS_LABELS[status]
}

// ── state ──────────────────────────────────────────────────
const loading = ref(false)
const assets = ref<AssetRead[]>([])
const categories = ref<AssetCategoryRead[]>([])
const locationsMini = ref<LocationMini[]>([])
const users = ref<UserRead[]>([])
const teams = ref<TeamRead[]>([])
const vendorsMini = ref<VendorMini[]>([])
const customersMini = ref<CustomerMini[]>([])
const partsMini = ref<PartMini[]>([])

const tree = computed(() => buildTree(assets.value))

function locationName(id: string | null): string {
  if (!id) return '—'
  return locationsMini.value.find((l) => l.id === id)?.name ?? '—'
}
function categoryName(id: string | null): string {
  if (!id) return '—'
  return categories.value.find((c) => c.id === id)?.name ?? '—'
}
function assetName(id: string | null): string {
  if (!id) return '—'
  return assets.value.find((a) => a.id === id)?.name ?? '—'
}

// ── fetch ──────────────────────────────────────────────────
async function fetchAssets() {
  loading.value = true
  try {
    assets.value = await listAssets()
  } finally {
    loading.value = false
  }
}
async function fetchCategories() {
  categories.value = await listAssetCategories()
}
async function fetchLocationsMini() {
  locationsMini.value = await listLocationsMini()
}
async function fetchUsers() {
  users.value = await listUsers()
}
async function fetchTeams() {
  teams.value = await listTeams()
}
async function fetchVendorsMini() {
  vendorsMini.value = await listVendorsMini()
}
async function fetchCustomersMini() {
  customersMini.value = await listCustomersMini()
}
async function fetchPartsMini() {
  partsMini.value = await listPartsMini()
}

onMounted(async () => {
  await Promise.all([
    fetchAssets(),
    fetchCategories(),
    fetchLocationsMini(),
    fetchUsers(),
    fetchTeams(),
    fetchVendorsMini(),
    fetchCustomersMini(),
    fetchPartsMini(),
  ])
})

// ── dialog ─────────────────────────────────────────────────
type DialogMode = 'create' | 'edit'

const dialogVisible = ref(false)
const dialogMode = ref<DialogMode>('create')
const editingId = ref<string | null>(null)
const submitting = ref(false)

interface FormState {
  name: string
  description: string
  parent_id: string | null
  location_id: string | null
  category_id: string | null
  status: AssetStatus
  serial_number: string
  model: string
  manufacturer: string
  power: string
  in_service_date: string
  warranty_expiration_date: string
  acquisition_cost: string
  barcode: string
  nfc_id: string
  area: string
  additional_infos: string
  image_url: string
  primary_user_id: string | null
  assigned_user_ids: string[]
  team_ids: string[]
  vendor_ids: string[]
  customer_ids: string[]
  part_ids: string[]
}

const form = reactive<FormState>({
  name: '',
  description: '',
  parent_id: null,
  location_id: null,
  category_id: null,
  status: 'OPERATIONAL',
  serial_number: '',
  model: '',
  manufacturer: '',
  power: '',
  in_service_date: '',
  warranty_expiration_date: '',
  acquisition_cost: '',
  barcode: '',
  nfc_id: '',
  area: '',
  additional_infos: '',
  image_url: '',
  primary_user_id: null,
  assigned_user_ids: [],
  team_ids: [],
  vendor_ids: [],
  customer_ids: [],
  part_ids: [],
})

const dialogTitle = computed(() => (dialogMode.value === 'create' ? '新建资产' : '编辑资产'))

// 编辑时排除自身 + 全部后代，防止成环。
const parentOptions = computed(() => {
  const excluded =
    dialogMode.value === 'edit' && editingId.value
      ? collectDescendantIds(assets.value, editingId.value)
      : new Set<string>()
  return assets.value.filter((a) => !excluded.has(a.id))
})

function resetForm() {
  form.name = ''
  form.description = ''
  form.parent_id = null
  form.location_id = null
  form.category_id = null
  form.status = 'OPERATIONAL'
  form.serial_number = ''
  form.model = ''
  form.manufacturer = ''
  form.power = ''
  form.in_service_date = ''
  form.warranty_expiration_date = ''
  form.acquisition_cost = ''
  form.barcode = ''
  form.nfc_id = ''
  form.area = ''
  form.additional_infos = ''
  form.image_url = ''
  form.primary_user_id = null
  form.assigned_user_ids = []
  form.team_ids = []
  form.vendor_ids = []
  form.customer_ids = []
  form.part_ids = []
}

function openCreate() {
  resetForm()
  dialogMode.value = 'create'
  editingId.value = null
  dialogVisible.value = true
}

function openEdit(row: AssetRead) {
  resetForm()
  Object.assign(form, {
    name: row.name,
    description: row.description,
    parent_id: row.parent_id,
    location_id: row.location_id,
    category_id: row.category_id,
    status: row.status,
    serial_number: row.serial_number,
    model: row.model,
    manufacturer: row.manufacturer,
    power: row.power,
    in_service_date: row.in_service_date ?? '',
    warranty_expiration_date: row.warranty_expiration_date ?? '',
    acquisition_cost: row.acquisition_cost ?? '',
    barcode: row.barcode ?? '',
    nfc_id: row.nfc_id ?? '',
    area: row.area ?? '',
    additional_infos: row.additional_infos ?? '',
    image_url: row.image_url ?? '',
    primary_user_id: row.primary_user_id,
    assigned_user_ids: [...row.assigned_user_ids],
    team_ids: [...row.team_ids],
    vendor_ids: [...row.vendor_ids],
    customer_ids: [...row.customer_ids],
    part_ids: [...row.part_ids],
  })
  dialogMode.value = 'edit'
  editingId.value = row.id
  dialogVisible.value = true
}

async function submitForm() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写名称')
    return
  }

  submitting.value = true
  try {
    const payload: AssetCreate | AssetUpdate = {
      name: form.name.trim(),
      description: form.description,
      parent_id: form.parent_id,
      location_id: form.location_id,
      category_id: form.category_id,
      status: form.status,
      serial_number: form.serial_number,
      model: form.model,
      manufacturer: form.manufacturer,
      power: form.power,
      in_service_date: form.in_service_date || null,
      warranty_expiration_date: form.warranty_expiration_date || null,
      acquisition_cost: form.acquisition_cost || null,
      barcode: form.barcode || null,
      nfc_id: form.nfc_id || null,
      area: form.area || null,
      additional_infos: form.additional_infos || null,
      image_url: form.image_url || null,
      primary_user_id: form.primary_user_id,
      assigned_user_ids: form.assigned_user_ids,
      team_ids: form.team_ids,
      vendor_ids: form.vendor_ids,
      customer_ids: form.customer_ids,
      part_ids: form.part_ids,
    }
    if (dialogMode.value === 'create') {
      await createAsset(payload as AssetCreate)
      ElMessage.success('资产创建成功')
    } else {
      if (!editingId.value) return
      await updateAsset(editingId.value, payload)
      ElMessage.success('资产更新成功')
    }
    dialogVisible.value = false
    await fetchAssets()
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    submitting.value = false
  }
}

// ── delete ─────────────────────────────────────────────────
async function handleDelete(row: AssetRead) {
  try {
    await ElMessageBox.confirm(`确认删除资产「${row.name}」？`, '提示', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteAsset(row.id)
    ElMessage.success('已删除')
    await fetchAssets()
  } catch {
    // cancelled or error handled by interceptor
  }
}

// ── child dialogs ──────────────────────────────────────────
const categoryDialogVisible = ref(false)

const downtimeDialogVisible = ref(false)
const downtimeAsset = ref<{ id: string; name: string } | null>(null)

function openDowntime(row: AssetRead) {
  downtimeAsset.value = { id: row.id, name: row.name }
  downtimeDialogVisible.value = true
}

// expose for tests (cycle-prevention on parentOptions, downtime entry wiring)
defineExpose({ parentOptions, openEdit, downtimeDialogVisible, downtimeAsset })
</script>

<template>
  <div class="page">
    <h2 class="page-title">资产管理</h2>

    <!-- toolbar -->
    <div class="toolbar">
      <el-button v-if="auth.hasPermission('asset.create')" type="primary" @click="openCreate">
        新建资产
      </el-button>
      <el-button
        v-if="auth.hasPermission('asset_category.view')"
        @click="categoryDialogVisible = true"
      >
        管理分类
      </el-button>
    </div>

    <!-- assets tree table -->
    <el-table
      v-loading="loading"
      :data="tree"
      row-key="id"
      :tree-props="{ children: 'children' }"
      default-expand-all
      border
      style="width: 100%; margin-top: 16px"
    >
      <el-table-column label="名称" min-width="180">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">{{ row.name }}</el-button>
        </template>
      </el-table-column>
      <el-table-column prop="custom_id" label="编号" min-width="120" />
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="位置" min-width="140">
        <template #default="{ row }">{{ locationName(row.location_id) }}</template>
      </el-table-column>
      <el-table-column label="分类" min-width="120">
        <template #default="{ row }">{{ categoryName(row.category_id) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="260" align="center" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="auth.hasPermission('asset.view')"
            link
            type="primary"
            @click="openDetail(row)"
          >
            详情
          </el-button>
          <el-button
            v-if="auth.hasPermission('asset.edit')"
            link
            type="primary"
            @click="openEdit(row)"
          >
            编辑
          </el-button>
          <el-button
            v-if="auth.hasPermission('asset.view')"
            link
            type="primary"
            @click="openDowntime(row)"
          >
            停机记录
          </el-button>
          <el-button
            v-if="auth.hasPermission('asset.delete')"
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
      width="640px"
      :close-on-click-modal="false"
    >
      <el-form label-width="90px" @submit.prevent="submitForm">
        <el-divider content-position="left">基本</el-divider>
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="请输入名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" placeholder="请输入描述" />
        </el-form-item>
        <el-form-item label="更多信息">
          <el-input
            v-model="form.additional_infos"
            type="textarea"
            placeholder="请输入更多信息"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" placeholder="请选择状态" style="width: 100%">
            <el-option
              v-for="o in STATUS_OPTIONS"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
          <el-text size="small" type="info">切换 运行↔停机 类状态将自动级联子资产</el-text>
        </el-form-item>

        <el-divider content-position="left">层级与归属</el-divider>
        <el-form-item label="父资产">
          <el-select
            v-model="form.parent_id"
            placeholder="请选择父资产"
            clearable
            style="width: 100%"
          >
            <el-option v-for="a in parentOptions" :key="a.id" :label="a.name" :value="a.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="位置">
          <el-select
            v-model="form.location_id"
            placeholder="请选择位置"
            clearable
            style="width: 100%"
          >
            <el-option v-for="l in locationsMini" :key="l.id" :label="l.name" :value="l.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="分类">
          <el-select
            v-model="form.category_id"
            placeholder="请选择分类"
            clearable
            style="width: 100%"
          >
            <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="区域">
          <el-input v-model="form.area" placeholder="请输入区域/库区" />
        </el-form-item>
        <el-form-item label="主图地址">
          <el-input v-model="form.image_url" placeholder="请输入主图 URL" />
        </el-form-item>

        <el-divider content-position="left">设备</el-divider>
        <el-form-item label="序列号">
          <el-input v-model="form.serial_number" placeholder="请输入序列号" />
        </el-form-item>
        <el-form-item label="型号">
          <el-input v-model="form.model" placeholder="请输入型号" />
        </el-form-item>
        <el-form-item label="制造商">
          <el-input v-model="form.manufacturer" placeholder="请输入制造商" />
        </el-form-item>
        <el-form-item label="功率">
          <el-input v-model="form.power" placeholder="请输入功率" />
        </el-form-item>

        <el-divider content-position="left">采购与保修</el-divider>
        <el-form-item label="购置成本">
          <el-input v-model="form.acquisition_cost" placeholder="请输入购置成本" />
        </el-form-item>
        <el-form-item label="启用日期">
          <el-date-picker
            v-model="form.in_service_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="请选择启用日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="保修到期">
          <el-date-picker
            v-model="form.warranty_expiration_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="请选择保修到期"
            style="width: 100%"
          />
        </el-form-item>

        <el-divider content-position="left">标识</el-divider>
        <el-form-item label="条码">
          <el-input v-model="form.barcode" placeholder="请输入条码" />
        </el-form-item>
        <el-form-item label="NFC">
          <el-input v-model="form.nfc_id" placeholder="请输入 NFC" />
        </el-form-item>

        <el-divider content-position="left">人员与团队</el-divider>
        <el-form-item label="主负责人">
          <el-select
            v-model="form.primary_user_id"
            placeholder="请选择主负责人"
            clearable
            filterable
            style="width: 100%"
          >
            <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="分配用户">
          <el-select
            v-model="form.assigned_user_ids"
            multiple
            filterable
            placeholder="请选择分配用户"
            style="width: 100%"
          >
            <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="团队">
          <el-select v-model="form.team_ids" multiple placeholder="请选择团队" style="width: 100%">
            <el-option v-for="t in teams" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>

        <el-divider content-position="left">关联</el-divider>
        <el-form-item label="供应商">
          <el-select
            v-model="form.vendor_ids"
            multiple
            filterable
            placeholder="请选择供应商"
            style="width: 100%"
          >
            <el-option v-for="v in vendorsMini" :key="v.id" :label="v.name" :value="v.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="客户">
          <el-select
            v-model="form.customer_ids"
            multiple
            filterable
            placeholder="请选择客户"
            style="width: 100%"
          >
            <el-option v-for="c in customersMini" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="备件">
          <el-select
            v-model="form.part_ids"
            multiple
            filterable
            placeholder="请选择备件"
            style="width: 100%"
          >
            <el-option v-for="p in partsMini" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- child dialogs -->
    <AssetCategoryManageDialog v-model:visible="categoryDialogVisible" @changed="fetchCategories" />
    <AssetDowntimeDialog
      v-model:visible="downtimeDialogVisible"
      :asset="downtimeAsset"
      :name-of="assetName"
      @changed="fetchAssets"
    />
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
</style>
