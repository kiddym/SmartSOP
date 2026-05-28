<script setup lang="ts">
import { computed } from 'vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'
import { useNodeEditorStore } from '@/store/nodeEditor'

// 发布检查列表（§17.4 / Q156 / Q178）：全 ✓（除 warning）才能确认发布。
// B3b-2：结构来自 nodeEditor（节点数 + 待确认数）；元字段来自 procedureEditor；即时写无 dirty/save。
const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'confirm'): void
}>()

const store = useProcedureEditorStore()
const nodeStore = useNodeEditorStore()

interface Check {
  label: string
  ok: boolean
  warning?: boolean
}

const checks = computed<Check[]>(() => {
  const p = store.procedure
  const list: Check[] = []
  list.push({ label: '程序名称非空', ok: !!p && p.name.trim().length > 0 })
  list.push({ label: '至少包含 1 个节点', ok: nodeStore.nodes.length > 0 })
  const reviewPending = nodeStore.reviewCount
  list.push({ label: `无待确认节点${reviewPending ? `（剩 ${reviewPending}）` : ''}`, ok: reviewPending === 0 })
  for (const f of store.fields.filter((f) => f.required)) {
    const v = p?.custom_values?.[f.key]
    list.push({ label: `必填字段「${f.name}」已填写`, ok: v !== undefined && v !== null && String(v).trim() !== '' })
  }
  if (p && p.version > 1) {
    list.push({ label: '本次版本更新说明非空', ok: p.version_update_notes.trim().length > 0 })
  }
  return list
})

const canConfirm = computed(() => checks.value.every((c) => c.ok || c.warning))

function close(): void {
  emit('update:modelValue', false)
}
</script>

<template>
  <el-dialog
    :model-value="props.modelValue"
    title="发布检查"
    width="480px"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <ul class="checks">
      <li v-for="(c, i) in checks" :key="i" :class="{ warn: c.warning, fail: !c.ok && !c.warning }">
        <span class="mark">{{ c.ok ? '✓' : c.warning ? '!' : '✗' }}</span>
        <span class="label">{{ c.label }}</span>
      </li>
    </ul>
    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :disabled="!canConfirm" @click="emit('confirm')">
        确认发布 v{{ store.procedure?.version }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.checks {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.checks li {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--el-color-success, #67c23a);
}
.checks li.fail {
  color: var(--el-color-danger, #f56c6c);
}
.checks li.warn {
  color: var(--el-color-warning, #e6a23c);
}
.mark {
  width: 16px;
  text-align: center;
  font-weight: bold;
}
.label {
  flex: 1;
}
</style>
