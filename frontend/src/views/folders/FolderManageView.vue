<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import FolderTree from '@/components/FolderTree.vue'
import { useFolderStore } from '@/store/folders'
import { createFolder, deleteFolder, updateFolder } from '@/api/folders'
import type { FolderTreeNode } from '@/types/folder'

const store = useFolderStore()
const selected = ref<FolderTreeNode | null>(null)

const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const submitting = ref(false)

interface FormState {
  id: string
  name: string
  parent_id: string // '' = 根目录（el-option 不接受 null，提交时归一为 null）
  prefix: string
  sequence_digits: number
}
const form = reactive<FormState>({
  id: '',
  name: '',
  parent_id: '',
  prefix: '',
  sequence_digits: 5,
})

async function refresh(): Promise<void> {
  await Promise.all([store.loadTree(), store.loadOptions()])
}
onMounted(refresh)

function onSelect(node: FolderTreeNode): void {
  selected.value = node
}

function openCreate(): void {
  dialogMode.value = 'create'
  Object.assign(form, {
    id: '',
    name: '',
    parent_id: selected.value?.id ?? '',
    prefix: '',
    sequence_digits: 5,
  })
  dialogVisible.value = true
}

function openEdit(): void {
  if (!selected.value) return
  if (selected.value.system) {
    ElMessage.warning('系统文件夹不可修改')
    return
  }
  dialogMode.value = 'edit'
  Object.assign(form, {
    id: selected.value.id,
    name: selected.value.name,
    parent_id: selected.value.parent_id ?? '',
    prefix: selected.value.prefix,
    sequence_digits: 5,
  })
  dialogVisible.value = true
}

async function submit(): Promise<void> {
  if (!form.name.trim()) {
    ElMessage.warning('请输入文件夹名称')
    return
  }
  submitting.value = true
  try {
    if (dialogMode.value === 'create') {
      await createFolder({
        name: form.name,
        parent_id: form.parent_id || null,
        prefix: form.prefix || '',
        sequence_digits: form.sequence_digits,
      })
      ElMessage.success('已创建')
    } else {
      await updateFolder(form.id, {
        name: form.name,
        parent_id: form.parent_id || null,
        prefix: form.prefix || '',
        sequence_digits: form.sequence_digits,
      })
      ElMessage.success('已保存')
    }
    dialogVisible.value = false
    await refresh()
  } finally {
    submitting.value = false
  }
}

async function remove(): Promise<void> {
  if (!selected.value) return
  await ElMessageBox.confirm(`确定删除文件夹「${selected.value.name}」？`, '删除确认', {
    type: 'warning',
  })
  await deleteFolder(selected.value.id)
  ElMessage.success('已删除')
  selected.value = null
  await refresh()
}
</script>

<template>
  <div class="folder-manage">
    <div class="toolbar">
      <h2 class="title">文件夹配置</h2>
      <div class="actions">
        <el-button type="primary" @click="openCreate">新建文件夹</el-button>
        <el-button :disabled="!selected || selected.system" @click="openEdit"
          >重命名 / 移动</el-button
        >
        <el-button :disabled="!selected || selected.system" type="danger" plain @click="remove">
          删除
        </el-button>
      </div>
    </div>

    <el-card shadow="never" class="tree-card">
      <FolderTree :data="store.tree" :loading="store.loading" @select="onSelect" />
      <el-empty v-if="!store.loading && store.tree.length === 0" description="暂无文件夹" />
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '新建文件夹' : '编辑文件夹'"
      width="480px"
    >
      <el-form label-width="96px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" maxlength="100" placeholder="文件夹名称" />
        </el-form-item>
        <el-form-item label="父文件夹">
          <el-select v-model="form.parent_id" clearable placeholder="根目录" class="full">
            <el-option label="（根目录）" value="" />
            <el-option
              v-for="opt in store.options"
              :key="opt.id"
              :label="opt.full_path"
              :value="opt.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="编码前缀">
          <el-input
            v-model="form.prefix"
            maxlength="20"
            placeholder="留空=中间容器；填写=可存程序的叶子"
          />
        </el-form-item>
        <el-form-item v-if="form.prefix" label="编号位数">
          <el-input-number v-model="form.sequence_digits" :min="1" :max="9" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.folder-manage {
  padding: 20px 24px;
}
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.title {
  margin: 0;
  font-size: 18px;
}
.tree-card {
  min-height: 320px;
}
.full {
  width: 100%;
}
</style>
