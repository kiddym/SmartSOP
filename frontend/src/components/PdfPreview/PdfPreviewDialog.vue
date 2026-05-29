<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import { downloadPdf, fetchPdfLayout, fetchProcedureDetail } from '@/api/procedures'
import { listNodes } from '@/api/nodes'
import type { ProcedureDetail } from '@/types/procedure'
import {
  LEVEL_OF_USE_LABELS,
  RISK_COLORS,
  RISK_LABELS,
  attachmentMarkText,
  buildModel,
  coverFieldRows,
  execText,
  fmtDate,
  type PreviewModel,
} from './pdfModel'
import { stepZoom, fitZoom, activePageIndex, clampPageInput, pageLabel, ZOOM_MIN, ZOOM_MAX } from './pdfChrome'
import { isAlertType } from '@/utils/editor'
import type { FormType } from '@/types/node'

function alertBlockClass(t: FormType): string {
  return `${t.toLowerCase()}-block`
}

const props = defineProps<{ modelValue: boolean; procedureId: string }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const loading = ref(false)
const downloading = ref(false)
const detail = ref<ProcedureDetail | null>(null)
const model = ref<PreviewModel | null>(null)

const scrollEl = ref<HTMLElement | null>(null)
const docEl = ref<HTMLElement | null>(null)
const zoom = ref(1)
const pageCount = ref(0)
const currentPage = ref(0)
const railOpen = ref(true)
const railEl = ref<HTMLElement | null>(null)
const railItems = ref<{ index: number; label: string }[]>([])
const zoomPct = computed(() => Math.round(zoom.value * 100))

function pageEls(): HTMLElement[] {
  return Array.from(docEl.value?.querySelectorAll<HTMLElement>('.page') ?? [])
}
function zoomIn(): void {
  zoom.value = stepZoom(zoom.value, 1)
}
function zoomOut(): void {
  zoom.value = stepZoom(zoom.value, -1)
}
function fit(): void {
  const cw = scrollEl.value?.clientWidth ?? 0
  const pw = pageEls()[0]?.offsetWidth ?? 0
  zoom.value = fitZoom(cw, pw)
}
function onScroll(): void {
  const tops = pageEls().map((el) => el.offsetTop)
  pageCount.value = tops.length
  currentPage.value = activePageIndex(scrollEl.value?.scrollTop ?? 0, tops)
}
function goPage(i: number): void {
  const n = pageEls().length
  if (n === 0) return
  const clamped = Math.min(n - 1, Math.max(0, i))
  pageEls()[clamped]?.scrollIntoView({ block: 'start' })
  currentPage.value = clamped
}
function prevPage(): void {
  goPage(currentPage.value - 1)
}
function nextPage(): void {
  goPage(currentPage.value + 1)
}
function onPageInput(e: Event): void {
  const el = e.target as HTMLInputElement
  const i = clampPageInput(el.value, pageCount.value)
  if (i !== null) goPage(i)
  el.value = String(currentPage.value + 1) // re-sync after a jump or an invalid entry
}

const meta = computed(() => detail.value?.procedure ?? null)
const watermarkText = computed(() => {
  const s = meta.value?.status
  return s === 'DRAFT' ? '草稿 DRAFT' : s === 'ARCHIVED' ? '已作废 SUPERSEDED' : ''
})
const watermarkClass = computed(() => {
  const s = meta.value?.status
  return s === 'DRAFT' ? 'wm-draft' : s === 'ARCHIVED' ? 'wm-archived' : ''
})

watch(visible, async (open) => {
  if (!open) return
  loading.value = true
  try {
    const [d, nodes, l] = await Promise.all([
      fetchProcedureDetail(props.procedureId),
      listNodes(props.procedureId),
      fetchPdfLayout(props.procedureId),
    ])
    detail.value = d
    model.value = buildModel(d, nodes, l)
      await nextTick()
      zoom.value = 1
      currentPage.value = 0
      pageCount.value = pageEls().length
      railItems.value = pageEls().map((el, i) => ({ index: i, label: pageLabel(el, i) }))
  } catch {
    /* 拦截器已提示 */
    visible.value = false
  } finally {
    loading.value = false
  }
})

