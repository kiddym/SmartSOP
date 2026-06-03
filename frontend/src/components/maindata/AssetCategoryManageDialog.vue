<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listAssetCategories,
  createAssetCategory,
  updateAssetCategory,
  deleteAssetCategory,
} from '@/api/assetCategories'
import type { AssetCategoryRead } from '@/types/maindata'
import { useAuthStore } from '@/store/auth'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'changed'): void
}>()

const auth = useAuthStore()

// ── state ──────────────────────────────────────────────────
const loading = ref(false)
const categories = ref<AssetCategoryRead[]>([])

async function fetchCategories() {
  loading.value = true
  try {
    categories.value = await listAssetCategories()
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

// ── form dialog ────────────────────────────────────────────
type FormMode = 'create' | 'edit'

const formVisible = ref(false)
const formMode = ref<FormMode>('create')
const editingId = ref<string | null>(null)
const submitting = ref(false)
const form = reactive<{ name: string }>({ name: '' })

function resetForm() {
  form.name = ''
}

function openCreate() {
  formMode.value = 'create'
  editingId.value = null
  resetForm()
  formVisible.value = true
}

function openEdit(row: AssetCategoryRead) {
  formMode.value = 'edit'
  editingId.value = row.id
  resetForm()
  form.name = row.name
  formVisible.value = true
}

async function submitForm() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写分类名称')
    return
  }
  submitting.value = true
  try {
    if (formMode.value === 'create') {
      await createAssetCategory({ name: form.name })
    } else {
      if (!editingId.value) return
      await updateAssetCategory(editingId.value, { name: form.name })
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

// ── delete ─────────────────────────────────────────────────
async function handleDelete(row: AssetCategoryRead) {
  try {
    await ElMessageBox.confirm(`确认删除分类「${row.name}」？`, '提示', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteAssetCategory(row.id)
    ElMessage.success('已删除')
    await fetchCategories()
    emit('changed')
  } catch {
    // cancelled or error handled by interceptor
  }
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    title="管理分类"
    width="520px"
    :close-on-click-modal="false"
    @update:model-value="(v: boolean) => emit('update:visible', v)"
  >
    <div class="toolbar">
      <el-button
        v-if="auth.hasPermission('asset_category.manage')"
        type="primary"
        @click="openCreate"
      >
        新增分类
      </el-button>
    </div>

    <el-table v-loading="loading" :data="categories" border style="width: 100%; margin-top: 12px">
      <el-table-column prop="name" label="名称" min-width="200" />
      <el-table-column
        v-if="auth.hasPermission('asset_category.manage')"
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

  <!-- create / edit form dialog -->
  <el-dialog
    v-model="formVisible"
    :title="formMode === 'create' ? '新增分类' : '编辑分类'"
    width="420px"
    append-to-body
    :close-on-click-modal="false"
  >
    <el-form label-width="80px" @submit.prevent="submitForm">
      <el-form-item label="名称" required>
        <el-input v-model="form.name" placeholder="请输入分类名称" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="formVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
    </template>
  </el-dialog>
</template>
