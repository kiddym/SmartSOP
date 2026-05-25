<script setup lang="ts">
import { computed } from 'vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'
import { computeFallback, formatCode } from '@/utils/editor'
import type { NodeKind } from '@/types/node'

// chapter 节点详情（§4.1）：仅标题 + 跳号 + 子节点只读列表，无 WangEditor（§19）。
const store = useProcedureEditorStore()
const chapter = computed(() => store.selectedChapter)
const ro = computed(() => !store.editable)

function onTitle(value: string): void {
  const id = chapter.value?.id
  if (id) store.updateChapterFields(id, { title: value }, `title:${id}`)
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
    const kind: NodeKind = c.content_type === 'content' ? 'content' : 'chapter'
    rows.push({
      id: c.id,
      kind,
      sort: c.sort_order,
      code: formatCode({ kind, level: levels.get(c.id) ?? 1, code: chapterCodes.get(c.id) ?? '', skipNumbering: c.skip_numbering }),
      text: c.title.trim() || computeFallback(kind, c.rich_content),
    })
  }
  for (const s of store.steps.filter((s) => s.chapter_id === ch.id)) {
    rows.push({
      id: s.id,
      kind: 'step',
      sort: s.sort_order,
      code: formatCode({ kind: 'step', level: 0, code: stepCodes.get(s.id) ?? '', skipNumbering: s.skip_numbering }),
      text: s.title.trim() || computeFallback('step', s.content),
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
      <el-form-item label="节点类型">
        <el-radio-group
          :model-value="chapter.content_type"
          :disabled="ro"
          size="small"
          @change="store.toggleContentType(chapter.id)"
        >
          <el-radio-button value="chapter">章节</el-radio-button>
          <el-radio-button value="content">内容块</el-radio-button>
        </el-radio-group>
        <el-button
          v-if="chapter.content_type === 'content' && !ro"
          size="small"
          type="primary"
          plain
          style="margin-left: 8px"
          @click="store.promoteContentToChapter(chapter.id)"
        >
          提升为章节
        </el-button>
      </el-form-item>

      <el-form-item label="章节标题">
        <div class="title-row">
          <el-input
            :model-value="chapter.title"
            type="textarea"
            autosize
            maxlength="500"
            show-word-limit
            :disabled="ro"
            placeholder="输入章节标题"
            @input="onTitle"
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