watch(currentPage, () => {
  void nextTick(() => {
    railEl.value?.querySelector<HTMLElement>('.pv-rail-item.is-active')?.scrollIntoView({ block: 'nearest' })
  })
})

function levelOfUse(): string {
  const m = meta.value
  if (!m) return ''
  const [cn, en] = LEVEL_OF_USE_LABELS[m.level_of_use] ?? [m.level_of_use, '']
  return `${cn} (${en})`
}

function doPrint(): void {
  window.print()
}

async function doDownload(): Promise<void> {
  downloading.value = true
  try {
    await downloadPdf(props.procedureId)
  } catch {
    /* 拦截器已提示 */
  } finally {
    downloading.value = false
  }
}

// 封面字段：仅 show_on_cover 且有值，select/multi 解析为 label（与下载版一致）
const coverRows = computed(() => (detail.value ? coverFieldRows(detail.value) : []))

// 附件区段页码标签（取后端 layout，对齐下载版页眉）
const attachmentsLabel = computed(() => {
  const m = model.value
  if (!m?.attachmentsPage) return ''
  return m.layout.page_labels[m.attachmentsPage - 1] ?? String(m.attachmentsPage)
})

defineExpose({ model })

function onPreviewClick(e: MouseEvent): void {
  // 富文本内嵌 signature-bar / hold-point「点击激活」（Q204）
  const el = (e.target as HTMLElement).closest('.signature-bar, .hold-point')
  if (el) el.classList.toggle('signed')
}
</script>

