<script setup lang="ts">
import { computed } from 'vue'
import { ElMessageBox } from 'element-plus'
import { useDebounceFn } from '@vueuse/core'
import RichTextEditor from './RichTextEditor.vue'
import StepFormFields from './StepFormFields.vue'
import FormFieldPreview from './FormFieldPreview.vue'
import { useNodeEditorStore } from '@/store/nodeEditor'
import { FORM_TYPE_META, isAlertType, isRichTextType } from '@/utils/editor'
import { FORM_TYPES } from '@/types/node'
import type { AttachmentMark, FormType, InputSchema } from '@/types/node'

// 统一节点详情（B3a-2）。即时·乐观写：body→updateBody（防抖）、表单+附件→updateForm。
const props = withDefaults(defineProps<{ readonly?: boolean }>(), { readonly: false })
const store = useNodeEditorStore()
const node = computed(() => store.selectedNode)
const procId = computed(() => store.procedureId ?? undefined)

const LEVELS = [
  { value: null as number | null, label: '正文' },
  { value: 1, label: '一级章节' },
  { value: 2, label: '二级章节' },
  { value: 3, label: '三级章节' },
]
const ATTACH_KINDS = [
  { value: 'video', label: '视频' },
  { value: 'image', label: '图片' },
  { value: 'document', label: '文档' },
  { value: 'audio', label: '音频' },
  { value: 'other', label: '其他' },
]

// step 节点的 input_schema 若为空 {} → 显示默认 COMMON，首次编辑时持久化。
const schema = computed<InputSchema>(() => {
  const s = node.value?.input_schema as InputSchema | Record<string, never>
  return s && 'type' in s ? (s as InputSchema) : { type: 'COMMON' }
})
const marks = computed<AttachmentMark[]>(() => node.value?.attachment_marks ?? [])

const pushBody = useDebounceFn((v: string) => {
  if (node.value) void store.updateBody(node.value.id, v)
}, 500)

function onLevel(v: number | null): void {
  if (node.value) void store.setLevel(node.value.id, v)
}
function onKindSwitch(isStep: boolean): void {
  if (node.value) void store.setKind(node.value.id, isStep ? 'step' : 'node')
}
function onSkip(): void {
  if (node.value) void store.toggleSkip(node.value.id)
}
function saveForm(nextSchema: InputSchema, nextMarks: AttachmentMark[]): void {
  if (node.value) void store.updateForm(node.value.id, nextSchema, nextMarks)
}
function onSchema(next: InputSchema): void {
  saveForm(next, marks.value)
}
function addMark(): void {
  saveForm(schema.value, [...marks.value, { filename: '', kind: 'document', note: '' }])
}
function updMark(i: number, patch: Partial<AttachmentMark>): void {
  saveForm(schema.value, marks.value.map((m, idx) => (idx === i ? { ...m, ...patch } : m)))
}
function removeMark(i: number): void {
  saveForm(schema.value, marks.value.filter((_, idx) => idx !== i))
}

function hasConfig(s: InputSchema): boolean {
  return Object.keys(s).some((k) => k !== 'type')
}
async function onTypeChange(next: FormType): Promise<void> {
  const cur = schema.value
  if (cur.type !== next && !isRichTextType(cur.type) && cur.type !== 'NONE' && hasConfig(cur)) {
    try {
      await ElMessageBox.confirm('切换类型会清空当前类型的配置（单位/范围/选项等），是否继续？', '切换确认', { type: 'warning' })
    } catch {
      return
    }
  }
  saveForm({ type: next }, marks.value)
}

const alertClass = computed(() => (isAlertType(schema.value.type) ? `alert-${schema.value.type.toLowerCase()}` : ''))
</script>

