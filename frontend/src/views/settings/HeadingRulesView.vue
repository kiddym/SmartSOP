<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listHeadingRules,
  createHeadingRule,
  updateHeadingRule,
  deleteHeadingRule,
  type HeadingRule,
} from '@/api/headingRules'
import {
  listNumberingProfiles,
  createNumberingProfile,
  updateNumberingProfile,
  deleteNumberingProfile,
  type NumberingProfile,
} from '@/api/numberingProfiles'

// 动态标题字典管理（方案 M4 §7.3）：列出 learned/manual 规则 + 来源/状态/证据/投票，
// 支持改层级（钉为 manual）、启停、删除。内置 yaml 词典不入此表、不在此管理。
const LEVEL_OPTIONS = [
  { value: null as number | null, label: '非标题（正文）' },
  { value: 1, label: '一级' },
  { value: 2, label: '二级' },
  { value: 3, label: '三级' },
]
const SOURCE_LABEL: Record<string, string> = { manual: '钉死', learned: '自学习', disabled: '停用' }
const SOURCE_TAG: Record<string, '' | 'success' | 'info' | 'warning'> = {
  manual: 'success',
  learned: 'info',
  disabled: 'warning',
}
const STATUS_LABEL: Record<string, string> = {
  active: '生效',
  candidate: '待定',
  disabled: '停用',
}

const rules = ref<HeadingRule[]>([])
const loading = ref(false)
const newName = ref('')
const newLevel = ref<number | null>(1)

async function load(): Promise<void> {
  loading.value = true
  try {
    rules.value = await listHeadingRules()
  } catch {
    ElMessage.error('加载字典失败')
  } finally {
    loading.value = false
  }
}

function levelLabel(level: number | null): string {
  return LEVEL_OPTIONS.find((o) => o.value === level)?.label ?? '—'
}

function votesText(votes: Record<string, number>): string {
  const entries = Object.entries(votes)
  if (entries.length === 0) return '—'
  return entries.map(([k, v]) => `${k === 'content' ? '正文' : 'L' + k}:${v}`).join(' / ')
}

async function addRule(): Promise<void> {
  const name = newName.value.trim()
  if (!name) {
    ElMessage.warning('请输入样式名')
    return
  }
  try {
    await createHeadingRule(name, newLevel.value)
    newName.value = ''
    ElMessage.success('已新增规则')
    await load()
  } catch {
    ElMessage.error('新增失败（样式名可能已存在）')
  }
}

async function changeLevel(rule: HeadingRule, level: number | null): Promise<void> {
  try {
    await updateHeadingRule(rule.id, { level })
    ElMessage.success(`已钉死「${rule.style_name}」为${levelLabel(level)}`)
    await load()
  } catch {
    ElMessage.error('修改失败')
  }
}

async function toggleStatus(rule: HeadingRule): Promise<void> {
  const next = rule.status === 'active' ? 'disabled' : 'active'
  try {
    await updateHeadingRule(rule.id, { status: next })
    ElMessage.success(next === 'active' ? '已启用' : '已停用')
    await load()
  } catch {
    ElMessage.error('操作失败')
  }
}