<template>
  <el-dialog
    v-model="visible"
    fullscreen
    :show-close="false"
    class="pdf-preview-dialog"
    append-to-body
  >
    <template #header>
      <div class="pv-toolbar no-print">
        <span class="pv-title">PDF 预览 · {{ meta?.code }} {{ meta?.name }}</span>
        <div class="pv-actions">
          <el-button v-if="model && pageCount" size="small" :type="railOpen ? 'primary' : 'default'" @click="railOpen = !railOpen">☰ 目录</el-button>
          <div v-if="model" class="pv-zoom">
            <el-button size="small" :disabled="zoom <= ZOOM_MIN" @click="zoomOut">−</el-button>
            <span class="pv-zoom-pct">{{ zoomPct }}%</span>
            <el-button size="small" :disabled="zoom >= ZOOM_MAX" @click="zoomIn">＋</el-button>
            <el-button size="small" @click="fit">适应</el-button>
          </div>
          <div v-if="model && pageCount" class="pv-pagenav">
            <el-button size="small" :disabled="currentPage <= 0" @click="prevPage">‹ 上一页</el-button>
            <input
              class="pv-pageind pv-pageinput"
              type="text"
              inputmode="numeric"
              :value="currentPage + 1"
              aria-label="跳转到页"
              @change="onPageInput"
              @keyup.enter="onPageInput"
            />
            <span class="pv-pagetotal">/ {{ pageCount }}</span>
            <el-button size="small" :disabled="currentPage >= pageCount - 1" @click="nextPage">下一页 ›</el-button>
          </div>
          <el-button :loading="downloading" @click="doDownload">{{ downloading ? '生成中…' : '下载 PDF' }}</el-button>
          <el-button type="primary" @click="doPrint">打印</el-button>
          <el-button @click="visible = false">关闭</el-button>
        </div>
      </div>
    </template>

    <div class="pv-body">
      <aside v-if="railOpen && model" ref="railEl" class="pv-rail no-print">
        <button
          v-for="it in railItems"
          :key="it.index"
          class="pv-rail-item"
          :class="{ 'is-active': it.index === currentPage }"
          @click="goPage(it.index)"
        >
          <span class="pv-rail-num">{{ it.index + 1 }}</span>
          <span class="pv-rail-label">{{ it.label }}</span>
        </button>
      </aside>
      <div ref="scrollEl" v-loading="loading" class="pv-scroll" @scroll="onScroll">
      <div v-if="model && meta" ref="docEl" class="pv-doc" :style="{ zoom }" @click="onPreviewClick">
        <!-- 封面（§3） -->
        <section class="page cover" :class="watermarkClass" :data-wm="watermarkText">
          <h1 class="cover-title">{{ meta.name }}</h1>
          <div class="cover-meta">
            <p>程序编号: {{ meta.code }}</p>
            <p>版本: Rev.{{ meta.version }}</p>
            <p>用途级别: {{ levelOfUse() }}</p>
            <p v-if="meta.folder_full_path">所属文件夹: {{ meta.folder_full_path }}</p>
            <p>
              风险等级: {{ RISK_LABELS[meta.risk_level] }}（{{ meta.risk_level }}）
              <span class="swatch" :style="{ background: RISK_COLORS[meta.risk_level] }" />
            </p>
            <p>
              质量等级: {{ RISK_LABELS[meta.quality_level] }}（{{ meta.quality_level }}）
              <span class="swatch" :style="{ background: RISK_COLORS[meta.quality_level] }" />
            </p>
            <p v-for="f in coverRows" :key="f.name">{{ f.name }}: {{ f.value }}</p>
            <p>创建日期: {{ fmtDate(meta.created_at) }}</p>
            <p>更新日期: {{ fmtDate(meta.updated_at) }}</p>
            <p v-if="meta.status === 'DRAFT'" class="status-draft">状态: 草稿 DRAFT</p>
            <p v-else-if="meta.status === 'ARCHIVED'" class="status-archived">
              已作废 SUPERSEDED<span v-if="meta.archived_at"> · 作废日期 {{ fmtDate(meta.archived_at) }}</span>
            </p>
          </div>
          <table class="sign-table cover-sign">
            <tr><th>编制</th><th>审核</th><th>批准</th></tr>
            <tr><td>签名:</td><td>签名:</td><td>签名:</td></tr>
            <tr><td>日期:</td><td>日期:</td><td>日期:</td></tr>
          </table>
        </section>

        <!-- 目录（§4） -->
        <section class="page front" :class="watermarkClass" :data-wm="watermarkText">
          <div class="page-header"><span class="ph-title">{{ meta.name }}</span></div>
          <h2 class="sec-title">目录</h2>
          <ul v-if="model.toc.length" class="toc">
            <li v-for="t in model.toc" :key="t.chapter_id" :class="`toc-l${t.level}`">
              <span class="toc-code">{{ t.code }}</span>
              <span class="toc-name">{{ t.title }}</span>
              <span class="toc-dots" />
              <span class="toc-page">{{ t.display_page }}</span>
            </li>
          </ul>
          <p v-else class="muted">（无章节）</p>
        </section>

        <!-- 修订记录（§5） -->
        <section class="page front" :class="watermarkClass" :data-wm="watermarkText">
          <div class="page-header"><span class="ph-title">{{ meta.name }}</span></div>
          <h2 class="sec-title">修订记录</h2>
          <table v-if="model.revision.length" class="grid">
            <tr><th>版本号</th><th>变更类型</th><th>变更日期</th><th>说明</th></tr>
            <tr v-for="(r, i) in model.revision" :key="i">
              <td>{{ r.version }}</td><td>{{ r.changeType }}</td><td>{{ r.changedAt }}</td>
              <td class="pre">{{ r.desc }}</td>
            </tr>
          </table>
          <p v-else class="muted">（无修订记录）</p>
        </section>

        <!-- 正文逐页（§6） -->
        <section
          v-for="pg in model.contentPages"
          :key="pg.page"
          class="page content"
          :class="watermarkClass"
          :data-wm="watermarkText"
        >
          <div class="page-header">
            <span class="ph-title">{{ meta.name }}</span>
            <span class="ph-right">
              <span>程序编号: {{ meta.code }}</span>
              <span>版本: Rev.{{ meta.version }}</span>
              <span>第 {{ pg.label }} 页 / 共 {{ model.layout.total_pages }} 页</span>
            </span>
          </div>
          <p v-if="!pg.blocks.length" class="muted">（程序无内容）</p>
          <template v-for="b in pg.blocks" :key="b.key">
            <component
              :is="`h${Math.min(b.level || 1, 3)}`"
              v-if="b.kind === 'chapter'"
              class="chapter-title"
            >
              <span v-if="b.code" class="ch-code">{{ b.code }}</span> {{ b.title }}
            </component>

            <div v-else-if="b.kind === 'content'" class="content-node" v-html="b.html" />

            <div v-else-if="b.kind === 'step' && b.step" class="step">
              <div class="step-title">
                <span v-if="b.code" class="st-code">{{ b.code }}</span> {{ b.title || '（步骤）' }}
              </div>
              <div
                v-if="isAlertType(b.step.input_schema.type)"
                class="alert"
                :class="alertBlockClass(b.step.input_schema.type)"
                v-html="b.stepContent"
              />
              <!-- 数据类型步骤的 content 被有意隐藏（与编辑器"已隐藏正文"提示一致） -->
              <div
                v-else-if="b.step.input_schema.type === 'COMMON' && b.stepContent"
                class="step-body"
                v-html="b.stepContent"
              />
              <p v-for="(m, i) in b.step.attachment_marks" :key="i" class="mark">
                {{ attachmentMarkText(m) }}
              </p>
              <p v-if="execText(b.step)" class="exec">{{ execText(b.step) }}</p>
              <p
                v-if="model.signoffEnabled && !isAlertType(b.step.input_schema.type)"
                class="signoff"
              >
                签字: __________ 日期: __________
              </p>
            </div>
          </template>
        </section>

        <!-- 附件清单（§6.6）：与下载版同列序、同页码 -->
        <section
          v-if="model.attachments.length"
          class="page content"
          :class="watermarkClass"
          :data-wm="watermarkText"
        >
          <div class="page-header">
            <span class="ph-title">{{ meta.name }}</span>
            <span class="ph-right">
              <span>程序编号: {{ meta.code }}</span>
              <span>版本: Rev.{{ meta.version }}</span>
              <span v-if="attachmentsLabel">
                第 {{ attachmentsLabel }} 页 / 共 {{ model.layout.total_pages }} 页
              </span>
            </span>
          </div>
          <h1 v-if="model.attachmentChapterTitle" class="chapter-title">
            {{ model.attachmentChapterTitle }}
          </h1>
          <table class="grid">
            <tr>
              <th>序号</th><th>文件名</th><th>大小</th><th>类型</th><th>上传日期</th><th>描述</th>
            </tr>
            <tr v-for="a in model.attachments" :key="a.index">
              <td>{{ a.index }}</td>
              <td>{{ a.fileName }}</td>
              <td>{{ a.size }}</td>
              <td>{{ a.mime }}</td>
              <td>{{ a.date }}</td>
              <td>{{ a.description }}</td>
            </tr>
          </table>
        </section>
      </div>
    </div>
    </div>
  </el-dialog>
