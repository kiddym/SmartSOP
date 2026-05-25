<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ImportMarkingRow from '@/components/import-v2/ImportMarkingRow.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'
import { computeLayerIndents, defaultLayerRole, type LayerRole } from '@/utils/layerMark'
import { computeFallback } from '@/utils/editor'

const store = useProcedureEditorStore()
const roleMap = ref<Map<string, LayerRole>>(new Map())

function seed(): void {
  const m = new Map<string, LayerRole>()
  for (const r of store.layerRows) m.set(r.id, defaultLayerRole(r.content_type, r.level))
  roleMap.value = m
}
watch(() => store.layerMode, (on) => { if (on) seed() }, { immediate: true })

const indents = computed(() => computeLayerIndents(store.layerRows, roleMap.value))

interface RenderRow { id: string; label: string; role: LayerRole; indent: number; disableContent: boolean }
const rows = computed<RenderRow[]>(() =>
  store.layerRows.map((r) => {
    const ch = store.chapterMap.get(r.id)
    const label =
      r.content_type === 'content'
        ? computeFallback('content', ch?.rich_content ?? '')
        : ch?.title.trim() || '（无标题）'
    return {
      id: r.id,
      label,
      role: roleMap.value.get(r.id) ?? defaultLayerRole(r.content_type, r.level),
      indent: indents.value.get(r.id) ?? 0,
      disableContent: r.hasStepChildren,
    }
  }),
)

function onSet(id: string, role: LayerRole): void {
  roleMap.value = new Map(roleMap.value).set(id, role)
}
function apply(): void {
  store.applyLayerRoles(roleMap.value)
}
function cancel(): void {
  store.toggleLayerMode()
}
</script>

<template>
  <div class="layer-marking">
    <div class="lm-bar">
      <span class="lm-hint">逐行设定层级，应用后原地重排</span>
      <span class="lm-spacer" />
      <el-button size="small" @click="cancel">取消</el-button>
      <el-button size="small" type="primary" @click="apply">应用层级</el-button>
    </div>
    <div class="lm-list">
      <ImportMarkingRow
        v-for="r in rows"
        :key="r.id"
        :label="r.label"
        :role="r.role"
        :indent="r.indent"
        :disable-content="r.disableContent"
        @set="(role: LayerRole) => onSet(r.id, role)"
      />
      <el-empty v-if="!rows.length" description="暂无可标定的章节/内容" :image-size="48" />
    </div>
  </div>
</template>

<style scoped>
.layer-marking { display: flex; flex-direction: column; height: 100%; min-height: 0; }
.lm-bar {
  display: flex; align-items: center; gap: 8px; padding: 8px;
  border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5);
}
.lm-hint { font-size: 12px; color: #909399; }
.lm-spacer { flex: 1; }
.lm-list { flex: 1; overflow-y: auto; }
</style>
