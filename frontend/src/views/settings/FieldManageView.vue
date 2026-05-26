<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Close, ArrowUp, ArrowDown } from '@element-plus/icons-vue'
import {
  listFields,
  createField,
  updateField,
  deleteField,
  updateFieldsStatus,
  batchDeleteFields,
  reorderFields,
} from '@/api/fields'
import type { FieldDetailOut, FieldCreate, FieldUpdate, FieldType, FieldOption } from '@/types/field'
import { formatDate } from '@/utils/format'

const FIELD_TYPE_LABELS: Record<string, string> = {
  text: '文本',
  number: '数字',
  date: '日期',
  select: '单选',
  multi_select: '多选',
  checkbox: '复选框',
  textarea: '长文本',
}

const FIELD_TYPE_OPTIONS = Object.entries(FIELD_TYPE_LABELS).map(([value, label]) => ({ value, label }))

// ── state ──────────────────────────────────────────────────
const loading = ref(false)
const allFields = ref<FieldDetailOut[]>([])
const statusFilter = ref<'' | 'active' | 'archived'>('')
const selectedRows = ref<FieldDetailOut[]>([])

const activeFields = computed(() =>
  allFields.value.filter(f => f.status === 'active'),
)
const archivedFields = computed(() =>
  allFields.value.filter(f => f.status === 'archived'),
)

// ── fetch ──────────────────────────────────────────────────
async function fetchFields() {
  loading.value = true
  try {
    const params = statusFilter.value ? { status: statusFilter.value } : undefined
    allFields.value = await listFields(params)
  } finally {
    loading.value = false
  }
}

onMounted(fetchFields)

// ── selection ──────────────────────────────────────────────
function handleSelectionChange(rows: FieldDetailOut[]) {
  selectedRows.value = rows
}

// ── dialog ─────────────────────────────────────────────────
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const submitting = ref(false)
const editingId = ref<string | null>(null)

interface FormState {
  name: string
  key: string
  field_type: FieldType
  description: string
  required: boolean
  show_on_cover: boolean
  options: FieldOption[]
  sort_order: number | undefined
}

const form = reactive<FormState>({
  name: '',
  key: '',
  field_type: 'text',
  description: '',
  required: false,
  show_on_cover: false,
  options: [],
  sort_order: undefined,
})

const hasOptions = computed(() =>
  form.field_type === 'select' || form.field_type === 'multi_select' || form.field_type === 'checkbox',
)

function openCreate() {
  dialogMode.value = 'create'
  editingId.value = null
  Object.assign(form, {
    name: '',
    key: '',
    field_type: 'text',
    description: '',
    required: false,
    show_on_cover: false,
    options: [],
    sort_order: undefined,
  })
  dialogVisible.value = true
}

function openEdit(row: FieldDetailOut) {
  dialogMode.value = 'edit'
  editingId.value = row.id
  Object.assign(form, {
    name: row.name,
    key: row.key,
    field_type: row.field_type,
    description: row.description ?? '',
    required: row.required,
    show_on_cover: row.show_on_cover,
    options: row.options ? row.options.map(o => ({ ...o })) : [],
    sort_order: row.sort_order,
  })
  dialogVisible.value = true
}

function addOption() {
  form.options.push({ value: Date.now().toString(), label: '' })
}

function removeOption(i: number) {
  form.options.splice(i, 1)
}

async function submitForm() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写字段名')
    return
  }
  if (dialogMode.value === 'create' && !form.key.trim()) {
    ElMessage.warning('请填写 Key')
    return
  }
  if (hasOptions.value && form.options.some(opt => opt.label.trim() === '')) {
    ElMessage.warning('选项名称不能为空')
    return
  }

  submitting.value = true
  try {
    if (dialogMode.value === 'create') {
      const payload: FieldCreate = {
        name: form.name,
        key: form.key,
        field_type: form.field_type,
        description: form.description || undefined,
        required: form.required,
        show_on_cover: form.show_on_cover,
        options: hasOptions.value ? form.options : undefined,
        sort_order: form.sort_order,
      }
      await createField(payload)
      ElMessage.success('字段创建成功')
    } else {
      if (!editingId.value) return
      const payload: FieldUpdate = {
        name: form.name,
        description: form.description || undefined,
        required: form.required,
        show_on_cover: form.show_on_cover,
        options: hasOptions.value ? form.options : undefined,
        sort_order: form.sort_order,
      }
      await updateField(editingId.value, payload)
      ElMessage.success('字段更新成功')
    }
    dialogVisible.value = false
    await fetchFields()
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    submitting.value = false
  }
}

