<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listMeters,
  getMeter,
  createMeter,
  updateMeter,
  deleteMeter,
  listReadings,
  submitReading,
  listTriggers,
  enableTrigger,
  disableTrigger,
  deleteTrigger,
} from '@/api/meters'
import type { ListMetersParams } from '@/api/meters'
import { listMeterCategories } from '@/api/meterCategories'
import { listAssetsMini } from '@/api/assets'
import { listLocationsMini } from '@/api/locations'
import { listUsers } from '@/api/users'
import MeterTriggerDialog from '@/components/maintenance/MeterTriggerDialog.vue'
import MeterCategoryManageDialog from '@/components/maintenance/MeterCategoryManageDialog.vue'
import type {
  MeterRead,
  MeterReadingRead,
  MeterCategoryRead,
  TriggerRead,
  MeterComparator,
  WorkOrderPriority,
} from '@/types/maintenance'
import type { AssetMini, LocationMini } from '@/types/maindata'
import type { UserRead } from '@/types/platform'
import { useAuthStore } from '@/store/auth'
import { formatDateTime } from '@/utils/format'

const auth = useAuthStore()

// ── label maps ─────────────────────────────────────────────
const COMPARATOR_LABELS: Record<MeterComparator, string> = {
  LESS_THAN: '小于',
  MORE_THAN: '大于',
}
const PRIORITY_LABELS: Record<WorkOrderPriority, string> = {
  NONE: '无',
  LOW: '低',
  MEDIUM: '中',
  HIGH: '高',
}
function comparatorLabel(c: MeterComparator): string {
  return COMPARATOR_LABELS[c]
}
function priorityLabel(p: WorkOrderPriority): string {
  return PRIORITY_LABELS[p]
}

// ── state ──────────────────────────────────────────────────
const loading = ref(false)
const meters = ref<MeterRead[]>([])
const assetsMini = ref<AssetMini[]>([])
const locationsMini = ref<LocationMini[]>([])
const users = ref<UserRead[]>([])
const categories = ref<MeterCategoryRead[]>([])
const filterAsset = ref('')
const filterLocation = ref('')
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
function categoryName(id: string | null): string {
  if (!id) return '—'
  const c = categories.value.find((x) => x.id === id)
  return c ? c.name : '—'
}

