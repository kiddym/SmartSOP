<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { listNodes } from '@/api/nodes'
import { nodeTitle } from '@/utils/nodeTree'
import { diffVersions, type DiffRow } from './versionDiff'
import { charDiff, htmlToText } from './charDiff'

const props = defineProps<{
  modelValue: boolean
  oldId: string
  newId: string
  oldVersion: number
  newVersion: number
}>()
const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>()
const visible = computed({ get: () => props.modelValue, set: (v) => emit('update:modelValue', v) })

const loading = ref(false)
const rows = ref<DiffRow[]>([])
const onlyChanges = ref(true)
const charMode = ref(true)
const expanded = ref<Set<number>>(new Set())

watch(
  visible,
  async (open) => {
    if (!open) return
    loading.value = true
    expanded.value = new Set()
    try {
      const [oldNodes, newNodes] = await Promise.all([listNodes(props.oldId), listNodes(props.newId)])
      rows.value = diffVersions(oldNodes, newNodes)
    } catch {
      visible.value = false // 拦截器已提示
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)

const visibleRows = computed(() =>
  onlyChanges.value ? rows.value.filter((r) => r.status !== 'unchanged') : rows.value,
)
const summary = computed(() => ({
  added: rows.value.filter((r) => r.status === 'added').length,
  removed: rows.value.filter((r) => r.status === 'removed').length,
  modified: rows.value.filter((r) => r.status === 'modified').length,
}))
const GLYPH: Record<DiffRow['status'], string> = { unchanged: '=', modified: '~', added: '+', removed: '−' }

function code(r: DiffRow): string {
  return (r.new ?? r.old)?.code ?? ''
}
function title(r: DiffRow): string {
  const x = r.new ?? r.old
  return x ? nodeTitle(x) : ''
}
function toggle(i: number): void {
  const next = new Set(expanded.value)
  if (next.has(i)) next.delete(i)
  else next.add(i)
  expanded.value = next
}
function charSegs(r: DiffRow) {
  return charDiff(htmlToText(r.old?.body ?? ''), htmlToText(r.new?.body ?? ''))
}
</script>

<template>
  <el-dialog v-model="visible" fullscreen :show-close="false" append-to-body class="vc-dialog">
    <template #header>
      <div class="vc-toolbar">
        <span class="vc-title">版本对比 · v{{ oldVersion }} → v{{ newVersion }}</span>
        <span class="vc-summary">
          <span class="add">+{{ summary.added }}</span>
          <span class="del">−{{ summary.removed }}</span>
          <span class="mod">~{{ summary.modified }}</span>
        </span>
        <span class="vc-spacer" />
        <el-switch v-model="onlyChanges" active-text="只看变更" />
        <el-switch v-model="charMode" active-text="字符差异" />
        <el-button @click="visible = false">关闭</el-button>
      </div>
    </template>

    <div v-loading="loading" class="vc-body">
      <div v-for="(r, i) in visibleRows" :key="`${i}-${(r.new ?? r.old)?.id}`" class="vc-row" :class="`is-${r.status}`">
        <div class="vc-line" :class="{ clickable: r.status !== 'unchanged' }" @click="r.status !== 'unchanged' && toggle(i)">
          <span class="vc-glyph">{{ GLYPH[r.status] }}</span>
          <span class="vc-code">{{ code(r) }}</span>
          <span class="vc-rowtitle">{{ title(r) }}</span>
          <el-tag v-for="f in r.changedFields" :key="f" size="small" type="warning" disable-transitions>{{ f }}</el-tag>
        </div>
        <div v-if="expanded.has(i)" class="vc-bodies">
          <template v-if="r.status === 'modified'">
            <div v-if="charMode" class="vc-chardiff">
              <span
                v-for="(seg, k) in charSegs(r)"
                :key="k"
                :class="seg.type === 'del' ? 'vc-del' : seg.type === 'ins' ? 'vc-ins' : ''"
              >{{ seg.text }}</span>
            </div>
            <template v-else>
              <div class="vc-col">
                <div class="vc-coltag">旧 v{{ oldVersion }}</div>
                <!-- eslint-disable-next-line vue/no-v-html -->
                <div class="vc-html" v-html="r.old?.body"></div>
              </div>
              <div class="vc-col">
                <div class="vc-coltag">新 v{{ newVersion }}</div>
                <!-- eslint-disable-next-line vue/no-v-html -->
                <div class="vc-html" v-html="r.new?.body"></div>
              </div>
            </template>
          </template>
          <div v-else-if="r.status === 'added'" class="vc-col">
            <div class="vc-coltag">新增</div>
            <!-- eslint-disable-next-line vue/no-v-html -->
            <div class="vc-html" v-html="r.new?.body"></div>
          </div>
          <div v-else-if="r.status === 'removed'" class="vc-col">
            <div class="vc-coltag">删除</div>
            <!-- eslint-disable-next-line vue/no-v-html -->
            <div class="vc-html" v-html="r.old?.body"></div>
          </div>
        </div>
      </div>
      <el-empty v-if="!loading && !visibleRows.length" description="两个版本内容一致" />
    </div>
  </el-dialog>
</template>

<style scoped>
.vc-toolbar { display: flex; align-items: center; gap: 12px; width: 100%; }
.vc-title { font-weight: 600; }
.vc-summary { display: inline-flex; gap: 8px; font-size: 13px; }
.vc-summary .add { color: var(--el-color-success, #67c23a); }
.vc-summary .del { color: var(--el-color-danger, #f56c6c); }
.vc-summary .mod { color: var(--el-color-warning, #e6a23c); }
.vc-spacer { flex: 1; }
.vc-body { height: calc(100vh - 90px); overflow: auto; }
.vc-row { border-bottom: 1px solid var(--el-border-color-lighter, #f0f0f0); }
.vc-line { display: flex; align-items: center; gap: 10px; padding: 6px 8px; }
.vc-line.clickable { cursor: pointer; }
.vc-glyph { width: 16px; text-align: center; font-weight: bold; }
.vc-code { min-width: 48px; color: #909399; }
.vc-rowtitle { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.is-added { background: #f0f9eb; }
.is-removed { background: #fef0f0; }
.is-modified { background: #fdf6ec; }
.vc-bodies { display: flex; gap: 16px; padding: 8px 8px 12px 42px; }
.vc-col { flex: 1; min-width: 0; }
.vc-coltag { font-size: 12px; color: #909399; margin-bottom: 4px; }
.vc-html { border: 1px solid var(--el-border-color-lighter, #ebeef5); border-radius: 4px; padding: 8px; background: #fff; overflow-x: auto; }
.vc-chardiff {
  flex: 1;
  min-width: 0;
  padding: 8px;
  background: #fff;
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
}
.vc-del {
  background: #fde2e2;
  color: #c0392b;
  text-decoration: line-through;
}
.vc-ins {
  background: #e3f9e5;
  color: #2e7d32;
}
</style>
