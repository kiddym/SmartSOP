<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import ImportTreeRow from './ImportTreeRow.vue'
import ImportMarkingRow from './ImportMarkingRow.vue'
import type { useImportDialog } from '@/composables/useImportDialog'

const props = defineProps<{ ctx: ReturnType<typeof useImportDialog> }>()

const search = ref('')

// 把树压平成可渲染的 FlatRow（含 depth 与可上下移标志）
interface FlatRow {
  node: typeof props.ctx.tree.value[0]
  depth: number
  canMoveUp: boolean
  canMoveDown: boolean
}

function flatten(nodes: typeof props.ctx.tree.value, depth = 0): FlatRow[] {
  const rows: FlatRow[] = []
  nodes.forEach((n, i) => {
    rows.push({
      node: n,
      depth,
      canMoveUp: i > 0,
      canMoveDown: i < nodes.length - 1,
    })
    rows.push(...flatten(n.children, depth + 1))
  })
  return rows
}

const allRows = computed(() => flatten(props.ctx.tree.value))
const visibleRows = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return allRows.value
  return allRows.value.filter((r) =>
    `${r.node.title} ${r.node.rich_content}`.toLowerCase().includes(q),
  )
})

// 平铺标定清单（按搜索过滤；行顺序恒为原文顺序）
const visibleMarkRows = computed(() => {
  const q = search.value.trim().toLowerCase()
  const rows = props.ctx.markRows.value
  if (!q) return rows
  return rows.filter((r) => r.label.toLowerCase().includes(q))
})

function checked(id: string): boolean {
  return props.ctx.markSelection.value.has(id)
}

function levelOf(id: string): string {
  const L = ['', '一级章节', '二级章节', '三级章节']
  const lv = props.ctx.levelMap.value.get(id) ?? 0
  return L[Math.min(lv, 3)] || ''
}

function onMove(id: string, dir: -1 | 1): void {
  props.ctx.selectNode(id)
  props.ctx.moveSelected(dir)
}

async function onRemove(id: string): Promise<void> {
  try {
    await ElMessageBox.confirm('删除该节点及其全部子节点？', '删除确认', { type: 'warning' })
    props.ctx.selectNode(id)
    props.ctx.deleteSelected()
  } catch { /* user cancelled */ }
}

async function onReset(): Promise<void> {
  try {
    await ElMessageBox.confirm('放弃当前所有调整，恢复为初始解析结果？', '重置确认', { type: 'warning' })
    if (props.ctx.parseResult.value) props.ctx.loadParseResult(props.ctx.parseResult.value)
  } catch { /* cancel */ }
}

async function onApplyStepAnnotation(): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `将 ${props.ctx.markSelection.value.size} 个节点标注为「步骤」？提交导入时会一并转换。`,
      '应用标注',
      { type: 'warning' },
    )
    props.ctx.applyStepAnnotation('step')
  } catch { /* cancel */ }
}
</script>