// ── fetch ──────────────────────────────────────────────────
async function fetchMeters() {
  loading.value = true
  try {
    const params: ListMetersParams = {}
    if (filterAsset.value) params.asset_id = filterAsset.value
    if (filterLocation.value) params.location_id = filterLocation.value
    meters.value = await listMeters(params)
  } finally {
    loading.value = false
  }
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
async function fetchCategories() {
  if (!auth.hasPermission('meter_category.view')) return
  categories.value = await listMeterCategories()
}

onMounted(async () => {
  await Promise.all([
    fetchMeters(),
    fetchAssetsMini(),
    fetchLocationsMini(),
    fetchUsers(),
    fetchCategories(),
  ])
})

// ── create / edit dialog (basic info) ──────────────────────
type MetaMode = 'create' | 'edit'

const metaVisible = ref(false)
const metaMode = ref<MetaMode>('create')
const editingId = ref<string | null>(null)
const metaSubmitting = ref(false)

interface MetaFormState {
  name: string
  unit: string
  update_frequency_days: number | null
  asset_id: string | null
  location_id: string | null
  meter_category_id: string | null
}
const metaForm = reactive<MetaFormState>({
  name: '',
  unit: '',
  update_frequency_days: null,
  asset_id: null,
  location_id: null,
  meter_category_id: null,
})

function resetMetaForm() {
  metaForm.name = ''
  metaForm.unit = ''
  metaForm.update_frequency_days = null
  metaForm.asset_id = null
  metaForm.location_id = null
  metaForm.meter_category_id = null
}

function openCreate() {
  resetMetaForm()
  metaMode.value = 'create'
  editingId.value = null
  metaVisible.value = true
}

function openEdit(row: MeterRead) {
  resetMetaForm()
  metaForm.name = row.name
  metaForm.unit = row.unit
  metaForm.update_frequency_days = row.update_frequency_days
  metaForm.asset_id = row.asset_id
  metaForm.location_id = row.location_id
  metaForm.meter_category_id = row.meter_category_id
  metaMode.value = 'edit'
  editingId.value = row.id
  metaVisible.value = true
}

async function submitMeta() {
  if (!metaForm.name.trim()) {
    ElMessage.warning('请填写名称')
    return
  }
  const payload = {
    name: metaForm.name.trim(),
    unit: metaForm.unit,
    update_frequency_days: metaForm.update_frequency_days,
    asset_id: metaForm.asset_id || null,
    location_id: metaForm.location_id || null,
    meter_category_id: metaForm.meter_category_id || null,
  }
  metaSubmitting.value = true
  try {
    if (metaMode.value === 'create') {
      await createMeter(payload)
    } else {
      if (!editingId.value) return
      await updateMeter(editingId.value, payload)
    }
    ElMessage.success('保存成功')
    metaVisible.value = false
    await fetchMeters()
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    metaSubmitting.value = false
  }
}

// ── detail dialog ──────────────────────────────────────────
const detailVisible = ref(false)
const detailMeter = ref<MeterRead | null>(null)
const readings = ref<MeterReadingRead[]>([])
const triggers = ref<TriggerRead[]>([])
const readingValue = ref('')
const readingAt = ref<string | null>(null)
const readingSubmitting = ref(false)

// nested trigger dialog
const triggerDialogVisible = ref(false)
const editingTrigger = ref<TriggerRead | null>(null)

async function openDetail(row: MeterRead) {
  try {
    detailMeter.value = await getMeter(row.id)
    readings.value = await listReadings(row.id)
    triggers.value = await listTriggers(row.id)
    readingValue.value = ''
    readingAt.value = null
    detailVisible.value = true
  } catch {
    ElMessage.error('加载计量详情失败，请重试')
  }
}

async function handleSubmitReading() {
  if (!detailMeter.value) return
  if (!readingValue.value.trim()) {
    ElMessage.warning('请输入读数值')
    return
  }
  readingSubmitting.value = true
  try {
    const res = await submitReading(detailMeter.value.id, {
      value: readingValue.value.trim(),
      reading_at: readingAt.value || null,
    })
    if (res.generated_work_order_ids.length) {
      ElMessage.success(`本次读数触发 ${res.generated_work_order_ids.length} 张工单`)
    } else {
      ElMessage.success('读数已记录')
    }
    readingValue.value = ''
    readingAt.value = null
    readings.value = await listReadings(detailMeter.value.id)
    triggers.value = await listTriggers(detailMeter.value.id)
  } catch {
    ElMessage.error('提交失败，请重试')
  } finally {
    readingSubmitting.value = false
  }
}

// ── trigger row operations ─────────────────────────────────
function openTriggerCreate() {
  editingTrigger.value = null
  triggerDialogVisible.value = true
}
function openTriggerEdit(t: TriggerRead) {
  editingTrigger.value = t
  triggerDialogVisible.value = true
}
async function onTriggerSaved() {
  if (detailMeter.value) triggers.value = await listTriggers(detailMeter.value.id)
}
async function toggleTrigger(t: TriggerRead) {
  if (!detailMeter.value) return
  try {
    if (t.is_enabled) {
      await disableTrigger(detailMeter.value.id, t.id)
    } else {
      await enableTrigger(detailMeter.value.id, t.id)
    }
    triggers.value = await listTriggers(detailMeter.value.id)
  } catch {
    ElMessage.error('操作失败，请重试')
  }
}
async function deleteTriggerRow(t: TriggerRead) {
  if (!detailMeter.value) return
  try {
    await ElMessageBox.confirm(`确认删除触发器「${t.name}」？`, '提示', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteTrigger(detailMeter.value.id, t.id)
    triggers.value = await listTriggers(detailMeter.value.id)
  } catch {
    // cancelled or error handled by interceptor
  }
}

// ── delete meter ───────────────────────────────────────────
async function handleDelete(row: MeterRead) {
  try {
    await ElMessageBox.confirm(`确认删除计量「${row.custom_id}」？`, '提示', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteMeter(row.id)
    ElMessage.success('已删除')
    await fetchMeters()
  } catch {
    // cancelled or error handled by interceptor
  }
}

// expose for tests (drive detail / readings / dialogs directly)
defineExpose({
  openDetail,
  handleSubmitReading,
  readingValue,
  openCreate,
  openEdit,
  metaForm,
  categories,
  categoryDialogVisible,
})
</script>

<template>
  <div class="page">
    <h2 class="page-title">计量</h2>

    <!-- toolbar -->
    <div class="toolbar">
      <el-button v-if="auth.hasPermission('meter.create')" type="primary" @click="openCreate">
        新建计量
      </el-button>
      <el-button
        v-if="auth.hasPermission('meter_category.view')"
        @click="categoryDialogVisible = true"
      >
        管理分类
      </el-button>
      <el-select
        v-model="filterAsset"
        placeholder="按资产筛选"
        clearable
        filterable
        style="width: 200px"
        @change="fetchMeters"
      >
        <el-option v-for="a in assetsMini" :key="a.id" :label="a.name" :value="a.id" />
      </el-select>
      <el-select
        v-model="filterLocation"
        placeholder="按位置筛选"
        clearable
        filterable
        style="width: 200px"
        @change="fetchMeters"
      >
        <el-option v-for="l in locationsMini" :key="l.id" :label="l.name" :value="l.id" />
      </el-select>
    </div>

    <!-- meters table -->
    <el-table
      v-loading="loading"
      :data="meters"
      row-key="id"
      border
      style="width: 100%; margin-top: 16px"
    >
      <el-table-column prop="custom_id" label="编号" min-width="120" />
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column prop="unit" label="单位" min-width="90" />
      <el-table-column label="资产" min-width="140">
        <template #default="{ row }">{{ assetName(row.asset_id) }}</template>
      </el-table-column>
      <el-table-column label="位置" min-width="140">
        <template #default="{ row }">{{ locationName(row.location_id) }}</template>
      </el-table-column>
      <el-table-column label="分类" min-width="120">
        <template #default="{ row }">{{ categoryName(row.meter_category_id) }}</template>
      </el-table-column>
      <el-table-column label="推荐频率" min-width="100" align="center">
        <template #default="{ row }">{{ row.update_frequency_days ?? '—' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="160" align="center" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情/编辑</el-button>
          <el-button
            v-if="auth.hasPermission('meter.delete')"
            link
            type="danger"
            @click="handleDelete(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- create / edit basic info dialog -->
    <el-dialog
      v-model="metaVisible"
      :title="metaMode === 'create' ? '新建计量' : '编辑计量'"
      width="560px"
      :close-on-click-modal="false"
    >
      <el-form label-width="120px" @submit.prevent="submitMeta">
        <el-form-item label="名称" required>
          <el-input v-model="metaForm.name" placeholder="请输入名称" />
        </el-form-item>
        <el-form-item label="单位">
          <el-input v-model="metaForm.unit" placeholder="请输入单位" />
        </el-form-item>
        <el-form-item label="推荐更新频率(天)">
          <el-input-number
            v-model="metaForm.update_frequency_days"
            :min="1"
            controls-position="right"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="资产">
          <el-select
            v-model="metaForm.asset_id"
            placeholder="请选择资产"
            clearable
            filterable
            style="width: 100%"
          >
            <el-option v-for="a in assetsMini" :key="a.id" :label="a.name" :value="a.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="位置">
          <el-select
            v-model="metaForm.location_id"
            placeholder="请选择位置"
            clearable
            filterable
            style="width: 100%"
          >
            <el-option v-for="l in locationsMini" :key="l.id" :label="l.name" :value="l.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="auth.hasPermission('meter_category.view')" label="分类">
          <el-select
            v-model="metaForm.meter_category_id"
            placeholder="请选择分类"
            clearable
            filterable
            style="width: 100%"
          >
            <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" :loading="metaSubmitting" @click="submitMeta">保存</el-button>
        <el-button @click="metaVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- detail dialog -->
    <el-dialog v-model="detailVisible" title="计量详情" width="900px" :close-on-click-modal="false">
      <template v-if="detailMeter">
        <!-- basic info -->
        <el-divider content-position="left">基本信息</el-divider>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="名称">{{ detailMeter.name }}</el-descriptions-item>
          <el-descriptions-item label="单位">{{ detailMeter.unit || '—' }}</el-descriptions-item>
          <el-descriptions-item label="资产">
            {{ assetName(detailMeter.asset_id) }}
          </el-descriptions-item>
          <el-descriptions-item label="位置">
            {{ locationName(detailMeter.location_id) }}
          </el-descriptions-item>
          <el-descriptions-item label="分类">
            {{ categoryName(detailMeter.meter_category_id) }}
          </el-descriptions-item>
          <el-descriptions-item label="推荐频率">
            {{ detailMeter.update_frequency_days ?? '—' }}
          </el-descriptions-item>
        </el-descriptions>

        <!-- readings history -->
        <el-divider content-position="left">读数历史</el-divider>
        <div v-if="auth.hasPermission('reading.create')" class="reading-entry">
          <el-input v-model="readingValue" placeholder="读数值" style="width: 200px" />
          <el-date-picker
            v-model="readingAt"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm:ss"
            placeholder="默认现在"
            style="width: 220px"
          />
          <el-button type="primary" :loading="readingSubmitting" @click="handleSubmitReading">
            提交读数
          </el-button>
        </div>
        <el-table :data="readings" border style="width: 100%; margin-top: 12px">
          <el-table-column prop="value" label="值" min-width="120" />
          <el-table-column label="时间" min-width="180">
            <template #default="{ row }">{{ formatDateTime(row.reading_at) }}</template>
          </el-table-column>
          <el-table-column label="记录人" min-width="120">
            <template #default="{ row }">{{ userName(row.recorded_by_user_id) }}</template>
          </el-table-column>
        </el-table>

        <!-- triggers -->
        <el-divider content-position="left">触发器</el-divider>
        <el-table :data="triggers" border style="width: 100%">
          <el-table-column prop="name" label="名称" min-width="140" />
          <el-table-column label="比较" min-width="80" align="center">
            <template #default="{ row }">{{ comparatorLabel(row.comparator) }}</template>
          </el-table-column>
          <el-table-column prop="threshold" label="阈值" min-width="90" />
          <el-table-column label="优先级" min-width="80" align="center">
            <template #default="{ row }">{{ priorityLabel(row.priority) }}</template>
          </el-table-column>
          <el-table-column label="启用" min-width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_enabled ? 'success' : 'info'">
                {{ row.is_enabled ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="武装" min-width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_armed ? 'warning' : 'info'">
                {{ row.is_armed ? '武装' : '已触发' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" align="center">
            <template #default="{ row }">
              <el-button
                v-if="auth.hasPermission('meter.edit')"
                link
                type="primary"
                @click="openTriggerEdit(row)"
              >
                编辑
              </el-button>
              <el-button
                v-if="auth.hasPermission('meter.edit')"
                link
                type="warning"
                @click="toggleTrigger(row)"
              >
                {{ row.is_enabled ? '停用' : '启用' }}
              </el-button>
              <el-button
                v-if="auth.hasPermission('meter.delete')"
                link
                type="danger"
                @click="deleteTriggerRow(row)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <div v-if="auth.hasPermission('meter.create')" class="add-trigger">
          <el-button link type="primary" @click="openTriggerCreate">+ 新增触发器</el-button>
        </div>
      </template>

      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- nested trigger create / edit dialog -->
    <MeterTriggerDialog
      v-model:visible="triggerDialogVisible"
      :meter-id="detailMeter?.id || ''"
      :editing="editingTrigger"
      @saved="onTriggerSaved"
    />

    <!-- meter category manage dialog -->
    <MeterCategoryManageDialog
      v-model:visible="categoryDialogVisible"
      @changed="fetchCategories"
    />
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
.reading-entry {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.add-trigger {
  margin-top: 8px;
}
</style>
