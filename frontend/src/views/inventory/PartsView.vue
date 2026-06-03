<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listParts, createPart, updatePart, deletePart } from '@/api/parts'
import { listPartCategories } from '@/api/partCategories'
import { listAssetsMini } from '@/api/assets'
import { listLocationsMini } from '@/api/locations'
import { listUsers } from '@/api/users'
import { listTeams } from '@/api/teams'
import PartCategoryManageDialog from '@/components/inventory/PartCategoryManageDialog.vue'
import type { PartRead, PartCreate, PartUpdate, PartCategoryRead } from '@/types/inventory'
import type { AssetMini, LocationMini } from '@/types/maindata'
import type { UserRead, TeamRead } from '@/types/platform'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()

// ── state ──────────────────────────────────────────────────
const loading = ref(false)
const parts = ref<PartRead[]>([])
const categories = ref<PartCategoryRead[]>([])
const assetsMini = ref<AssetMini[]>([])
const locationsMini = ref<LocationMini[]>([])
const users = ref<UserRead[]>([])
const teams = ref<TeamRead[]>([])
const lowStockOnly = ref(false)

const categoryDialogVisible = ref(false)

// ── fetch ──────────────────────────────────────────────────
async function fetchParts() {
  loading.value = true
  try {
    parts.value = await listParts(lowStockOnly.value ? { low_stock: true } : {})
  } finally {
    loading.value = false
  }
}

async function fetchCategories() {
  categories.value = await listPartCategories()
}

