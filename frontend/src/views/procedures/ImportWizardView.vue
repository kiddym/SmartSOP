<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { watchDebounced } from '@vueuse/core'
import type { AxiosError } from 'axios'
import UploadStep from '@/components/import/UploadStep.vue'
import ModeStep from '@/components/import/ModeStep.vue'
import ReviewReportStep from '@/components/import/ReviewReportStep.vue'
import BlockMarkingStep from '@/components/import/BlockMarkingStep.vue'
import TreeReviewStep from '@/components/import/TreeReviewStep.vue'
import ImportFormStep from '@/components/import/ImportFormStep.vue'
import { importProcedure, parseDocx, uploadDocx } from '@/api/parse'
import {
  buildMarkedBlocks,
  rebuildTreeFromMarks,
  toImportNodesFromBlocks,
  validateMarkedBlocks,
  type MarkedImportBlock,
} from '@/utils/importBlocks'
import {
  buildWizardTree,
  cloneTree,
  countReview,
  toImportNodes,
  type WizardNode,
} from '@/utils/importTree'
import { uploadSizeTier } from '@/utils/upload'
import {
  clearWizard,
  loadWizard,
  saveWizard,
  type WizardSnapshot,
} from '@/composables/useImportWizardPersistence'
import type { ParseMode, ParseResponse, ValidationReport } from '@/types/parse'

const router = useRouter()

const STEPS = ['上传文档', '解析模式', '校验报告', '章节标定', '树审查', '导入信息']
const step = ref(0)

const file = ref<File | null>(null)
const uploadToken = ref('')
const filename = ref('')
const parseMode = ref<ParseMode>('smart')
const parseResult = ref<ParseResponse | null>(null)
const markedBlocks = ref<MarkedImportBlock[]>([])
const markIssues = computed(() => validateMarkedBlocks(markedBlocks.value))
const initialTree = ref<WizardNode[]>([])
const tree = ref<WizardNode[]>([])
const form = reactive({ name: '', folder_id: '' })

const uploading = ref(false)
const parsing = ref(false)
const importing = ref(false)
const submitted = ref(false)
const parseErrorMessage = ref('')
const parseErrorValidation = ref<ValidationReport | null>(null)

const reviewCount = computed(() => countReview(tree.value))
const hasProgress = computed(() => !!file.value || !!uploadToken.value)

// ---- step1：选文件 ---- //
function onSelect(f: File): void {
  file.value = f
  filename.value = f.name
  uploadToken.value = '' // 换文件作废旧 token + 解析结果
  parseResult.value = null
  parseErrorMessage.value = ''
  tree.value = []
}
function onClear(): void {
  file.value = null
  filename.value = ''
  uploadToken.value = ''
  parseResult.value = null
  tree.value = []
  clearWizard() // 主动移除文件即作废已保存进度，避免下次恢复到指向已移除文件的 token
}

const canNext = computed(() => {
  if (step.value === 0) return !!file.value && uploadSizeTier(file.value.size).tier !== 'error'
  if (step.value === 2) return !!parseResult.value && !parseErrorMessage.value
  if (step.value === 3) return markedBlocks.value.length > 0 && !markIssues.value.some((i) => i.level === 'error')
  if (step.value === 4) return tree.value.length > 0
  return true
})

function defaultName(): string {
  return filename.value.replace(/\.docx$/i, '').trim()
}

function applyParse(res: ParseResponse): void {
  parseResult.value = res
  markedBlocks.value = buildMarkedBlocks(res.import_blocks)
  initialTree.value = rebuildTreeFromMarks(markedBlocks.value) as WizardNode[]
  tree.value = cloneTree(initialTree.value)
  parseErrorMessage.value = ''
  parseErrorValidation.value = null
  if (!form.name) form.name = defaultName()
}

function parseErr(e: unknown): void {
  const ax = e as AxiosError<{ detail?: { message?: string; validation?: ValidationReport } }>
  // 后端 30s 线程超时会先返回 504 PARSE_TIMEOUT（走下方 message 分支）；
  // 这里的 ECONNABORTED 仅在客户端 45s 都未收到响应（网络/服务无响应）时触发。
  if (ax.code === 'ECONNABORTED') {
    parseErrorMessage.value = '请求超时：服务无响应，请检查网络后重试（文档过大也可能导致解析过久）。'
    parseErrorValidation.value = null
    return
  }
  const d = ax.response?.data?.detail
  parseErrorMessage.value = d?.message ?? '解析失败，请重试。'
  parseErrorValidation.value = d?.validation ?? null
}

async function ensureUploaded(): Promise<boolean> {
  if (uploadToken.value) return true
  if (!file.value) return false
  uploading.value = true
  try {
    const res = await uploadDocx(file.value)
    uploadToken.value = res.upload_token
    if (!filename.value) filename.value = res.filename
    return true
  } catch {
    return false // 拦截器已提示
  } finally {
    uploading.value = false
  }
}

async function runParse(): Promise<void> {
  if (!uploadToken.value) return
  parsing.value = true
  parseResult.value = null
  parseErrorMessage.value = ''
  parseErrorValidation.value = null
  try {
    applyParse(await parseDocx(uploadToken.value, parseMode.value))
  } catch (e) {
    parseErr(e)
  } finally {
    parsing.value = false
  }
}

async function next(): Promise<void> {
  if (!canNext.value) return
  if (step.value === 0) {
    if (await ensureUploaded()) step.value = 1
    return
  }
  if (step.value === 1) {
    step.value = 2
    await runParse() // 进入报告页即解析（可能成功 / 失败，均停在报告页）
    return
  }
  if (step.value === 3) {
    initialTree.value = rebuildTreeFromMarks(markedBlocks.value) as WizardNode[]
    tree.value = cloneTree(initialTree.value)
    step.value += 1
    return
  }
  if (step.value === 5) {
    await submit()
    return
  }
  step.value += 1
}