<template>
  <div class="tree-panel">
    <!-- Row① 固定工具栏 -->
    <div class="tb-row">
      <el-input v-model="search" size="small" placeholder="搜索章节 / 步骤..." clearable class="search" />
      <span class="spacer" />
      <el-button
        size="small"
        :type="ctx.mode.value === 'layer-marking' ? 'primary' : ''"
        @click="ctx.toggleLayerMarking"
      >🏷 层级标定</el-button>
      <el-button
        size="small"
        :type="ctx.mode.value === 'step-annotation' ? 'warning' : ''"
        @click="ctx.toggleStepAnnotation"
      >⚑ 步骤标注</el-button>
      <el-button size="small" @click="onReset">↺ 重置</el-button>
    </div>

    <!-- Row② 动态条 -->
    <div class="tb-row tb-row-dynamic">
      <template v-if="ctx.mode.value === 'normal'">
        <template v-if="!ctx.selected.value">
          <span class="ctx-label">根级：</span>
          <el-button size="small" @click="ctx.addChild(null, 'chapter')">+章节</el-button>
          <el-button size="small" @click="ctx.addChild(null, 'content')">+内容</el-button>
        </template>
        <template v-else>
          <span class="ctx-label">「{{ levelOf(ctx.selected.value.id) }} · {{ ctx.selected.value.title || '（无标题）' }}」：</span>
          <el-button size="small" @click="ctx.addChild(ctx.selectedId.value!, 'chapter')">+子章节</el-button>
          <el-button size="small" @click="ctx.addChild(ctx.selectedId.value!, 'content')">+内容</el-button>
        </template>
      </template>

      <template v-else-if="ctx.mode.value === 'layer-marking'">
        <span class="ctx-label">逐段选择级别（只需改解析错的行）：</span>
        <span class="spacer" />
        <el-button size="small" type="primary" @click="ctx.exitMode">完成</el-button>
      </template>

      <template v-else>
        <el-button size="small" @click="ctx.exitMode">← 退出</el-button>
        <span class="ctx-label">已选 {{ ctx.markSelection.value.size }} 项：</span>
        <el-button size="small" type="warning" :disabled="!ctx.markSelection.value.size" @click="onApplyStepAnnotation">→ 步骤</el-button>
        <el-button size="small" :disabled="!ctx.markSelection.value.size" @click="ctx.applyStepAnnotation('content')">→ 内容</el-button>
        <el-button size="small" :disabled="!ctx.markSelection.value.size" @click="ctx.clearStepAnnotation">清除标注</el-button>
      </template>
    </div>

    <!-- 树体 / 平铺标定清单 -->
    <div class="tree-scroll">
      <template v-if="ctx.mode.value === 'layer-marking'">
        <ImportMarkingRow
          v-for="row in visibleMarkRows"
          :key="row.id"
          :label="row.label"
          :role="ctx.roleMap.value.get(row.id) ?? row.defaultRole"
          :indent="ctx.markIndents.value.get(row.id) ?? 0"
          @set="(r) => ctx.setRole(row.id, r)"
        />
        <el-empty v-if="!visibleMarkRows.length" description="无可标定内容" :image-size="60" />
      </template>
      <template v-else>
        <ImportTreeRow
          v-for="row in visibleRows"
          :key="row.node.id"
          :node="row.node"
          :depth="row.depth"
          :level="ctx.levelMap.value.get(row.node.id) ?? 1"
          :number="ctx.numberMap.value[row.node.id] ?? ''"
          :selected="ctx.selectedId.value === row.node.id"
          :mode="ctx.mode.value"
          :checked="checked(row.node.id)"
          :can-move-up="row.canMoveUp"
          :can-move-down="row.canMoveDown"
          @select="ctx.mode.value === 'normal' ? ctx.selectNode(row.node.id) : ctx.toggleMarkSelection(row.node.id)"
          @check="() => ctx.toggleMarkSelection(row.node.id)"
          @move="(dir) => onMove(row.node.id, dir)"
          @remove="onRemove(row.node.id)"
        />
        <el-empty v-if="!visibleRows.length" description="树为空" :image-size="60" />
      </template>
    </div>

    <!-- 底部忽略区（保留：仅展示/恢复，已无新增入口） -->
    <div v-if="ctx.ignored.value.length" class="ignored-bar">
      <el-collapse>
        <el-collapse-item :title="`已忽略 (${ctx.ignored.value.length} 项)`" name="ig">
          <div v-for="n in ctx.ignored.value" :key="n.id" class="ignored-row">
            <el-tag size="small" type="info" disable-transitions>忽略</el-tag>
            <span class="ig-text">{{ n.title || '(无标题)' }}</span>
            <span class="spacer" />
            <el-button size="small" text @click="ctx.restoreIgnored(n.id)">恢复</el-button>
          </div>
          <div class="ignored-footer">
            <el-button size="small" @click="ctx.restoreAllIgnored">全部恢复</el-button>
          </div>
        </el-collapse-item>
      </el-collapse>
    </div>
  </div>
</template>

<style scoped>
.tree-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  border-right: 1px solid var(--el-border-color-lighter, #ebeef5);
}
.tb-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px;
  min-height: 44px;
  border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5);
}
.tb-row-dynamic { background: #fafbfc; }
.search { max-width: 240px; }
.spacer { flex: 1; }
.ctx-label { font-size: 12px; color: #606266; margin-right: 4px; }
.tree-scroll { flex: 1; overflow-y: auto; }
.ignored-bar { border-top: 1px solid var(--el-border-color-lighter, #ebeef5); background: #fafafa; }
.ignored-row { display: flex; align-items: center; gap: 8px; padding: 4px 12px; font-size: 13px; color: #606266; }
.ig-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 360px; }
.ignored-footer { padding: 6px 12px; text-align: right; }
</style>
