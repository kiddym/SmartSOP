<script setup lang="ts">
import { computed } from 'vue'
import type { WizardNode } from '@/utils/importTree'

const props = defineProps<{
  node: WizardNode
  level: number
  number: string
  children: { id: string; title: string; number: string; kind: 'chapter' | 'content' }[]
}>()
const emit = defineEmits<{
  (e: 'update', patch: { title?: string; skip_numbering?: boolean }): void
  (e: 'accept-review'): void
  (e: 'select-child', id: string): void
}>()

const LEVEL_LABEL = ['', '一级章节', '二级章节', '三级章节']
const levelLabel = computed(() => LEVEL_LABEL[Math.min(props.level, 3)] || '章节')
const titleModel = computed<string>({
  get: () => props.node.title,
  set: (v) => emit('update', { title: v }),
})
const skipModel = computed<boolean>({
  get: () => props.node.skip_numbering,
  set: (v) => emit('update', { skip_numbering: v }),
})
</script>

<template>
  <div class="card">
    <div class="head">
      <div class="badge">📘 {{ levelLabel }}</div>
      <div class="title-line">
        <span v-if="number" class="num">{{ number }}</span>
        <span class="title">{{ node.title || '（无标题）' }}</span>
      </div>
    </div>

    <el-form label-position="top" class="form">
      <el-form-item label="标题">
        <el-input v-model="titleModel" maxlength="500" placeholder="章节标题" />
      </el-form-item>
      <el-form-item>
        <el-checkbox v-model="skipModel">跳过自动编号</el-checkbox>
      </el-form-item>
      <el-form-item v-if="node.mark_status === 'review'">
        <el-button size="small" type="warning" plain @click="emit('accept-review')">✓ 接受待确认</el-button>
      </el-form-item>
    </el-form>

    <el-divider content-position="left">子节点（{{ children.length }}）</el-divider>
    <div v-if="children.length" class="children">
      <div v-for="c in children" :key="c.id" class="child" @click="emit('select-child', c.id)">
        <el-tag size="small" :type="c.kind === 'content' ? 'info' : 'primary'" disable-transitions>
          {{ c.kind === 'content' ? '正文' : '章节' }}
        </el-tag>
        <span v-if="c.number" class="cnum">{{ c.number }}</span>
        <span class="ctitle">{{ c.title || '(无标题)' }}</span>
      </div>
    </div>
    <el-empty v-else description="暂无子节点" :image-size="48" />
  </div>
</template>

<style scoped>
.card { padding: 16px; }
.head { margin-bottom: 12px; }
.badge { display: inline-block; padding: 2px 8px; background: #ecf5ff; color: #409eff; border-radius: 4px; font-size: 12px; }
.title-line { margin-top: 6px; display: flex; align-items: baseline; gap: 8px; }
.num { color: #409eff; font-weight: 600; }
.title { font-size: 15px; font-weight: 600; }
.form { margin-top: 8px; }
.children { display: flex; flex-direction: column; gap: 4px; }
.child { display: flex; align-items: center; gap: 8px; padding: 6px 8px; border: 1px solid #ebeef5; border-radius: 4px; cursor: pointer; font-size: 13px; }
.child:hover { background: #f5f7fa; }
.cnum { color: #888; font-variant-numeric: tabular-nums; }
.ctitle { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