<template>
  <div v-if="node" class="node-detail">
    <el-form v-if="!props.readonly" label-position="top">
      <el-form-item label="层级">
        <el-select :model-value="node.heading_level" @change="onLevel">
          <el-option v-for="l in LEVELS" :key="String(l.value)" :value="l.value as number" :label="l.label" />
        </el-select>
      </el-form-item>
      <div class="inline">
        <el-form-item label="作为步骤（带执行表单）" class="kind-switch">
          <el-switch :model-value="node.kind === 'step'" @change="onKindSwitch" />
        </el-form-item>
        <el-form-item label="跳号">
          <el-switch :model-value="node.skip_numbering" @change="onSkip" />
        </el-form-item>
      </div>
    </el-form>

    <el-collapse :model-value="['body', 'form', 'attach']">
      <el-collapse-item title="正文" name="body">
        <RichTextEditor
          :key="`body-${node.id}`"
          :model-value="node.body"
          variant="full"
          :readonly="props.readonly"
          :procedure-id="procId"
          placeholder="输入正文…（首个块级元素文本作为标题）"
          @update:model-value="pushBody"
        />
      </el-collapse-item>

      <el-collapse-item v-if="node.kind === 'step'" title="执行表单" name="form">
        <el-form label-position="top">
          <el-form-item label="类型">
            <el-select :model-value="schema.type" :disabled="props.readonly" @change="onTypeChange">
              <el-option v-for="t in FORM_TYPES" :key="t" :value="t" :label="FORM_TYPE_META[t].label" />
            </el-select>
          </el-form-item>
          <div v-if="isRichTextType(schema.type)" class="rt-wrap" :class="alertClass">
            <span class="rt-hint">富文本类型的提示文本随正文渲染；此处仅配置类型样式。</span>
          </div>
          <template v-else>
            <div class="config-preview">
              <div class="cp-config"><StepFormFields :schema="schema" :readonly="props.readonly" @update:schema="onSchema" /></div>
              <div class="cp-preview"><FormFieldPreview :schema="schema" /></div>
            </div>
          </template>
        </el-form>
      </el-collapse-item>

      <el-collapse-item v-if="node.kind === 'step'" title="附件标记" name="attach">
        <div v-for="(m, i) in marks" :key="i" class="mark-row">
          <el-input :model-value="m.filename" placeholder="文件名" :disabled="props.readonly" @input="(v: string) => updMark(i, { filename: v })" />
          <el-select :model-value="m.kind" class="mark-kind" :disabled="props.readonly" @change="(v: string) => updMark(i, { kind: v })">
            <el-option v-for="k in ATTACH_KINDS" :key="k.value" :value="k.value" :label="k.label" />
          </el-select>
          <el-input :model-value="m.note" placeholder="备注" :disabled="props.readonly" @input="(v: string) => updMark(i, { note: v })" />
          <el-button v-if="!props.readonly" size="small" text @click="removeMark(i)">✕</el-button>
        </div>
        <el-button v-if="!props.readonly" class="add-mark" size="small" @click="addMark">+ 附件标记</el-button>
      </el-collapse-item>
    </el-collapse>

    <div v-if="node.mark_status === 'review' && !props.readonly" class="review-bar">
      <span class="review-tag">待确认</span>
      <el-button class="confirm-review" size="small" type="primary" @click="store.confirmReview(node.id)">确认</el-button>
    </div>
  </div>
  <el-empty v-else description="选择左侧节点进行编辑" />
</template>

<style scoped>
.node-detail { padding: 8px 0 40px; }
.inline { display: flex; gap: 16px; }
.config-preview { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 8px; }
.cp-config, .cp-preview { flex: 1 1 280px; min-width: 0; }
.rt-wrap { padding-left: 8px; border-left: 3px solid transparent; }
.alert-note { border-left-color: var(--el-color-primary, #d97757); }
.alert-caution { border-left-color: #e6a23c; }
.alert-warning { border-left-color: #f56c6c; }
.rt-hint { font-size: 12px; color: #909399; }
.mark-row { display: flex; gap: 6px; align-items: center; margin-bottom: 6px; }
.mark-kind { width: 120px; flex: none; }
.review-bar { display: flex; align-items: center; gap: 8px; margin-top: 12px; }
.review-tag { font-size: 12px; color: #b88230; background: #fdf6ec; border: 1px solid #f5dab1; border-radius: 3px; padding: 1px 6px; }
</style>