// ── status toggle ──────────────────────────────────────────
async function toggleStatus(row: FieldDetailOut) {
  const newStatus = row.status === 'active' ? 'archived' : 'active'
  const label = newStatus === 'archived' ? '归档' : '激活'
  try {
    await updateFieldsStatus([row.id], newStatus)
    ElMessage.success(`已${label}`)
    await fetchFields()
  } catch {
    // error handled by interceptor
  }
}

// ── single delete ──────────────────────────────────────────
async function handleDelete(row: FieldDetailOut) {
  try {
    await deleteField(row.id)
    ElMessage.success('已删除')
    await fetchFields()
  } catch {
    ElMessage.error('删除失败，请重试')
  }
}

// ── batch operations ───────────────────────────────────────
async function batchArchive() {
  if (!selectedRows.value.length) return
  const ids = selectedRows.value.map(r => r.id)
  try {
    await updateFieldsStatus(ids, 'archived')
    ElMessage.success(`已归档 ${ids.length} 个字段`)
    selectedRows.value = []
    await fetchFields()
  } catch {
    // error handled by interceptor
  }
}

async function batchDelete() {
  if (!selectedRows.value.length) return
  try {
    await ElMessageBox.confirm(
      `确认批量删除 ${selectedRows.value.length} 个字段？此操作不可撤销。`,
      '批量删除',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    const ids = selectedRows.value.map(r => r.id)
    const result = await batchDeleteFields(ids)
    ElMessage.success(`已删除 ${result.deleted_ids.length} 个字段`)
    if (result.failed.length) {
      ElMessage.warning(`${result.failed.length} 个字段删除失败`)
    }
    selectedRows.value = []
    await fetchFields()
  } catch {
    // cancelled or error
  }
}

// ── reorder ────────────────────────────────────────────────
async function moveField(index: number, direction: 'up' | 'down') {
  const arr = [...allFields.value.filter(f => f.status === 'active')]
  const swapIndex = direction === 'up' ? index - 1 : index + 1
  if (swapIndex < 0 || swapIndex >= arr.length) return
  ;[arr[index], arr[swapIndex]] = [arr[swapIndex], arr[index]]
  // Update allFields to reflect new order immediately
  const archived = allFields.value.filter(f => f.status !== 'active')
  allFields.value = [...arr, ...archived]
  try {
    await reorderFields(arr.map(f => f.id))
  } catch {
    // error handled by interceptor; refetch to restore state
    await fetchFields()
  }
}
</script>

<template>
  <div class="field-manage">
    <h2 class="page-title">字段管理</h2>

    <!-- toolbar -->
    <div class="toolbar">
      <el-button type="primary" @click="openCreate">新建字段</el-button>

      <el-select
        v-model="statusFilter"
        placeholder="全部状态"
        clearable
        style="width: 140px"
        @change="fetchFields"
      >
        <el-option label="全部" value="" />
        <el-option label="使用中" value="active" />
        <el-option label="已归档" value="archived" />
      </el-select>

      <template v-if="selectedRows.length > 0">
        <el-button @click="batchArchive">批量归档 ({{ selectedRows.length }})</el-button>
        <el-button type="danger" @click="batchDelete">批量删除 ({{ selectedRows.length }})</el-button>
      </template>
    </div>

    <!-- active fields table -->
    <el-table
      v-loading="loading"
      :data="activeFields"
      border
      style="width: 100%; margin-top: 16px"
      @selection-change="handleSelectionChange"
    >
      <el-table-column type="selection" width="50" />
      <el-table-column prop="name" label="字段名" min-width="140" />
      <el-table-column prop="key" label="Key" min-width="140" />
      <el-table-column label="类型" width="100">
        <template #default="{ row }">
          {{ FIELD_TYPE_LABELS[row.field_type] ?? row.field_type }}
        </template>
      </el-table-column>
      <el-table-column label="必填" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="row.required ? 'danger' : 'info'" size="small">
            {{ row.required ? '是' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="120" align="center">
        <template #default="{ row }">
          {{ formatDate(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="封面显示" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="row.show_on_cover ? 'success' : 'info'" size="small">
            {{ row.show_on_cover ? '是' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'warning'" size="small">
            {{ row.status === 'active' ? '使用中' : '已归档' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="260" align="center" fixed="right">
        <template #default="{ row, $index }">
          <el-button
            :icon="ArrowUp"
            circle
            size="small"
            :disabled="$index === 0"
            @click="moveField($index, 'up')"
          />
          <el-button
            :icon="ArrowDown"
            circle
            size="small"
            :disabled="$index === activeFields.length - 1"
            @click="moveField($index, 'down')"
          />
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link @click="toggleStatus(row)">
            {{ row.status === 'active' ? '归档' : '激活' }}
          </el-button>
          <el-popconfirm
            :title="`确认删除字段「${row.name}」？`"
            confirm-button-text="删除"
            cancel-button-text="取消"
            @confirm="handleDelete(row)"
          >
            <template #reference>
              <el-button link type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <!-- archived fields collapse -->
    <el-collapse style="margin-top: 24px">
      <el-collapse-item name="archived">
        <template #title>
          <span class="collapse-title">已归档字段（{{ archivedFields.length }}）</span>
        </template>
        <el-table :data="archivedFields" border style="width: 100%">
          <el-table-column prop="name" label="字段名" min-width="140" />
          <el-table-column prop="key" label="Key" min-width="140" />
          <el-table-column label="类型" width="100">
            <template #default="{ row }">
              {{ FIELD_TYPE_LABELS[row.field_type] ?? row.field_type }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160" align="center" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
              <el-button link type="success" @click="toggleStatus(row)">激活</el-button>
              <el-popconfirm
                :title="`确认删除字段「${row.name}」？`"
                confirm-button-text="删除"
                cancel-button-text="取消"
                @confirm="handleDelete(row)"
              >
                <template #reference>
                  <el-button link type="danger">删除</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
      </el-collapse-item>
    </el-collapse>

    <!-- create / edit dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '新建字段' : '编辑字段'"
      width="560px"
      :close-on-click-modal="false"
    >
      <el-form label-width="100px" @submit.prevent="submitForm">
        <el-form-item label="字段名" required>
          <el-input v-model="form.name" placeholder="请输入字段名" />
        </el-form-item>

        <el-form-item label="Key" required>
          <el-input
            v-model="form.key"
            placeholder="snake_case 格式，如 due_date"
            :readonly="dialogMode === 'edit'"
          />
          <div v-if="dialogMode === 'edit'" class="hint">Key 创建后不可修改</div>
        </el-form-item>

        <el-form-item label="字段类型" required>
          <el-select
            v-model="form.field_type"
            :disabled="dialogMode === 'edit'"
            style="width: 100%"
          >
            <el-option
              v-for="t in FIELD_TYPE_OPTIONS"
              :key="t.value"
              :label="t.label"
              :value="t.value"
            />
          </el-select>
          <div v-if="dialogMode === 'edit'" class="hint">字段类型创建后不可修改</div>
        </el-form-item>

        <el-form-item label="描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="2"
            placeholder="可选描述"
          />
        </el-form-item>

        <el-form-item label="必填">
          <el-switch v-model="form.required" />
        </el-form-item>

        <el-form-item label="封面显示">
          <el-switch v-model="form.show_on_cover" />
        </el-form-item>

        <el-form-item label="排序值">
          <el-input-number v-model="form.sort_order" :min="0" :controls="true" />
        </el-form-item>

        <!-- options management for select / multi_select / checkbox -->
        <el-form-item v-if="hasOptions" label="选项">
          <div class="options-list">
            <div
              v-for="(opt, i) in form.options"
              :key="opt.value"
              class="option-row"
            >
              <el-input v-model="opt.label" placeholder="显示名" style="flex: 1" />
              <el-input v-model="opt.value" placeholder="值" style="flex: 1; margin-left: 8px" />
              <el-button
                :icon="Close"
                circle
                size="small"
                style="margin-left: 8px; flex-shrink: 0"
                @click="removeOption(i)"
              />
            </div>
            <el-button style="margin-top: 8px" @click="addOption">添加选项</el-button>
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">
          {{ dialogMode === 'create' ? '创建' : '保存' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.field-manage {
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
.collapse-title {
  font-size: 14px;
  font-weight: 500;
}
.hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}
.options-list {
  width: 100%;
}
.option-row {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}
</style>
