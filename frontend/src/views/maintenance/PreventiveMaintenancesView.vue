<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listPMs,
  createPM,
  updatePM,
  deletePM,
  enablePM,
  disablePM,
  generatePM,
  listPMActivities,
  addPMComment,
} from '@/api/preventiveMaintenances'
import type { ListPMsParams } from '@/api/preventiveMaintenances'
import { listAssetsMini } from '@/api/assets'
import { listLocationsMini } from '@/api/locations'
import { listUsers } from '@/api/users'
import { listTeams } from '@/api/teams'
import { listProceduresMini } from '@/api/procedures'
import type {
  PMRead,
  PMFrequencyUnit,
  WorkOrderPriority,
  ActivityRead,
  ProcedureMini,
} from '@/types/maintenance'
import type { AssetMini, LocationMini } from '@/types/maindata'
import type { UserRead, TeamRead } from '@/types/platform'
import { useAuthStore } from '@/store/auth'
import { formatDateTime } from '@/utils/format'

const auth = useAuthStore()

// ── mappings ───────────────────────────────────────────────
const PRIORITY_LABELS: Record<WorkOrderPriority, string> = {
  NONE: '无',
  LOW: '低',
  MEDIUM: '中',
  HIGH: '高',
}
const PRIORITY_OPTIONS = (Object.keys(PRIORITY_LABELS) as WorkOrderPriority[]).map((v) => ({
  value: v,
  label: PRIORITY_LABELS[v],
}))

const FREQUENCY_LABELS: Record<PMFrequencyUnit, string> = {
  DAY: '天',
  WEEK: '周',
  MONTH: '月',
}
const FREQUENCY_OPTIONS = (Object.keys(FREQUENCY_LABELS) as PMFrequencyUnit[]).map((v) => ({
  value: v,
  label: FREQUENCY_LABELS[v],
}))
function frequencyText(pm: PMRead): string {
  return `每 ${pm.frequency_value} ${FREQUENCY_LABELS[pm.frequency_unit]}`
}

// ── state ──────────────────────────────────────────────────
const loading = ref(false)
const pms = ref<PMRead[]>([])
const assetsMini = ref<AssetMini[]>([])
const locationsMini = ref<LocationMini[]>([])
const users = ref<UserRead[]>([])
const teams = ref<TeamRead[]>([])
const procedures = ref<ProcedureMini[]>([])