function prev(): void {
  if (step.value > 0) step.value -= 1
}

function goto(i: number): void {
  if (i < step.value) step.value = i // 仅允许回跳已完成步骤
}

async function submit(): Promise<void> {
  if (!form.name.trim()) {
    ElMessage.warning('请输入程序名称')
    return
  }
  if (!form.folder_id) {
    ElMessage.warning('请选择目标文件夹')
    return
  }
  importing.value = true
  try {
    const proc = await importProcedure({
      name: form.name.trim(),
      folder_id: form.folder_id,
      description: '',
      chapters: toImportNodes(tree.value), // 内部清 review（Q354）
    })
    submitted.value = true
    clearWizard()
    ElMessage.success(`已导入 ${proc.code}`)
    void router.push(`/procedures/${proc.id}`)
  } catch {
    /* 拦截器已提示（REVIEW_NOT_CLEARED / 校验失败等） */
  } finally {
    importing.value = false
  }
}

// ---- 持久化（Q353） ---- //
function snapshot(): WizardSnapshot {
  return {
    created_at: new Date().toISOString(),
    step: step.value,
    upload_token: uploadToken.value,
    filename: filename.value,
    parse_mode: parseMode.value,
    parse_result: parseResult.value,
    tree: tree.value,
    marked_blocks: markedBlocks.value,
    form: { ...form },
  }
}

function restore(s: WizardSnapshot): void {
  step.value = s.step
  uploadToken.value = s.upload_token
  filename.value = s.filename
  parseMode.value = s.parse_mode
  parseResult.value = s.parse_result
  tree.value = s.tree
  markedBlocks.value = s.marked_blocks ?? (s.parse_result?.import_blocks?.length ? buildMarkedBlocks(s.parse_result.import_blocks) : [])
  if (s.parse_result) initialTree.value = buildWizardTree(s.parse_result.chapters)
  form.name = s.form.name
  form.folder_id = s.form.folder_id
}

onMounted(async () => {
  const saved = loadWizard()
  if (saved && saved.upload_token) {
    try {
      await ElMessageBox.confirm(
        `检测到上次未完成的导入进度（${saved.filename || '未命名'}），是否恢复？`,
        '恢复导入',
        { confirmButtonText: '恢复', cancelButtonText: '重新开始', type: 'info' },
      )
      restore(saved)
    } catch {
      clearWizard()
    }
  }
  // 仅在已上传后才持久化（向导无 id，单一全局键）。
  watchDebounced(
    () => [step.value, uploadToken.value, parseMode.value, parseResult.value, tree.value, form],
    () => {
      if (uploadToken.value) saveWizard(snapshot())
    },
    { debounce: 1000, deep: true },
  )
})

onBeforeRouteLeave(async () => {
  if (submitted.value || !hasProgress.value) {
    return true
  }
  try {
    await ElMessageBox.confirm('导入向导尚未完成，离开将保留当前进度（24 小时内可恢复）。确认离开？', '离开向导', {
      confirmButtonText: '离开',
      cancelButtonText: '留在本页',
      type: 'warning',
    })
    return true
  } catch {
    return false
  }
})

function discardAndExit(): void {
  void ElMessageBox.confirm('放弃本次导入并清除已保存进度？', '放弃导入', { type: 'warning' }).then(
    () => {
      submitted.value = true // 跳过离开守卫
      clearWizard()
      void router.push({ name: 'procedure-library' })
    },
  )
}
</script>

<template>
  <div class="wizard">
    <div class="head">
      <h2 class="title">从 Word 导入程序</h2>
      <el-button text @click="discardAndExit">放弃并返回</el-button>
    </div>

    <el-steps :active="step" finish-status="success" align-center class="steps">
      <el-step
        v-for="(s, i) in STEPS"
        :key="i"
        :title="s"
        :style="{ cursor: i < step ? 'pointer' : 'default' }"
        @click="goto(i)"
      />
    </el-steps>

    <div class="content">
      <UploadStep v-show="step === 0" :file="file" :filename="filename" @select="onSelect" @clear="onClear" />
      <ModeStep v-show="step === 1" v-model="parseMode" />
      <ReviewReportStep
        v-show="step === 2"
        :parsing="parsing"
        :parse-result="parseResult"
        :parse-mode="parseMode"
        :error-message="parseErrorMessage"
        :error-validation="parseErrorValidation"
        :review-count="reviewCount"
      />
      <BlockMarkingStep v-show="step === 3" v-model="markedBlocks" />
      <TreeReviewStep v-show="step === 4" v-model="tree" :initial="initialTree" />
      <ImportFormStep
        v-show="step === 5"
        v-model:name="form.name"
        v-model:folder-id="form.folder_id"
      />
    </div>

    <div class="footer">
      <el-button v-if="step > 0" @click="prev">上一步</el-button>
      <span class="spacer" />
      <el-button
        v-if="step < 5"
        type="primary"
        :loading="uploading || parsing"
        :disabled="!canNext"
        @click="next"
      >
        {{ step === 1 ? '解析' : '下一步' }}
      </el-button>
      <el-button v-else type="success" :loading="importing" @click="next">提交导入</el-button>
    </div>
  </div>
</template>

<style scoped>
.wizard {
  max-width: 960px;
  margin: 0 auto;
  padding: 8px 4px 40px;
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.title {
  margin: 0;
  font-size: 18px;
}
.steps {
  margin-bottom: 20px;
}
.content {
  min-height: 320px;
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-radius: 6px;
  padding: 16px 20px;
}
.footer {
  display: flex;
  align-items: center;
  margin-top: 20px;
}
.spacer {
  flex: 1;
}
</style>
