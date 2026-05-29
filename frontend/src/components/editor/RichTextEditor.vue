<script setup lang="ts">
import { onBeforeUnmount, shallowRef, computed } from 'vue'
import '@wangeditor/editor/dist/css/style.css'
import { Editor, Toolbar } from '@wangeditor/editor-for-vue'
import type { IDomEditor, IEditorConfig, IToolbarConfig } from '@wangeditor/editor'
import { Boot } from '@wangeditor/editor'
import { uploadAsset } from '@/api/parse'
import { withMarkdownAutoformat } from './markdownAutoformat'

// Register markdown autoformat once for all wangeditor instances (HMR-safe via a global flag).
const MD_PLUGIN_KEY = '__smartsop_md_autoformat_registered__'
if (!(globalThis as Record<string, unknown>)[MD_PLUGIN_KEY]) {
  Boot.registerPlugin(withMarkdownAutoformat)
  ;(globalThis as Record<string, unknown>)[MD_PLUGIN_KEY] = true
}

// content / step 富文本编辑器（§4.2-4.3）。chapter 节点不使用本组件（§19）。
// 图片直传（Q214/Q355）：仅 full 变体 + 传入 procedureId + 可编辑时启用「上传图片」菜单，
//   走 POST /procedures/{id}/assets（sha256 去重入库），插入永久 asset URL；
//   始终禁用「网络图片」(insertImage)。特殊元素经 dangerouslyInsertHtml 插入。

interface Props {
  modelValue: string
  variant?: 'full' | 'step'
  readonly?: boolean
  placeholder?: string
  procedureId?: string
}
const props = withDefaults(defineProps<Props>(), {
  variant: 'full',
  readonly: false,
  placeholder: '请输入内容…',
  procedureId: '',
})
const emit = defineEmits<{ (e: 'update:modelValue', value: string): void }>()

const editorRef = shallowRef<IDomEditor | null>(null)

const mode = computed(() => (props.variant === 'step' ? 'simple' : 'default'))

const allowImageUpload = computed(
  () => props.variant === 'full' && !props.readonly && !!props.procedureId,
)

const toolbarConfig = computed<Partial<IToolbarConfig>>(() => {
  if (props.variant === 'step') {
    return { toolbarKeys: ['bold', 'italic', 'underline', 'bulletedList', 'numberedList', 'insertLink'] }
  }
  // insertImage（网络图片 by URL）始终禁用；上传图片仅在 allowImageUpload 时放开。
  const exclude = ['group-video', 'insertImage', 'insertVideo', 'uploadVideo', 'fullScreen', 'codeBlock']
  if (!allowImageUpload.value) exclude.push('group-image', 'uploadImage')
  return { excludeKeys: exclude }
})

type InsertImageFn = (url: string, alt: string, href: string) => void

const editorConfig = computed<Partial<IEditorConfig>>(() => {
  const cfg: Partial<IEditorConfig> = {
    placeholder: props.placeholder,
    readOnly: props.readonly,
  }
  if (allowImageUpload.value) {
    const pid = props.procedureId
    cfg.MENU_CONF = {
      uploadImage: {
        async customUpload(file: File, insertFn: InsertImageFn): Promise<void> {
          try {
            const res = await uploadAsset(pid, file)
            insertFn(res.url, file.name, res.url)
          } catch {
            /* http 拦截器已 toast（IMAGE_TOO_LARGE / IMAGE_CONVERT_FAILED 等） */
          }
        },
      },
    }
  }
  return cfg
})

// §4.3 特殊元素：PDF 生成时由 ReportLab 识别 class 渲染。
const SPECIAL_BLOCKS: { key: string; label: string; html: string }[] = [
  { key: 'note', label: '注意', html: '<div class="note-block">在此输入提示内容</div>' },
  { key: 'caution', label: '小心', html: '<div class="caution-block">在此输入设备风险警示</div>' },
  { key: 'warning', label: '警告', html: '<div class="warning-block">在此输入人身风险警示</div>' },
  { key: 'signature', label: '签名栏', html: '<div class="signature-bar" data-columns="3">在此配置签名栏</div>' },
  { key: 'hold', label: 'HoldPoint', html: '<div class="hold-point">在此输入 hold point 内容</div>' },
]
const showSpecials = computed(() => props.variant === 'full' && !props.readonly)

function handleCreated(editor: IDomEditor): void {
  editorRef.value = editor
}

function insertSpecial(html: string): void {
  const editor = editorRef.value
  if (!editor) return
  editor.restoreSelection()
  editor.dangerouslyInsertHtml(html)
}

// wangEditor 空内容规范化为 <p><br></p>，且挂载时会迟发一次 onChange（把初始/空内容规范化后
// 回吐）。空内容统一回发 '' 与存储侧对齐；且仅当结果相对传入 modelValue 真正变化时才回发——
// 否则「未编辑即落库 + 产生撤销项」（幽灵脏：挂载即点亮撤销按钮）。用户插入/编辑会改变值故照常回发。
function onChange(editor: IDomEditor): void {
  const v = editor.isEmpty() ? '' : editor.getHtml()
  if (v === props.modelValue) return
  emit('update:modelValue', v)
}

onBeforeUnmount(() => {
  editorRef.value?.destroy()
  editorRef.value = null
})
</script>

<template>
  <div class="rte" :class="{ 'rte--readonly': readonly }">
    <Toolbar
      class="rte-toolbar"
      :editor="editorRef"
      :default-config="toolbarConfig"
      :mode="mode"
    />
    <div v-if="showSpecials" class="rte-specials">
      <el-button
        v-for="b in SPECIAL_BLOCKS"
        :key="b.key"
        size="small"
        text
        @click="insertSpecial(b.html)"
      >
        {{ b.label }}
      </el-button>
    </div>
    <Editor
      class="rte-body"
      :model-value="modelValue"
      :default-config="editorConfig"
      :mode="mode"
      @on-created="handleCreated"
      @on-change="onChange"
    />
  </div>
</template>

<style scoped>
.rte {
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 4px;
  overflow: hidden;
}
.rte-toolbar {
  border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5);
}
.rte-specials {
  display: flex;
  gap: 4px;
  padding: 4px 8px;
  border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5);
  background: #fafafa;
}
.rte-body {
  min-height: 240px;
  overflow-y: auto;
}
.rte--readonly .rte-body {
  background: #fafafa;
}
</style>