async function removeRule(rule: HeadingRule): Promise<void> {
  try {
    await ElMessageBox.confirm(`删除「${rule.style_name}」规则？删除后该样式回退到内置词典/启发式判定。`, '删除确认', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await deleteHeadingRule(rule.id)
    ElMessage.success('已删除')
    await load()
  } catch {
    ElMessage.error('删除失败')
  }
}

// ── 编号体例（M4b）──────────────────────────────────────────
// 常见编号 pattern_key（与后端 classify_numbering 产出一致），供下拉选择。
const PATTERN_OPTIONS = ['第X章', '第X节', '第X条', '一、', 'N、', 'N.N、', 'N.N.N、', 'N.', 'N 空格', 'N+中文']
const KIND_OPTIONS = [
  { value: 'heading', label: '标题' },
  { value: 'weak_heading', label: '弱标题（需加粗）' },
  { value: 'list', label: '非标题（列表/正文）' },
]

const profiles = ref<NumberingProfile[]>([])
const loadingP = ref(false)
const newPattern = ref('第X条')
const newKind = ref('heading')
const newProfLevel = ref<number | null>(3)

async function loadProfiles(): Promise<void> {
  loadingP.value = true
  try {
    profiles.value = await listNumberingProfiles()
  } catch {
    ElMessage.error('加载编号体例失败')
  } finally {
    loadingP.value = false
  }
}

async function addProfile(): Promise<void> {
  const key = newPattern.value.trim()
  if (!key) {
    ElMessage.warning('请选择/输入编号模式')
    return
  }
  try {
    await createNumberingProfile(key, newKind.value, newKind.value === 'heading' ? newProfLevel.value : null)
    ElMessage.success('已新增编号体例')
    await loadProfiles()
  } catch {
    ElMessage.error('新增失败（编号模式可能已存在）')
  }
}

async function changeProfile(p: NumberingProfile, patch: { kind?: string; level?: number | null }): Promise<void> {
  try {
    await updateNumberingProfile(p.id, patch)
    await loadProfiles()
  } catch {
    ElMessage.error('修改失败')
  }
}

async function toggleProfileStatus(p: NumberingProfile): Promise<void> {
  const next = p.status === 'active' ? 'disabled' : 'active'
  try {
    await updateNumberingProfile(p.id, { status: next })
    await loadProfiles()
  } catch {
    ElMessage.error('操作失败')
  }
}

async function removeProfile(p: NumberingProfile): Promise<void> {
  try {
    await ElMessageBox.confirm(`删除编号体例「${p.pattern_key}」？删除后回退到内置编号判定。`, '删除确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteNumberingProfile(p.id)
    ElMessage.success('已删除')
    await loadProfiles()
  } catch {
    ElMessage.error('删除失败')
  }
}

onMounted(() => {
  void load()
  void loadProfiles()
})
</script>

<template>
  <div class="heading-rules-page">
    <h2 class="page-title">标题字典</h2>
    <p class="hint">
      动态识别字典：样式名 → 标题层级。「自学习」规则由编辑器中的反复改级/确认自动积累；
      「钉死」为人工确认或管理员修改，自学习不再覆盖。内置中文词典随程序发布、不在此列。
    </p>

    <el-card class="add-card">
      <div class="add-row">
        <el-input v-model="newName" class="add-name" placeholder="样式名（如：章节标题）" />
        <el-select v-model="newLevel" class="add-level">
          <el-option v-for="o in LEVEL_OPTIONS" :key="String(o.value)" :value="o.value as number" :label="o.label" />
        </el-select>
        <el-button type="primary" class="add-btn" @click="addRule">新增规则</el-button>
      </div>
    </el-card>

    <el-card v-loading="loading">
      <el-table :data="rules" class="rules-table" empty-text="暂无动态规则（先在编辑器「记住此样式」或在上方新增）">
        <el-table-column prop="style_name" label="样式名" min-width="160" />
        <el-table-column label="层级" width="170">
          <template #default="{ row }">
            <el-select
              :model-value="row.level"
              size="small"
              class="lvl-select"
              @change="(v: number | null) => changeLevel(row, v)"
            >
              <el-option v-for="o in LEVEL_OPTIONS" :key="String(o.value)" :value="o.value as number" :label="o.label" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="90">
          <template #default="{ row }">
            <el-tag :type="SOURCE_TAG[row.source] ?? 'info'" size="small" disable-transitions>{{ SOURCE_LABEL[row.source] ?? row.source }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <span class="status" :class="`status-${row.status}`">{{ STATUS_LABEL[row.status] ?? row.status }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="evidence_count" label="证据" width="70" align="center" />
        <el-table-column label="一致率" width="80" align="center">
          <template #default="{ row }">{{ row.evidence_count > 0 ? Math.round(row.agreement * 100) + '%' : '—' }}</template>
        </el-table-column>
        <el-table-column label="投票分布" min-width="140">
          <template #default="{ row }">
            <span class="votes">{{ votesText(row.level_votes) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text @click="toggleStatus(row)">{{ row.status === 'active' ? '停用' : '启用' }}</el-button>
            <el-button size="small" text type="danger" @click="removeRule(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <h3 class="section-title">编号体例</h3>
    <p class="hint">
      按编号模式（如「第X条」「N.N、」）覆盖内置判定，适配本组织书写习惯——例如把「第X条」当作三级标题、
      把顿号子项「N.N、」设为非标题。仅作用于本部署。
    </p>
    <el-card class="add-card">
      <div class="add-row">
        <el-select v-model="newPattern" class="add-name" filterable allow-create default-first-option placeholder="编号模式">
          <el-option v-for="p in PATTERN_OPTIONS" :key="p" :value="p" :label="p" />
        </el-select>
        <el-select v-model="newKind" class="add-level">
          <el-option v-for="o in KIND_OPTIONS" :key="o.value" :value="o.value" :label="o.label" />
        </el-select>
        <el-select v-model="newProfLevel" class="add-level" :disabled="newKind !== 'heading'">
          <el-option v-for="o in LEVEL_OPTIONS.slice(1)" :key="String(o.value)" :value="o.value as number" :label="o.label" />
        </el-select>
        <el-button type="primary" class="add-btn" @click="addProfile">新增体例</el-button>
      </div>
    </el-card>
    <el-card v-loading="loadingP">
      <el-table :data="profiles" class="profiles-table" empty-text="暂无编号体例">
        <el-table-column prop="pattern_key" label="编号模式" min-width="120" />
        <el-table-column label="判定" width="180">
          <template #default="{ row }">
            <el-select :model-value="row.kind" size="small" class="lvl-select" @change="(v: string) => changeProfile(row, { kind: v })">
              <el-option v-for="o in KIND_OPTIONS" :key="o.value" :value="o.value" :label="o.label" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="层级" width="150">
          <template #default="{ row }">
            <el-select
              :model-value="row.level"
              size="small"
              class="lvl-select"
              :disabled="row.kind === 'list'"
              @change="(v: number | null) => changeProfile(row, { level: v })"
            >
              <el-option v-for="o in LEVEL_OPTIONS.slice(1)" :key="String(o.value)" :value="o.value as number" :label="o.label" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="90">
          <template #default="{ row }">
            <el-tag :type="SOURCE_TAG[row.source] ?? 'info'" size="small" disable-transitions>{{ SOURCE_LABEL[row.source] ?? row.source }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <span class="status" :class="`status-${row.status}`">{{ STATUS_LABEL[row.status] ?? row.status }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text @click="toggleProfileStatus(row)">{{ row.status === 'active' ? '停用' : '启用' }}</el-button>
            <el-button size="small" text type="danger" @click="removeProfile(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.heading-rules-page { max-width: 980px; padding: 20px 24px; }
.page-title { font-size: 20px; font-weight: 600; margin: 0 0 8px; color: var(--text-primary, #303133); }
.section-title { font-size: 16px; font-weight: 600; margin: 28px 0 8px; color: var(--text-primary, #303133); }
.hint { font-size: 13px; color: var(--el-text-color-secondary); margin: 0 0 16px; line-height: 1.6; }
.add-card { margin-bottom: 16px; }
.add-row { display: flex; gap: 12px; }
.add-name { flex: 1 1 auto; }
.add-level { width: 160px; flex: none; }
.add-btn { flex: none; }
.lvl-select { width: 150px; }
.votes { color: var(--el-text-color-secondary); font-variant-numeric: tabular-nums; }
.status { font-size: 12px; padding: 1px 6px; border-radius: 3px; }
.status-active { color: #2c7a3f; background: #eef7f0; border: 1px solid #b7e0c2; }
.status-candidate { color: #b88230; background: #fdf6ec; border: 1px solid #f5dab1; }
.status-disabled { color: #909399; background: #f4f4f5; border: 1px solid #e0e0e2; }
</style>
