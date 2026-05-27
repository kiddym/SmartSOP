<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'
import { computeFallback, formatCode } from '@/utils/editor'
import type { NodeKind } from '@/types/node'

// chapter 节点详情（§4.1）：仅标题 + 跳号 + 子节点只读列表，无 WangEditor（§19）。
const store = useProcedureEditorStore()
const chapter = computed(() => store.selectedChapter)
const ro = computed(() => !store.editable)

const titleRef = ref<{ focus: () => void } | null>(null)
onMounted(() => {
  if (chapter.value && !chapter.value.title.trim()) titleRef.value?.focus()
})

function onTitle(value: string): void {
  const id = chapter.value?.id
  if (id) store.updateChapterFields(id, { title: value }, `title:${id}`)
}

// ---- 光标跟踪 / 拆分按钮 ---- //
const cursorOffset = ref<number | null>(null)

function refreshCursor(event?: Event): void {
  const target = event?.target as HTMLTextAreaElement | null
  if (target && target.tagName === 'TEXTAREA') {
    cursorOffset.value = target.selectionStart ?? null
    return
  }
  // 回退：尝试通过 EP ref 获取 textarea 元素
  const inputEl = titleRef.value as unknown as { textarea?: { value?: HTMLTextAreaElement } }
  const el = inputEl?.textarea?.value
  if (el) {
    cursorOffset.value = el.selectionStart ?? null
    return
  }
  cursorOffset.value = null
}

const splitDisabled = computed(() => {
  if (ro.value) return true
  const ch = chapter.value
  if (!ch || !ch.title.trim()) return true
  const c = cursorOffset.value
  if (c === null) return true
  if (c <= 0 || c >= ch.title.length) return true
  return false
})

function onSplit(): void {
  const ch = chapter.value
  const c = cursorOffset.value
  if (!ch || c === null) return
  void store.splitChapterTitleContent(ch.id, c)
}

interface ChildRow {
  id: string
  code: string
  text: string
  kind: NodeKind
}
const children = computed<ChildRow[]>(() => {
  const ch = chapter.value
  if (!ch) return []
  const { chapterCodes, stepCodes } = store.codeMaps
  const levels = store.levelMap
  const rows: (ChildRow & { sort: number })[] = []
  for (const c of store.chapters.filter((c) => c.parent_id === ch.id)) {
    const kind: NodeKind = 'chapter'
    rows.push({
      id: c.id,
      kind,
      sort: c.sort_order,
      code: formatCode({ kind, level: levels.get(c.id) ?? 1, code: chapterCodes.get(c.id) ?? '', skipNumbering: c.skip_numbering }),
      text: c.title.trim() || computeFallback('chapter', ''),
    })
  }
  for (const s of store.steps.filter((s) => s.chapter_id === ch.id)) {
    const kind: NodeKind = s.kind === 'content' ? 'content' : 'step'
    rows.push({
      id: s.id,
      kind,
      sort: s.sort_order,
      code: formatCode({ kind, level: 0, code: stepCodes.get(s.id) ?? '', skipNumbering: s.skip_numbering }),
      text: s.title.trim() || computeFallback(kind, s.content),
    })
  }
  return rows.sort((a, b) => a.sort - b.sort).map(({ sort: _sort, ...r }) => r)
})
</script>

<template>
  <div v-if="chapter" class="chapter-detail">
    <div v-if="chapter.mark_status === 'review' && !ro" class="review-banner">
      <span>⚠ 解析存疑（待确认）——确认结构无误后接受</span>
      <el-button size="small" type="warning" plain @click="store.acceptReview(chapter.id)">接受待确认</el-button>
    </div>
    <el-form label-position="top">
      <el-form-item label="章节标题">
        <div class="title-row">
          <el-input
            ref="titleRef"
            :model-value="chapter.title"
            type="textarea"
            autosize
            maxlength="500"
            show-word-limit
            :disabled="ro"
            placeholder="输入章节标题"
            @input="onTitle"
            @focus="refreshCursor"
            @blur="refreshCursor"
            @click="refreshCursor"
            @keyup="refreshCursor"
            @select="refreshCursor"
          />
          <div class="skip">
            <span class="skip-label">跳号</span>
            <el-switch
              :model-value="chapter.skip_numbering"
              :disabled="ro"
              @change="store.toggleSkipNumbering(chapter.id)"
            />
          </div>
        </div>
      </el-form-item>
      <div class="split-row">
        <el-button
          size="small"
          type="primary"
          plain
          data-test="split-title-content-btn"
          :disabled="splitDisabled"
          @click="onSplit"
        >
          在光标处拆为标题 + 内容
        </el-button>
        <span v-if="!splitDisabled" class="split-hint">将把光标后的文本变为本章节首个内容块</span>
      </div>
    </el-form>

    <el-divider content-position="left">子节点（在左侧树增删）</el-divider>
    <div v-if="children.length" class="child-list">
      <div v-for="c in children" :key="c.id" class="child" @click="store.selectNode(c.id)">
        <span class="child-code">{{ c.code }}</span>
        <span class="child-text">{{ c.text }}</span>
        <el-tag size="small" :type="c.kind === 'step' ? 'success' : c.kind === 'content' ? 'info' : 'primary'">
          {{ c.kind === 'step' ? '步骤' : c.kind === 'content' ? '内容' : '章节' }}
        </el-tag>
      </div>
    </div>
    <el-empty v-else description="暂无子节点" :image-size="48" />
  </div>
</template>

<style scoped>
.review-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
  padding: 6px 10px;
  font-size: 13px;
  color: #b88230;
  background: #fdf6ec;
  border: 1px solid #f5dab1;
  border-radius: 4px;
}
.title-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  width: 100%;
}
.title-row :deep(.el-textarea) {
  flex: 1;
}
.skip {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding-top: 4px;
}
.skip-label {
  font-size: 12px;
  color: #909399;
}
.split-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 8px 0;
}
.split-hint {
  font-size: 12px;
  color: #909399;
}
.child-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.child {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-radius: 4px;
  cursor: pointer;
}
.child:hover {
  background: var(--el-fill-color-light, #f5f7fa);
}
.child-code {
  color: #888;
  font-variant-numeric: tabular-nums;
}
.child-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