const filterEnabled = ref<'' | 'true' | 'false'>('')
const filterAsset = ref('')
const filterLocation = ref('')

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
async function fetchPMs() {
  loading.value = true
  try {
    const params: ListPMsParams = {}
    if (filterEnabled.value) params.is_enabled = filterEnabled.value === 'true'
    if (filterAsset.value) params.asset_id = filterAsset.value
    if (filterLocation.value) params.location_id = filterLocation.value
    pms.value = await listPMs(params)
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
async function fetchTeams() {
  teams.value = await listTeams()
}
async function fetchProcedures() {
  procedures.value = await listProceduresMini()
}

onMounted(async () => {
  await Promise.all([
    fetchPMs(),
    fetchAssetsMini(),
    fetchLocationsMini(),
    fetchUsers(),
    fetchTeams(),
    fetchProcedures(),
  ])
})

// ── create / edit dialog ───────────────────────────────────
type DialogMode = 'create' | 'edit'

const dialogVisible = ref(false)
const dialogMode = ref<DialogMode>('create')
const editingId = ref('')
const submitting = ref(false)
const editingNextDue = ref('')

interface FormState {
  title: string
  description: string
  priority: WorkOrderPriority
  asset_id: string | null
  location_id: string | null
  primary_user_id: string | null
  procedure_id: string | null
  start_date: string
  frequency_unit: PMFrequencyUnit
  frequency_value: number
  due_date_delay: number
  ends_on: string | null
  assignee_ids: string[]
  team_ids: string[]
}
const form = reactive<FormState>({
  title: '',
  description: '',
  priority: 'NONE',
  asset_id: null,
  location_id: null,
  primary_user_id: null,
  procedure_id: null,
  start_date: '',
  frequency_unit: 'MONTH',
  frequency_value: 1,
  due_date_delay: 0,
  ends_on: null,
  assignee_ids: [],
  team_ids: [],
})

function resetForm() {
  form.title = ''
  form.description = ''
  form.priority = 'NONE'
  form.asset_id = null
  form.location_id = null
  form.primary_user_id = null
  form.procedure_id = null
  form.start_date = ''
  form.frequency_unit = 'MONTH'
  form.frequency_value = 1
  form.due_date_delay = 0
  form.ends_on = null
  form.assignee_ids = []
  form.team_ids = []
}

function openCreate() {
  resetForm()
  dialogMode.value = 'create'
  editingId.value = ''
  editingNextDue.value = ''
  dialogVisible.value = true
}

function openEdit(row: PMRead) {
  resetForm()
  Object.assign(form, {
    title: row.title,
    description: row.description,
    priority: row.priority,
    asset_id: row.asset_id,
    location_id: row.location_id,
    primary_user_id: row.primary_user_id,
    procedure_id: row.procedure_id,
    start_date: row.start_date,
    frequency_unit: row.frequency_unit,
    frequency_value: row.frequency_value,
    due_date_delay: row.due_date_delay,
    ends_on: row.ends_on,
    assignee_ids: [...row.assignee_ids],
    team_ids: [...row.team_ids],
  })
  editingNextDue.value = row.next_due_date
  dialogMode.value = 'edit'
  editingId.value = row.id
  dialogVisible.value = true
}

async function submitForm() {
  if (!form.title.trim() || !form.start_date) {
    ElMessage.warning('请填写标题与首期日')
    return
  }
  const payload = {
    title: form.title.trim(),
    description: form.description,
    priority: form.priority,
    asset_id: form.asset_id || null,
    location_id: form.location_id || null,
    primary_user_id: form.primary_user_id || null,
    procedure_id: form.procedure_id || null,
    start_date: form.start_date,
    frequency_unit: form.frequency_unit,
    frequency_value: Number(form.frequency_value),
    due_date_delay: Number(form.due_date_delay),
    ends_on: form.ends_on || null,
    assignee_ids: form.assignee_ids,
    team_ids: form.team_ids,
  }
  try {
    submitting.value = true
    if (dialogMode.value === 'create') {
      await createPM(payload)
    } else {
      await updatePM(editingId.value, payload)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    await fetchPMs()
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    submitting.value = false
  }
}

// ── enable / disable ───────────────────────────────────────
async function toggleEnabled(row: PMRead) {
  try {
    if (row.is_enabled) {
      await disablePM(row.id)
    } else {
      await enablePM(row.id)
    }
    ElMessage.success(row.is_enabled ? '已停用' : '已启用')
    await fetchPMs()
  } catch {
    ElMessage.error('操作失败，请重试')
  }
}

// ── manual generate ────────────────────────────────────────
async function handleGenerate(row: PMRead) {
  const ok = await ElMessageBox.confirm('确认按此 PM 立即生成一张工单？', '提示', {
    type: 'warning',
  }).catch(() => '__cancel__')
  if (ok === '__cancel__') return
  try {
    await generatePM(row.id)
    ElMessage.success('已生成工单')
    await fetchPMs()
  } catch {
    ElMessage.error('操作失败，请重试')
  }
}

// ── delete ─────────────────────────────────────────────────
async function handleDelete(row: PMRead) {
  try {
    await ElMessageBox.confirm(`确认删除预防性维护「${row.custom_id}」？`, '提示', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deletePM(row.id)
    ElMessage.success('已删除')
    await fetchPMs()
  } catch {
    // cancelled or error handled by interceptor
  }
}

// ── activity timeline ──────────────────────────────────────
const activityVisible = ref(false)
const activities = ref<ActivityRead[]>([])
const activePmId = ref('')
const commentText = ref('')

async function openActivities(row: PMRead) {
  activePmId.value = row.id
  activities.value = await listPMActivities(row.id)
  commentText.value = ''
  activityVisible.value = true
}

async function submitComment() {
  if (!commentText.value.trim()) return
  try {
    await addPMComment(activePmId.value, { comment: commentText.value.trim() })
    commentText.value = ''
    activities.value = await listPMActivities(activePmId.value)
  } catch {
    ElMessage.error('操作失败，请重试')
  }
}

// expose for tests (drive dialogs / forms directly)
defineExpose({
  openCreate,
  openEdit,
  form,
  handleGenerate,
  toggleEnabled,
  openActivities,
})
</script>

<template>
  <div class="page">
    <h2 class="page-title">预防性维护</h2>

    <!-- toolbar -->
    <div class="toolbar">
      <el-button
        v-if="auth.hasPermission('preventive_maintenance.create')"
        type="primary"
        @click="openCreate"
      >
        新建预防性维护
      </el-button>
      <el-select
        v-model="filterEnabled"
        placeholder="按启用状态筛选"
        clearable
        style="width: 160px"
        @change="fetchPMs"
      >
        <el-option label="启用" value="true" />
        <el-option label="停用" value="false" />
      </el-select>
      <el-select
        v-model="filterAsset"
        placeholder="按资产筛选"
        clearable
        filterable
        style="width: 200px"
        @change="fetchPMs"
      >
        <el-option v-for="a in assetsMini" :key="a.id" :label="a.name" :value="a.id" />
      </el-select>
      <el-select
        v-model="filterLocation"
        placeholder="按位置筛选"
        clearable
        filterable
        style="width: 200px"
        @change="fetchPMs"
      >
        <el-option v-for="l in locationsMini" :key="l.id" :label="l.name" :value="l.id" />
      </el-select>
    </div>

    <!-- PM table -->
    <el-table
      v-loading="loading"
      :data="pms"
      row-key="id"
      border
      style="width: 100%; margin-top: 16px"
    >
      <el-table-column prop="custom_id" label="编号" min-width="110" />
      <el-table-column prop="title" label="标题" min-width="160" />
      <el-table-column label="资产" min-width="140">
        <template #default="{ row }">{{ assetName(row.asset_id) }}</template>
      </el-table-column>
      <el-table-column label="位置" min-width="140">
        <template #default="{ row }">{{ locationName(row.location_id) }}</template>
      </el-table-column>
      <el-table-column label="频率" min-width="110">
        <template #default="{ row }">{{ frequencyText(row) }}</template>
      </el-table-column>
      <el-table-column label="下次到期" min-width="120">
        <template #default="{ row }">{{ row.next_due_date }}</template>
      </el-table-column>
      <el-table-column label="状态" min-width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.is_enabled ? 'success' : 'info'">
            {{ row.is_enabled ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="工单" min-width="120" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.last_work_order_id" type="info">已生成工单</el-tag>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="320" align="center" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="auth.hasPermission('preventive_maintenance.edit')"
            link
            type="primary"
            @click="openEdit(row)"
          >
            编辑
          </el-button>
          <el-button
            v-if="auth.hasPermission('preventive_maintenance.edit')"
            link
            :type="row.is_enabled ? 'warning' : 'success'"
            @click="toggleEnabled(row)"
          >
            {{ row.is_enabled ? '停用' : '启用' }}
          </el-button>
          <el-button
            v-if="auth.hasPermission('preventive_maintenance.create')"
            link
            type="primary"
            @click="handleGenerate(row)"
          >
            手动生成
          </el-button>
          <el-button link type="primary" @click="openActivities(row)">活动</el-button>
          <el-button
            v-if="auth.hasPermission('preventive_maintenance.delete')"
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
      :title="dialogMode === 'create' ? '新建预防性维护' : '编辑预防性维护'"
      width="640px"
      :close-on-click-modal="false"
    >
      <el-form label-width="90px" @submit.prevent="submitForm">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" placeholder="请输入标题" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" placeholder="请输入描述" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="form.priority" style="width: 100%">
            <el-option
              v-for="p in PRIORITY_OPTIONS"
              :key="p.value"
              :label="p.label"
              :value="p.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="资产">
          <el-select
            v-model="form.asset_id"
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
            v-model="form.location_id"
            placeholder="请选择位置"
            clearable
            filterable
            style="width: 100%"
          >
            <el-option v-for="l in locationsMini" :key="l.id" :label="l.name" :value="l.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="负责人">
          <el-select
            v-model="form.primary_user_id"
            placeholder="请选择负责人"
            clearable
            filterable
            style="width: 100%"
          >
            <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="协办人">
          <el-select
            v-model="form.assignee_ids"
            placeholder="请选择协办人"
            multiple
            filterable
            style="width: 100%"
          >
            <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="团队">
          <el-select v-model="form.team_ids" placeholder="请选择团队" multiple style="width: 100%">
            <el-option v-for="t in teams" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="关联程序">
          <el-select
            v-model="form.procedure_id"
            placeholder="请选择程序"
            clearable
            filterable
            style="width: 100%"
          >
            <el-option v-for="pr in procedures" :key="pr.id" :label="pr.name" :value="pr.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="首期日" required>
          <el-date-picker
            v-model="form.start_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="请选择首期日"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="频率单位">
          <el-select v-model="form.frequency_unit" style="width: 100%">
            <el-option
              v-for="f in FREQUENCY_OPTIONS"
              :key="f.value"
              :label="f.label"
              :value="f.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="频率值">
          <el-input-number v-model="form.frequency_value" :min="1" />
        </el-form-item>
        <el-form-item label="到期日延迟(天)">
          <el-input-number v-model="form.due_date_delay" :min="0" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker
            v-model="form.ends_on"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="可选：排程结束后停止生单"
            clearable
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item v-if="dialogMode === 'edit'" label="下次到期">
          <span>{{ editingNextDue }}</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
        <el-button @click="dialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- activity dialog -->
    <el-dialog v-model="activityVisible" title="活动时间线" width="600px">
      <el-timeline>
        <el-timeline-item
          v-for="a in activities"
          :key="a.id"
          :timestamp="formatDateTime(a.created_at)"
        >
          <span v-if="a.actor_user_id">{{ userName(a.actor_user_id) }}：</span>
          {{ a.comment || a.activity_type }}
        </el-timeline-item>
      </el-timeline>
      <div class="comment-box">
        <el-input v-model="commentText" type="textarea" placeholder="请输入评论" :rows="2" />
        <el-button
          v-if="auth.hasPermission('preventive_maintenance.view')"
          type="primary"
          style="margin-top: 8px"
          @click="submitComment"
        >
          发表评论
        </el-button>
      </div>
    </el-dialog>
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
.comment-box {
  margin-top: 12px;
}
</style>
