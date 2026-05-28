<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import NodeTreePanel from '@/components/editor/NodeTreePanel.vue'
import NodeDetailPanel from '@/components/editor/NodeDetailPanel.vue'
import { useNodeEditorStore } from '@/store/nodeEditor'
import { fetchProcedureDetail } from '@/api/procedures'

// 隔离的统一节点编辑器（B3a-2，behind ?editor=node）。即时·乐观写，无 Save。
const props = defineProps<{ procedureId: string }>()
const store = useNodeEditorStore()
// useRouter 必须在 setup 同步阶段取（内部 inject），不能放进 goBack 点击回调里，否则 router 为 undefined。
const router = useRouter()

const title = ref('')
const code = ref('')
const inflight = ref(0)
const saving = ref(false)

// autosave 指示：经 $onAction 计数 mutating actions（不改 store）。
const MUTATING = new Set([
  'setLevel', 'setKind', 'toggleSkip', 'batchSetLevel', 'batchSetKind',
  'confirmReview', 'createNode', 'removeNode', 'reorder', 'updateBody', 'updateForm', 'undo',
])
store.$onAction(({ name, after, onError }) => {
  if (!MUTATING.has(name)) return
  inflight.value++
  saving.value = true
  const done = (): void => {
    inflight.value = Math.max(0, inflight.value - 1)
    if (inflight.value === 0) saving.value = false
  }
  after(done)
  onError(done)
})

onMounted(async () => {
  await store.load(props.procedureId)
  try {
    const meta = await fetchProcedureDetail(props.procedureId)
    title.value = meta.procedure.name
    code.value = meta.procedure.code
  } catch {
    /* meta 仅作面包屑，失败不阻塞编辑 */
  }
})

function goBack(): void {
  void router.push({ name: 'procedure-library' })
}
</script>

<template>
  <div class="node-editor">
    <div class="nev-bar">
      <el-button class="nev-back" size="small" text @click="goBack">← 返回</el-button>
      <span class="nev-title">{{ code }} {{ title }}</span>
      <el-button class="nev-undo" size="small" :disabled="!store.canUndo" @click="store.undo()">↶ 撤销</el-button>
      <span class="nev-save" :class="{ 'is-saving': saving }">{{ saving ? '保存中…' : '✓ 已保存' }}</span>
    </div>
    <div class="nev-body">
      <div class="nev-left"><NodeTreePanel /></div>
      <div class="nev-right"><NodeDetailPanel /></div>
    </div>
  </div>
</template>

<style scoped>
.node-editor { display: flex; flex-direction: column; height: calc(100vh - 0px); min-height: 480px; }
.nev-bar { display: flex; align-items: center; gap: 12px; padding: 8px 12px; border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5); }
.nev-title { font-weight: 600; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.nev-save { font-size: 12px; color: #67c23a; }
.nev-save.is-saving { color: #909399; }
.nev-body { flex: 1; display: flex; min-height: 0; }
.nev-left { flex: 1; min-width: 280px; min-height: 0; }
.nev-right { width: 380px; min-width: 320px; border-left: 1px solid var(--el-border-color-lighter, #ebeef5); overflow-y: auto; padding: 0 14px; }
</style>
