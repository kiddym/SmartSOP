<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listTimeCategories,
  createTimeCategory,
  updateTimeCategory,
  deleteTimeCategory,
} from '@/api/timeCategories'
import type { TimeCategoryRead } from '@/types/workOrder'
import { useAuthStore } from '@/store/auth'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'changed'): void
}>()

const auth = useAuthStore()

const loading = ref(false)
const categories = ref<TimeCategoryRead[]>([])

async function fetchCategories() {
  loading.value = true
  try {
    categories.value = await listTimeCategories()
  } finally {
    loading.value = false
  }
}

watch(
  () => props.visible,
  (v) => {
    if (v) fetchCategories()
  },
  { immediate: true },
)

type FormMode = 'create' | 'edit'

const formVisible = ref(false)
const formMode = ref<FormMode>('create')
const editingId = ref<string | null>(null)
const submitting = ref(false)
const form = reactive<{ name: string; hourly_rate: string; description: string }>({
  name: '',
  hourly_rate: '',
  description: '',
})

function resetForm() {
  form.name = ''
  form.hourly_rate = ''
  form.description = ''
}

function openCreate() {
  formMode.value = 'create'
  editingId.value = null
  resetForm()
  formVisible.value = true
}

function openEdit(row: TimeCategoryRead) {
  formMode.value = 'edit'
  editingId.value = row.id
  resetForm()
  form.name = row.name
  form.hourly_rate = row.hourly_rate
  form.description = row.description
  formVisible.value = true
}

async function submitForm() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写分类名称')
    return
  }
  submitting.value = true
  try {
    const payload = {
      name: form.name.trim(),
      hourly_rate: form.hourly_rate || '0',
      description: form.description,
    }
    if (formMode.value === 'create') {
      await createTimeCategory(payload)
    } else {
      if (!editingId.value) return
      await updateTimeCategory(editingId.value, payload)
    }
    ElMessage.success('保存成功')
    formVisible.value = false
    await fetchCategories()
    emit('changed')
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: TimeCategoryRead) {
  try {
    await ElMessageBox.confirm(`确认删除工时分类「${row.name}」？`, '提示', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteTimeCategory(row.id)
    ElMessage.success('已删除')
    await fetchCategories()
    emit('changed')
  } catch {
    // cancelled or error handled by interceptor
  }
}

defineExpose({ openCreate, openEdit, submitForm, handleDelete, form })
</script>

<template>
  <el-dialog
    :model-value="visible"
    title="管理工时分类"
    width="600px"
    :close-on-click-modal="false"
    @update:model-value="(v: boolean) => emit('update:visible', v)"
  >
    <div class="toolbar">
      <el-button
        v-if="auth.hasPermission('time_category.manage')"
        type="primary"
        @click="openCreate"
      >
        新增分类
      </el-button>
    </div>

    <el-table v-loading="loading" :data="categories" border style="width: 100%; margin-top: 12px">
      <el-table-column prop="name" label="名称" min-width="150" />
      <el-table-column prop="hourly_rate" label="费率（元/时）" min-width="120" />
      <el-table-column prop="description" label="描述" min-width="180" />
      <el-table-column
        v-if="auth.hasPermission('time_category.manage')"
        label="操作"
        width="160"
        align="center"
      >
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <template #footer>
      <el-button @click="emit('update:visible', false)">关闭</el-button>
    </template>
  </el-dialog>

  <el-dialog
    v-model="formVisible"
    :title="formMode === 'create' ? '新增工时分类' : '编辑工时分类'"
    width="460px"
    append-to-body
    :close-on-click-modal="false"
  >
    <el-form label-width="100px" @submit.prevent="submitForm">
      <el-form-item label="名称" required>
        <el-input v-model="form.name" placeholder="请输入分类名称" />
      </el-form-item>
      <el-form-item label="费率（元/时）">
        <el-input v-model="form.hourly_rate" placeholder="默认费率，可空（按 0 计）" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" placeholder="请输入描述" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="formVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.toolbar {
  display: flex;
  gap: 8px;
}
</style>
