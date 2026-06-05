<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listMultiParts,
  createMultiPart,
  updateMultiPart,
  deleteMultiPart,
} from '@/api/multiParts'
import { listPartsMini } from '@/api/parts'
import type {
  MultiPartRead,
  MultiPartCreate,
  MultiPartUpdate,
  PartMini,
} from '@/types/inventory'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()

defineProps<{ embedded?: boolean }>()

const loading = ref(false)
const multiParts = ref<MultiPartRead[]>([])
const partsMini = ref<PartMini[]>([])

async function fetchMultiParts() {
  loading.value = true
  try {
    multiParts.value = await listMultiParts()
  } finally {
    loading.value = false
  }
}
async function fetchPartsMini() {
  partsMini.value = await listPartsMini()
}

onMounted(async () => {
  await Promise.all([fetchMultiParts(), fetchPartsMini()])
})

const partMap = computed(() => {
  const m = new Map<string, PartMini>()
  for (const p of partsMini.value) m.set(p.id, p)
  return m
})
function memberLabel(id: string): string {
  const p = partMap.value.get(id)
  return p ? `${p.custom_id} ${p.name}` : '(已删除)'
}

type DialogMode = 'create' | 'edit'

const dialogVisible = ref(false)
const dialogMode = ref<DialogMode>('create')
const editingId = ref<string | null>(null)
const submitting = ref(false)

interface FormState {
  name: string
  description: string
  part_ids: string[]
}
const form = reactive<FormState>({ name: '', description: '', part_ids: [] })

const dialogTitle = computed(() => (dialogMode.value === 'create' ? '新建套件' : '编辑套件'))

function resetForm() {
  form.name = ''
  form.description = ''
  form.part_ids = []
}

function openCreate() {
  resetForm()
  dialogMode.value = 'create'
  editingId.value = null
  dialogVisible.value = true
}

function openEdit(row: MultiPartRead) {
  resetForm()
  Object.assign(form, {
    name: row.name,
    description: row.description,
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
    const payload: MultiPartCreate | MultiPartUpdate = {
      name: form.name.trim(),
      description: form.description,
      part_ids: form.part_ids,
    }
    if (dialogMode.value === 'create') {
      await createMultiPart(payload as MultiPartCreate)
      ElMessage.success('套件创建成功')
    } else {
      if (!editingId.value) return
      await updateMultiPart(editingId.value, payload)
      ElMessage.success('套件更新成功')
    }
    dialogVisible.value = false
    await fetchMultiParts()
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: MultiPartRead) {
  try {
    await ElMessageBox.confirm(`确认删除套件「${row.name}」？`, '提示', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteMultiPart(row.id)
    ElMessage.success('已删除')
    await fetchMultiParts()
  } catch {
    // cancelled or error handled by interceptor
  }
}

defineExpose({ memberLabel, form })
</script>

<template>
  <div :class="embedded ? '' : 'page'">
    <h2 v-if="!embedded" class="page-title">多备件套件</h2>

    <div class="toolbar">
      <el-button v-if="auth.hasPermission('part.create')" type="primary" @click="openCreate">
        新建套件
      </el-button>
    </div>

    <el-table
      v-loading="loading"
      :data="multiParts"
      row-key="id"
      border
      style="width: 100%; margin-top: 16px"
    >
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="member-list">
            <span v-if="row.part_ids.length === 0" class="member-empty">(无成员)</span>
            <el-tag v-for="pid in row.part_ids" :key="pid" class="member-tag" type="info">
              {{ memberLabel(pid) }}
            </el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="custom_id" label="编号" min-width="120" />
      <el-table-column prop="name" label="名称" min-width="180" />
      <el-table-column prop="description" label="描述" min-width="200" />
      <el-table-column label="成员数" min-width="100" align="center">
        <template #default="{ row }">{{ row.part_ids.length }} 项</template>
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

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="640px"
      :close-on-click-modal="false"
    >
      <el-form label-width="100px" @submit.prevent="submitForm">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="请输入名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" placeholder="请输入描述" />
        </el-form-item>
        <el-form-item label="成员备件">
          <el-select
            v-model="form.part_ids"
            multiple
            filterable
            placeholder="选择成员备件"
            style="width: 100%"
          >
            <el-option
              v-for="p in partsMini"
              :key="p.id"
              :label="`${p.custom_id} ${p.name}`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm"> 保存 </el-button>
      </template>
    </el-dialog>
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
.member-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 16px;
}
.member-empty {
  color: var(--text-tertiary, #909399);
  font-size: 13px;
}
</style>