async function fetchAssetsMini() {
  assetsMini.value = await listAssetsMini()
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

onMounted(async () => {
  await Promise.all([
    fetchParts(),
    fetchCategories(),
    fetchAssetsMini(),
    fetchLocationsMini(),
    fetchUsers(),
    fetchTeams(),
  ])
})

// ── mapping ────────────────────────────────────────────────
function categoryName(id: string | null): string {
  if (!id) return '—'
  const c = categories.value.find((x) => x.id === id)
  return c ? c.name : '—'
}

// ── dialog ─────────────────────────────────────────────────
type DialogMode = 'create' | 'edit'

const dialogVisible = ref(false)
const dialogMode = ref<DialogMode>('create')
const editingId = ref<string | null>(null)
const submitting = ref(false)

interface FormState {
  name: string
  description: string
  cost: string
  quantity: string
  min_quantity: string
  unit: string
  barcode: string
  non_stock: boolean
  category_id: string | null
  assignee_ids: string[]
  team_ids: string[]
  asset_ids: string[]
  location_ids: string[]
}

const form = reactive<FormState>({
  name: '',
  description: '',
  cost: '',
  quantity: '',
  min_quantity: '',
  unit: '',
  barcode: '',
  non_stock: false,
  category_id: null,
  assignee_ids: [],
  team_ids: [],
  asset_ids: [],
  location_ids: [],
})

const dialogTitle = computed(() => (dialogMode.value === 'create' ? '新建备件' : '编辑备件'))

function resetForm() {
  form.name = ''
  form.description = ''
  form.cost = ''
  form.quantity = ''
  form.min_quantity = ''
  form.unit = ''
  form.barcode = ''
  form.non_stock = false
  form.category_id = null
  form.assignee_ids = []
  form.team_ids = []
  form.asset_ids = []
  form.location_ids = []
}

function openCreate() {
  resetForm()
  dialogMode.value = 'create'
  editingId.value = null
  dialogVisible.value = true
}

function openEdit(row: PartRead) {
  resetForm()
  Object.assign(form, {
    name: row.name,
    description: row.description,
    cost: row.cost,
    quantity: row.quantity,
    min_quantity: row.min_quantity,
    unit: row.unit,
    barcode: row.barcode ?? '',
    non_stock: row.non_stock,
    category_id: row.category_id,
    assignee_ids: [...row.assignee_ids],
    team_ids: [...row.team_ids],
    asset_ids: [...row.asset_ids],
    location_ids: [...row.location_ids],
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
    const payload: PartCreate | PartUpdate = {
      name: form.name.trim(),
      description: form.description,
      cost: form.cost || '0',
      quantity: form.quantity || '0',
      min_quantity: form.min_quantity || '0',
      unit: form.unit,
      barcode: form.barcode || null,
      non_stock: form.non_stock,
      category_id: form.category_id,
      assignee_ids: form.assignee_ids,
      team_ids: form.team_ids,
      asset_ids: form.asset_ids,
      location_ids: form.location_ids,
    }
    if (dialogMode.value === 'create') {
      await createPart(payload as PartCreate)
      ElMessage.success('备件创建成功')
    } else {
      if (!editingId.value) return
      await updatePart(editingId.value, payload)
      ElMessage.success('备件更新成功')
    }
    dialogVisible.value = false
    await fetchParts()
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    submitting.value = false
  }
}

// ── delete ─────────────────────────────────────────────────
async function handleDelete(row: PartRead) {
  try {
    await ElMessageBox.confirm(`确认删除备件「${row.name}」？`, '提示', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deletePart(row.id)
    ElMessage.success('已删除')
    await fetchParts()
  } catch {
    // cancelled or error handled by interceptor
  }
}
</script>

<template>
  <div class="page">
    <h2 class="page-title">备件库存</h2>

    <!-- toolbar -->
    <div class="toolbar">
      <el-button v-if="auth.hasPermission('part.create')" type="primary" @click="openCreate">
        新建备件
      </el-button>
      <el-button
        v-if="auth.hasPermission('part_category.view')"
        @click="categoryDialogVisible = true"
      >
        管理分类
      </el-button>
      <span class="switch-label">仅看低库存</span>
      <el-switch v-model="lowStockOnly" @change="fetchParts" />
    </div>

    <!-- parts table -->
    <el-table
      v-loading="loading"
      :data="parts"
      row-key="id"
      border
      style="width: 100%; margin-top: 16px"
    >
      <el-table-column prop="custom_id" label="编号" min-width="120" />
      <el-table-column prop="name" label="名称" min-width="180" />
      <el-table-column label="分类" min-width="120">
        <template #default="{ row }">{{ categoryName(row.category_id) }}</template>
      </el-table-column>
      <el-table-column prop="quantity" label="库存数量" min-width="100" />
      <el-table-column prop="unit" label="单位" min-width="80" />
      <el-table-column prop="cost" label="单价" min-width="100" />
      <el-table-column label="低库存" min-width="100" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.is_low_stock" type="danger">低库存</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" align="center" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="auth.hasPermission('part.edit')"
            link
            type="primary"
            @click="openEdit(row)"
          >
            编辑
          </el-button>
          <el-button
            v-if="auth.hasPermission('part.delete')"
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
      <el-form label-width="120px" @submit.prevent="submitForm">
        <el-divider content-position="left">基本</el-divider>
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="请输入名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" placeholder="请输入描述" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select
            v-model="form.category_id"
            clearable
            placeholder="请选择分类"
            style="width: 100%"
          >
            <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>

        <el-divider content-position="left">库存</el-divider>
        <el-form-item label="库存数量">
          <el-input v-model="form.quantity" placeholder="直接修改即入库/校正" />
        </el-form-item>
        <el-form-item label="最低库存阈值">
          <el-input v-model="form.min_quantity" placeholder="请输入最低库存阈值" />
        </el-form-item>
        <el-form-item label="单位">
          <el-input v-model="form.unit" placeholder="请输入单位" />
        </el-form-item>
        <el-form-item label="单价">
          <el-input v-model="form.cost" placeholder="请输入单价" />
        </el-form-item>
        <el-form-item label="非库存件">
          <el-switch v-model="form.non_stock" />
        </el-form-item>

        <el-divider content-position="left">标识</el-divider>
        <el-form-item label="条码">
          <el-input v-model="form.barcode" placeholder="请输入条码" />
        </el-form-item>

        <el-divider content-position="left">关联</el-divider>
        <el-form-item label="负责人">
          <el-select
            v-model="form.assignee_ids"
            multiple
            filterable
            placeholder="请选择负责人"
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
        <el-form-item label="资产">
          <el-select
            v-model="form.asset_ids"
            multiple
            filterable
            placeholder="请选择资产"
            style="width: 100%"
          >
            <el-option v-for="a in assetsMini" :key="a.id" :label="a.name" :value="a.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="位置">
          <el-select
            v-model="form.location_ids"
            multiple
            placeholder="请选择位置"
            style="width: 100%"
          >
            <el-option v-for="l in locationsMini" :key="l.id" :label="l.name" :value="l.id" />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm"> 保存 </el-button>
      </template>
    </el-dialog>

    <!-- category manage dialog -->
    <PartCategoryManageDialog v-model:visible="categoryDialogVisible" @changed="fetchCategories" />
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
.switch-label {
  margin-left: 8px;
  color: var(--text-secondary, #606266);
  font-size: 14px;
}
</style>
