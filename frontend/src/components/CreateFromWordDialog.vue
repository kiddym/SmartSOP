<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchFolderTree } from '@/api/folders'
import { importFromWord } from '@/api/parse'
import type { FolderTreeNode } from '@/types/folder'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'imported', id: string): void
}>()
const visible = computed({ get: () => props.modelValue, set: (v) => emit('update:modelValue', v) })

interface LeafOption { id: string; label: string }
const leaves = ref<LeafOption[]>([])
const file = ref<File | null>(null)
const form = reactive({ folder_id: '', name: '' })
const phase = ref<'' | 'working'>('')
const busy = computed(() => phase.value !== '')

function collectLeaves(nodes: FolderTreeNode[], acc: LeafOption[]): void {
  for (const n of nodes) {
    if (!n.system && n.children.length === 0 && n.prefix) acc.push({ id: n.id, label: n.full_path })
    if (n.children.length) collectLeaves(n.children, acc)
  }
}
async function loadLeaves(): Promise<void> {
  const acc: LeafOption[] = []
  collectLeaves(await fetchFolderTree(), acc)
  leaves.value = acc
}
watch(visible, (open) => {
  if (open) {
    file.value = null
    form.folder_id = ''
    form.name = ''
    phase.value = ''
    void loadLeaves()
  }
})
function onFile(e: Event): void {
  const f = (e.target as HTMLInputElement).files?.[0] ?? null
  file.value = f
  if (f && !form.name.trim()) form.name = f.name.replace(/\.docx$/i, '')
}
async function submit(): Promise<void> {
  if (!file.value) { ElMessage.warning('请选择 .docx 文件'); return }
  if (!form.folder_id) { ElMessage.warning('请选择目标文件夹'); return }
  if (!form.name.trim()) { ElMessage.warning('请输入程序名称'); return }
  phase.value = 'working'
  try {
    const proc = await importFromWord(file.value, form.folder_id, form.name.trim())
    ElMessage.success(`已创建 ${proc.code}`)
    visible.value = false
    emit('imported', proc.id)
  } catch {
    /* 拦截器已提示；保持打开可重试 */
  } finally {
    phase.value = ''
  }
}
</script>

<template>
  <el-dialog v-model="visible" title="从 Word 导入" width="520px">
    <el-form label-width="96px">
      <el-form-item label="Word 文件" required>
        <input type="file" accept=".docx" @change="onFile" />
      </el-form-item>
      <el-form-item label="目标文件夹" required>
        <el-select v-model="form.folder_id" filterable placeholder="仅可存程序的叶子文件夹" class="full">
          <el-option v-for="l in leaves" :key="l.id" :label="l.label" :value="l.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="程序名称" required>
        <el-input v-model="form.name" maxlength="200" placeholder="默认取文件名" />
      </el-form-item>
      <div v-if="busy" class="phase">上传解析创建中…</div>
    </el-form>
    <template #footer>
      <el-button :disabled="busy" @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="busy" @click="submit">导入并编辑</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.full { width: 100%; }
.phase { color: #606266; font-size: 13px; padding-left: 96px; }
</style>