</template>

<style scoped>
.pv-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}
.pv-title {
  font-weight: 600;
}
.pv-zoom,
.pv-pagenav {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.pv-zoom-pct,
.pv-pageind {
  font-size: 12px;
  min-width: 44px;
  text-align: center;
}
.pv-pageinput {
  width: 34px;
  text-align: center;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 4px;
  font-size: 12px;
  padding: 1px 2px;
}
.pv-pagetotal {
  font-size: 12px;
  color: #909399;
}
.pv-body {
  display: flex;
  height: calc(100vh - 90px);
}
.pv-scroll {
  flex: 1;
  min-width: 0;
  overflow: auto;
  background: #525659;
  padding: 24px 0;
}
.pv-rail {
  width: 200px;
  flex: none;
  overflow-y: auto;
  background: #3a3d42;
  padding: 8px 0;
}
.pv-rail-item {
  display: flex;
  gap: 6px;
  width: 100%;
  text-align: left;
  padding: 4px 10px;
  background: none;
  border: none;
  color: #cfd3dc;
  cursor: pointer;
  font-size: 12px;
  line-height: 1.4;
}
.pv-rail-item:hover {
  background: rgba(255, 255, 255, 0.08);
}
.pv-rail-item.is-active {
  background: var(--el-color-primary, #d97757);
  color: #fff;
}
.pv-rail-num {
  flex: none;
  width: 20px;
  text-align: right;
  opacity: 0.7;
}
.pv-rail-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pv-doc {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 18px;
}
.page {
  position: relative;
  width: 210mm;
  min-height: 297mm;
  padding: 1.27cm 2.03cm;
  background: #fff;
  /* 纸面孤岛：与 docs/design-system.md §3.8「桌上一张文件」语义对齐。
     单一来源 --shadow-paper（tokens.css）；任何幅度调整请回填 §2.4。 */
  box-shadow: var(--shadow-paper);
  box-sizing: border-box;
  font-family: 'SimSun', 'Noto Serif SC', serif;
  font-size: 12pt;
  line-height: 1.5;
  color: #000;
}
/* 水印（§3.4）：45° 斜纹平铺文字 */
.page[data-wm]:not([data-wm=''])::before {
  content: attr(data-wm);
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 30pt;
  font-weight: 700;
  transform: rotate(-45deg);
  pointer-events: none;
  z-index: 0;
  white-space: nowrap;
  letter-spacing: 0.4em;
}
/* 水印色/透明度与后端 constants.WATERMARK 对齐（DRAFT 0.30 / ARCHIVED 0.35） */
.wm-draft[data-wm]:not([data-wm=''])::before {
  color: rgba(200, 200, 200, 0.3);
}
.wm-archived[data-wm]:not([data-wm=''])::before {
  color: rgba(230, 150, 150, 0.35);
}
.page > * {
  position: relative;
  z-index: 1;
}
.cover {
  text-align: center;
}
.cover-title {
  font-family: 'SimHei', 'Noto Sans SC', sans-serif;
  font-size: 22pt;
  margin: 48px 0 18px;
}
.cover-meta p {
  margin: 2px 0;
}
.swatch {
  display: inline-block;
  width: 12px;
  height: 12px;
  vertical-align: middle;
  margin-left: 4px;
}
.status-draft {
  color: #808080;
}
.status-archived {
  color: #dc2626;
  font-family: 'SimHei', 'Noto Sans SC', sans-serif;
}
.sign-table {
  border-collapse: collapse;
  margin: 28px auto 0;
  width: 80%;
}
.sign-table th,
.sign-table td {
  border: 1px solid #000;
  padding: 6px 10px;
  text-align: left;
}
.sign-table th {
  background: #eee;
  text-align: center;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  border-bottom: 1px solid #000;
  padding-bottom: 6px;
  margin-bottom: 12px;
  font-size: 10pt;
}
.ph-title {
  font-size: 11pt;
}
.ph-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}
.sec-title {
  font-family: 'SimHei', 'Noto Sans SC', sans-serif;
  font-size: 16pt;
  margin: 0 0 12px;
}
.toc {
  list-style: none;
  padding: 0;
}
.toc li {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin: 4px 0;
}
.toc-l1 {
  font-family: 'SimHei', 'Noto Sans SC', sans-serif;
  font-size: 14pt;
}
.toc-l2 {
  padding-left: 1em;
}
.toc-l3 {
  padding-left: 2em;
}
.toc-dots {
  flex: 1;
  border-bottom: 1px dotted #888;
  transform: translateY(-3px);
}
.grid {
  border-collapse: collapse;
  width: 100%;
  font-size: 10.5pt;
}
.grid th,
.grid td {
  border: 1px solid #000;
  padding: 4px 5px;
  text-align: left;
  vertical-align: top;
}
.grid th {
  background: #eee;
}
.pre {
  white-space: pre-wrap;
}
.chapter-title {
  font-family: 'SimHei', 'Noto Sans SC', sans-serif;
  margin: 14px 0 6px;
}
h1.chapter-title {
  font-size: 16pt;
}
h2.chapter-title {
  font-size: 14pt;
}
h3.chapter-title {
  font-size: 12pt;
}
.content-node {
  margin: 1em 0;
}
.step {
  margin: 10px 0;
}
.step-title {
  font-family: 'SimHei', 'Noto Sans SC', sans-serif;
  font-size: 14pt;
  font-weight: 700;
  margin: 8px 0 4px;
}
.mark {
  color: #404040;
  font-size: 11pt;
  margin: 2px 0;
}
.exec {
  margin: 4px 0;
}
.signoff {
  text-align: right;
}
.muted {
  color: #888;
  text-align: center;
  margin-top: 12px;
}
/* 警示三色（ANSI Z535，§7） + 富文本内嵌特殊块 */
.alert,
:deep(.note-block),
:deep(.caution-block),
:deep(.warning-block) {
  border-width: 1px;
  border-style: solid;
  padding: 8px 12px;
  margin: 8px 0;
}
.note-block,
:deep(.note-block) {
  background: rgb(204, 229, 255);
  border-color: rgb(13, 71, 161);
}
.caution-block,
:deep(.caution-block) {
  background: rgb(255, 217, 102);
  border-color: #000;
}
.warning-block,
:deep(.warning-block) {
  background: rgb(255, 205, 210);
  border-color: rgb(220, 38, 38);
}
.alert.note-block::before {
  content: 'ⓘ 注意 NOTE';
  display: block;
  font-weight: 700;
  color: rgb(13, 71, 161);
  margin-bottom: 2px;
}
.alert.caution-block::before {
  content: '⚠ 小心 CAUTION';
  display: block;
  font-weight: 700;
  margin-bottom: 2px;
}
.alert.warning-block::before {
  content: '‼ 警告 WARNING';
  display: block;
  font-weight: 700;
  color: rgb(220, 38, 38);
  margin-bottom: 2px;
}
:deep(.hold-point) {
  border: 2px solid rgb(220, 38, 38);
  padding: 10px 12px;
  margin: 12px 0;
  cursor: pointer;
}
:deep(.hold-point.signed) {
  background: rgba(220, 38, 38, 0.08);
}
:deep(.signature-bar) {
  border: 1px dashed #888;
  padding: 8px;
  margin: 8px 0;
  cursor: pointer;
}
:deep(.signature-bar.signed) {
  background: rgba(21, 128, 61, 0.08);
}
:deep(table) {
  border-collapse: collapse;
  width: 100%;
}
:deep(td),
:deep(th) {
  border: 1px solid #000;
  padding: 4px;
}
:deep(img) {
  max-width: 100%;
  display: block;
  margin: 8px auto;
}
</style>

<style>
/* 打印（§6.7 / Q213）：仅留预览文档、隐藏工具栏与对话框 chrome */
@media print {
  body * {
    visibility: hidden;
  }
  .pdf-preview-dialog .pv-doc,
  .pdf-preview-dialog .pv-doc * {
    visibility: visible;
  }
  .no-print {
    display: none !important;
  }
  .pv-scroll {
    height: auto !important;
    overflow: visible !important;
    background: #fff !important;
    padding: 0 !important;
  }
  .pv-doc {
    gap: 0 !important;
    zoom: 1 !important;
  }
  .page {
    box-shadow: none !important;
    page-break-after: always;
    min-height: auto !important;
  }
}
</style>
