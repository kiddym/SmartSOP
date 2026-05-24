# 步骤表单字段预览 + 补齐缺失类型配置 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增表单字段级只读预览组件并补齐缺失类型配置，使编辑器在配置 `input_schema` 时所见即所得，对标 DPMS `StepInputDisplay`。

**Architecture:** 纯前端。新建单文件分发组件 `FormFieldPreview.vue`（按 `schema.type` v-if 渲染 12 型只读控件），复用到执行记录区 + 3 警示区；增强 `StepFormFields.vue` 补 YESNO/SIGNATURE/DATE/PHOTO 配置与 METER 阈值；`StepDetailPanel.vue` 改「配置左/预览右」并排布局。后端 `_validate_input_schema` 仅校验 `type` 枚举、`input_schema` 为自由 JSON，故新配置键无需任何后端改动。

**Tech Stack:** Vue 3 `<script setup>` + TypeScript + Element Plus 2.7；测试 Vitest + @vue/test-utils（jsdom），测试位于 `frontend/tests/unit/*.spec.ts`。

**关联 spec：** `docs/superpowers/specs/2026-05-24-step-field-preview-design.md`

**Git 约定：** 当前分支 `feature/preimport-block-marking` 存在大量与本功能无关的未提交改动。**每次提交只 `git add` 本任务明确列出的文件，禁止 `git add -A` / `git add .`**，以免误纳入他人 WIP。所有命令在 `frontend/` 目录下执行。

---

### Task 1: FormFieldPreview.vue — 12 型只读预览组件

**Files:**
- Create: `frontend/src/components/editor/FormFieldPreview.vue`
- Test: `frontend/tests/unit/FormFieldPreview.spec.ts`

- [ ] **Step 1: 写失败测试**

Create `frontend/tests/unit/FormFieldPreview.spec.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import FormFieldPreview from '@/components/editor/FormFieldPreview.vue'
import type { InputSchema } from '@/types/node'

function mountPreview(schema: InputSchema) {
  return mount(FormFieldPreview, {
    props: { schema },
    global: { plugins: [ElementPlus] },
  })
}

describe('FormFieldPreview', () => {
  it('NUMBER 显示单位与范围、小数位', () => {
    const w = mountPreview({ type: 'NUMBER', unit: '℃', min: 0, max: 100, decimals: 1 })
    expect(w.text()).toContain('℃')
    expect(w.text()).toContain('范围 0 ~ 100')
    expect(w.text()).toContain('1 位小数')
  })

  it('METER 显示名称与下限上限', () => {
    const w = mountPreview({ type: 'METER', name: '压力', unit: 'MPa', lower_limit: 1, upper_limit: 9 })
    expect(w.text()).toContain('压力')
    expect(w.text()).toContain('下限 1 / 上限 9')
  })

  it('METER 缺省名称回退为「仪表读数」', () => {
    const w = mountPreview({ type: 'METER' })
    expect(w.text()).toContain('仪表读数')
  })

  it('CHECK 默认渲染通过/不通过两按钮', () => {
    const w = mountPreview({ type: 'CHECK' })
    expect(w.text()).toContain('通过')
    expect(w.text()).toContain('不通过')
  })

  it('CHECK 自定义标签生效', () => {
    const w = mountPreview({ type: 'CHECK', pass_label: '合格', fail_label: '不合格' })
    expect(w.text()).toContain('合格')
    expect(w.text()).toContain('不合格')
  })

  it('YESNO 默认是/否，无不适用', () => {
    const w = mountPreview({ type: 'YESNO' })
    expect(w.text()).toContain('是')
    expect(w.text()).toContain('否')
    expect(w.text()).not.toContain('不适用')
  })

  it('YESNO na_enabled 时显示不适用', () => {
    const w = mountPreview({ type: 'YESNO', na_enabled: true })
    expect(w.text()).toContain('不适用')
  })

  it('CHECKBOX 按 options 渲染对应数量复选框', () => {
    const w = mountPreview({ type: 'CHECKBOX', options: ['甲', '乙', '丙'] })
    expect(w.findAll('.el-checkbox').length).toBe(3)
    expect(w.text()).toContain('甲')
  })

  it('CHECKBOX 无选项显示未配置提示', () => {
    const w = mountPreview({ type: 'CHECKBOX' })
    expect(w.text()).toContain('未配置选项')
  })

  it('RADIO 按 options 渲染对应数量单选', () => {
    const w = mountPreview({ type: 'RADIO', options: ['A', 'B'] })
    expect(w.findAll('.el-radio').length).toBe(2)
  })

  it('UPLOAD 显示占位与 accept/max_count', () => {
    const w = mountPreview({ type: 'UPLOAD', accept: 'image/*', max_count: 3 })
    expect(w.text()).toContain('添加文件')
    expect(w.text()).toContain('image/*')
    expect(w.text()).toContain('3')
  })

  it('PHOTO 显示最多张数', () => {
    const w = mountPreview({ type: 'PHOTO', max_count: 5 })
    expect(w.text()).toContain('添加照片')
    expect(w.text()).toContain('5 张')
  })

  it('SIGNATURE 显示占位与提示', () => {
    const w = mountPreview({ type: 'SIGNATURE', hint: '请操作人签名' })
    expect(w.text()).toContain('添加签名')
    expect(w.text()).toContain('请操作人签名')
  })

  it('DATE 无时间时占位为选择日期', () => {
    const w = mountPreview({ type: 'DATE' })
    expect(w.find('input').attributes('placeholder')).toBe('选择日期')
  })

  it('DATE with_time 时占位为选择日期时间', () => {
    const w = mountPreview({ type: 'DATE', with_time: true })
    expect(w.find('input').attributes('placeholder')).toBe('选择日期时间')
  })

  it('COMMON 显示操作说明提示', () => {
    const w = mountPreview({ type: 'COMMON' })
    expect(w.text()).toContain('通用操作说明型')
  })

  it('NONE 显示无需填写提示', () => {
    const w = mountPreview({ type: 'NONE' })
    expect(w.text()).toContain('无需填写')
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npm run test -- FormFieldPreview`
Expected: FAIL（找不到模块 `@/components/editor/FormFieldPreview.vue`）

- [ ] **Step 3: 写最小实现**

Create `frontend/src/components/editor/FormFieldPreview.vue`:

```vue
<script setup lang="ts">
import { computed } from 'vue'
import type { InputSchema } from '@/types/node'

// 表单字段执行态只读预览（对标 DPMS StepInputDisplay）。按 schema.type 分发，纯展示无 emit。
const props = defineProps<{ schema: InputSchema }>()

const type = computed(() => props.schema.type)

function str(key: string, fallback = ''): string {
  const v = props.schema[key]
  return typeof v === 'string' && v !== '' ? v : fallback
}
function num(key: string): number | undefined {
  const v = props.schema[key]
  return typeof v === 'number' ? v : undefined
}
function bool(key: string): boolean {
  return props.schema[key] === true
}
const options = computed<string[]>(() => {
  const v = props.schema.options
  return Array.isArray(v) ? v.map((x) => String(x)) : []
})

const numberRange = computed(() => {
  const min = num('min')
  const max = num('max')
  const decimals = num('decimals')
  const parts: string[] = []
  if (min !== undefined || max !== undefined) parts.push(`范围 ${min ?? '-'} ~ ${max ?? '-'}`)
  if (decimals !== undefined) parts.push(`${decimals} 位小数`)
  return parts.join('，')
})
const meterRange = computed(() => {
  const lo = num('lower_limit')
  const hi = num('upper_limit')
  if (lo === undefined && hi === undefined) return ''
  return `下限 ${lo ?? '-'} / 上限 ${hi ?? '-'}`
})
</script>

<template>
  <div class="field-preview">
    <div class="fp-header">预览</div>
    <div class="fp-body">
      <div v-if="type === 'NUMBER'" class="fp-number">
        <el-input class="fp-input" disabled placeholder="数值">
          <template v-if="str('unit')" #append>{{ str('unit') }}</template>
        </el-input>
        <div v-if="numberRange" class="fp-hint">{{ numberRange }}</div>
      </div>

      <div v-else-if="type === 'METER'" class="fp-meter">
        <div class="fp-meter-name">{{ str('name', '仪表读数') }}</div>
        <el-input class="fp-input" disabled placeholder="读数">
          <template v-if="str('unit')" #append>{{ str('unit') }}</template>
        </el-input>
        <div v-if="meterRange" class="fp-hint fp-meter-range">{{ meterRange }}</div>
      </div>

      <div v-else-if="type === 'CHECK'" class="fp-buttons">
        <el-button disabled>{{ str('pass_label', '通过') }}</el-button>
        <el-button disabled>{{ str('fail_label', '不通过') }}</el-button>
      </div>

      <div v-else-if="type === 'YESNO'" class="fp-buttons">
        <el-button disabled>{{ str('yes_label', '是') }}</el-button>
        <el-button disabled>{{ str('no_label', '否') }}</el-button>
        <el-button v-if="bool('na_enabled')" disabled>不适用</el-button>
      </div>

      <div v-else-if="type === 'CHECKBOX'" class="fp-options">
        <template v-if="options.length">
          <el-checkbox v-for="(opt, i) in options" :key="i" disabled>{{ opt }}</el-checkbox>
        </template>
        <div v-else class="fp-hint">未配置选项</div>
      </div>

      <div v-else-if="type === 'RADIO'" class="fp-options">
        <template v-if="options.length">
          <el-radio v-for="(opt, i) in options" :key="i" :label="opt" disabled>{{ opt }}</el-radio>
        </template>
        <div v-else class="fp-hint">未配置选项</div>
      </div>

      <div v-else-if="type === 'UPLOAD'" class="fp-placeholder">
        <div class="fp-ph-box">+ 添加文件</div>
        <div class="fp-hint">接受 {{ str('accept', '*') }} · 最多 {{ num('max_count') ?? '不限' }}</div>
      </div>

      <div v-else-if="type === 'PHOTO'" class="fp-placeholder">
        <div class="fp-ph-box">+ 添加照片</div>
        <div class="fp-hint">最多 {{ num('max_count') ?? 1 }} 张</div>
      </div>

      <div v-else-if="type === 'SIGNATURE'" class="fp-placeholder">
        <div class="fp-ph-box">+ 添加签名</div>
        <div v-if="str('hint')" class="fp-hint">{{ str('hint') }}</div>
      </div>

      <div v-else-if="type === 'DATE'" class="fp-date">
        <el-input class="fp-input" disabled :placeholder="bool('with_time') ? '选择日期时间' : '选择日期'" />
      </div>

      <div v-else-if="type === 'COMMON'" class="fp-hint">通用操作说明型，执行时无独立录入控件。</div>

      <div v-else class="fp-hint">该步骤无需填写录入项。</div>
    </div>
  </div>
</template>

<style scoped>
.field-preview {
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 4px;
  overflow: hidden;
}
.fp-header {
  padding: 6px 10px;
  background: var(--el-fill-color-light, #f5f7fa);
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
}
.fp-body {
  padding: 10px;
}
.fp-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
  margin-top: 6px;
}
.fp-input {
  max-width: 240px;
}
.fp-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.fp-options {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.fp-meter-name {
  font-size: 13px;
  margin-bottom: 4px;
}
.fp-meter-range {
  color: var(--el-color-warning, #e6a23c);
}
.fp-ph-box {
  border: 1px dashed var(--el-border-color, #dcdfe6);
  border-radius: 4px;
  padding: 16px;
  text-align: center;
  color: var(--el-text-color-secondary, #909399);
  font-size: 13px;
}
</style>
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npm run test -- FormFieldPreview`
Expected: PASS（18 个用例全绿）

- [ ] **Step 5: 提交**

```bash
git add src/components/editor/FormFieldPreview.vue tests/unit/FormFieldPreview.spec.ts
git commit -m "feat(editor): add FormFieldPreview component for 12 form types

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: 增强 StepFormFields.vue — 补齐缺失类型配置

**Files:**
- Modify: `frontend/src/components/editor/StepFormFields.vue`
- Test: `frontend/tests/unit/StepFormFields.spec.ts`

- [ ] **Step 1: 写失败测试**

Create `frontend/tests/unit/StepFormFields.spec.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import StepFormFields from '@/components/editor/StepFormFields.vue'
import type { InputSchema } from '@/types/node'

function mountFields(schema: InputSchema) {
  return mount(StepFormFields, {
    props: { schema },
    global: { plugins: [ElementPlus] },
  })
}

describe('StepFormFields 新增配置分支', () => {
  it('YESNO 显示是/否标签与不适用开关', () => {
    const w = mountFields({ type: 'YESNO' })
    expect(w.text()).toContain('是 标签')
    expect(w.text()).toContain('否 标签')
    expect(w.text()).toContain('包含')
  })

  it('YESNO 编辑是标签派发 update:schema', async () => {
    const w = mountFields({ type: 'YESNO' })
    await w.findAll('input')[0].setValue('Y')
    const events = w.emitted('update:schema')
    expect(events).toBeTruthy()
    expect((events!.at(-1)![0] as InputSchema).yes_label).toBe('Y')
  })

  it('METER 显示名称/下限/上限/小数位', () => {
    const w = mountFields({ type: 'METER' })
    expect(w.text()).toContain('仪表名称')
    expect(w.text()).toContain('下限')
    expect(w.text()).toContain('上限')
    expect(w.text()).toContain('小数位')
  })

  it('SIGNATURE 显示签名提示输入', () => {
    const w = mountFields({ type: 'SIGNATURE' })
    expect(w.text()).toContain('签名提示')
  })

  it('DATE 显示包含时间开关', () => {
    const w = mountFields({ type: 'DATE' })
    expect(w.text()).toContain('包含时间')
  })

  it('PHOTO 显示最大张数', () => {
    const w = mountFields({ type: 'PHOTO' })
    expect(w.text()).toContain('最大张数')
  })

  it('COMMON 仍显示无需配置兜底', () => {
    const w = mountFields({ type: 'COMMON' })
    expect(w.text()).toContain('无需额外配置')
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npm run test -- StepFormFields`
Expected: FAIL（YESNO/METER 新文案断言失败——当前 YESNO 落到兜底、METER 仅有单位）

- [ ] **Step 3: 实现配置分支**

In `frontend/src/components/editor/StepFormFields.vue`, add a `bool` helper after the existing `num` function (around line 21):

```ts
function bool(key: string): boolean {
  return props.schema[key] === true
}
```

Replace the existing METER block (lines 70-74) with:

```vue
    <template v-else-if="type === 'METER'">
      <el-form-item label="仪表名称">
        <el-input :model-value="str('name')" :disabled="readonly" @input="(v: string) => set('name', v)" />
      </el-form-item>
      <el-form-item label="单位">
        <el-input :model-value="str('unit')" :disabled="readonly" @input="(v: string) => set('unit', v)" />
      </el-form-item>
      <div class="num-row">
        <el-form-item label="下限">
          <el-input-number :model-value="num('lower_limit')" :disabled="readonly" controls-position="right" @change="(v: number | undefined) => set('lower_limit', v)" />
        </el-form-item>
        <el-form-item label="上限">
          <el-input-number :model-value="num('upper_limit')" :disabled="readonly" controls-position="right" @change="(v: number | undefined) => set('upper_limit', v)" />
        </el-form-item>
        <el-form-item label="小数位">
          <el-input-number :model-value="num('decimals')" :min="0" :max="6" :disabled="readonly" controls-position="right" @change="(v: number | undefined) => set('decimals', v)" />
        </el-form-item>
      </div>
    </template>
```

Then add the following four blocks immediately before the final `<el-text v-else ...>` line (line 97):

```vue
    <template v-else-if="type === 'YESNO'">
      <el-form-item label="是 标签">
        <el-input :model-value="str('yes_label')" :disabled="readonly" placeholder="是" @input="(v: string) => set('yes_label', v)" />
      </el-form-item>
      <el-form-item label="否 标签">
        <el-input :model-value="str('no_label')" :disabled="readonly" placeholder="否" @input="(v: string) => set('no_label', v)" />
      </el-form-item>
      <el-form-item label="包含『不适用』">
        <el-switch :model-value="bool('na_enabled')" :disabled="readonly" @change="(v: string | number | boolean) => set('na_enabled', !!v)" />
      </el-form-item>
    </template>

    <template v-else-if="type === 'SIGNATURE'">
      <el-form-item label="签名提示">
        <el-input :model-value="str('hint')" :disabled="readonly" placeholder="如：操作人签名" @input="(v: string) => set('hint', v)" />
      </el-form-item>
    </template>

    <template v-else-if="type === 'DATE'">
      <el-form-item label="包含时间">
        <el-switch :model-value="bool('with_time')" :disabled="readonly" @change="(v: string | number | boolean) => set('with_time', !!v)" />
      </el-form-item>
    </template>

    <template v-else-if="type === 'PHOTO'">
      <el-form-item label="最大张数">
        <el-input-number :model-value="num('max_count')" :min="1" :disabled="readonly" controls-position="right" @change="(v: number | undefined) => set('max_count', v)" />
      </el-form-item>
    </template>
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npm run test -- StepFormFields`
Expected: PASS（7 个用例全绿）

- [ ] **Step 5: 提交**

```bash
git add src/components/editor/StepFormFields.vue tests/unit/StepFormFields.spec.ts
git commit -m "feat(editor): add config UI for YESNO/SIGNATURE/DATE/PHOTO and METER thresholds

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: 集成预览到 StepDetailPanel.vue（执行记录 + 3 警示区）

**Files:**
- Modify: `frontend/src/components/editor/StepDetailPanel.vue`

集成层依赖 Pinia store 与 selectedStep，按 spec §4 不做组件单测；以 typecheck + build + lint + 现有测试无回归 + 运行态目视为验收。

- [ ] **Step 1: 引入组件**

In `frontend/src/components/editor/StepDetailPanel.vue`, add the import after the `StepFormFields` import (line 4):

```ts
import FormFieldPreview from './FormFieldPreview.vue'
```

- [ ] **Step 2: 执行记录区改并排布局**

Replace the exec collapse-item body (lines 160-167) with:

```vue
      <el-collapse-item title="执行记录" name="exec">
        <el-form label-position="top">
          <div class="config-preview">
            <div class="cp-config">
              <StepFormFields :schema="step.input_schema" :readonly="ro" @update:schema="onSchema" />
            </div>
            <div class="cp-preview">
              <FormFieldPreview :schema="step.input_schema" />
            </div>
          </div>
          <el-checkbox :model-value="step.require_confirmation" :disabled="ro" @change="(v: string | number | boolean) => upd({ require_confirmation: !!v })">
            需要操作员确认
          </el-checkbox>
        </el-form>
      </el-collapse-item>
```

- [ ] **Step 3: 三警示区非 COMMON 分支改并排布局**

Replace the note `<el-form v-else ...>` block (lines 102-104) with:

```vue
          <el-form v-else label-position="top">
            <div class="config-preview">
              <div class="cp-config">
                <StepFormFields :schema="step.note_schema" :readonly="ro" @update:schema="(s) => onAlertSchema('note', s)" />
              </div>
              <div class="cp-preview">
                <FormFieldPreview :schema="step.note_schema" />
              </div>
            </div>
          </el-form>
```

Replace the caution `<el-form v-else ...>` block (lines 120-122) with:

```vue
          <el-form v-else label-position="top">
            <div class="config-preview">
              <div class="cp-config">
                <StepFormFields :schema="step.caution_schema" :readonly="ro" @update:schema="(s) => onAlertSchema('caution', s)" />
              </div>
              <div class="cp-preview">
                <FormFieldPreview :schema="step.caution_schema" />
              </div>
            </div>
          </el-form>
```

Replace the warning `<el-form v-else ...>` block (lines 138-140) with:

```vue
          <el-form v-else label-position="top">
            <div class="config-preview">
              <div class="cp-config">
                <StepFormFields :schema="step.warning_schema" :readonly="ro" @update:schema="(s) => onAlertSchema('warning', s)" />
              </div>
              <div class="cp-preview">
                <FormFieldPreview :schema="step.warning_schema" />
              </div>
            </div>
          </el-form>
```

- [ ] **Step 4: 加布局 CSS**

In the `<style scoped>` block of `StepDetailPanel.vue`, add after the `.inline` rule:

```css
.config-preview {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.cp-config,
.cp-preview {
  flex: 1 1 280px;
  min-width: 0;
}
```

- [ ] **Step 5: typecheck + lint 验证**

Run: `npm run typecheck && npm run lint`
Expected: 均无错误（0 errors, 0 warnings）

- [ ] **Step 6: 提交**

```bash
git add src/components/editor/StepDetailPanel.vue
git commit -m "feat(editor): show side-by-side form field preview in step detail panel

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: 全量门禁验证

**Files:** 无（仅运行校验）

- [ ] **Step 1: 运行完整测试套件**

Run: `npm run test`
Expected: 全部通过，含新增的 FormFieldPreview / StepFormFields 用例，无既有用例回归。

- [ ] **Step 2: typecheck + lint + build**

Run: `npm run lint && npm run typecheck && npm run build`
Expected: lint 0 警告；typecheck 无错误；build 成功产出 dist。

- [ ] **Step 3: 运行态目视确认（手动）**

Run: `npm run dev`，打开一个程序进入编辑器，选中一个步骤：
- 执行记录区类型依次切到 NUMBER/METER/CHECK/YESNO/CHECKBOX/RADIO/UPLOAD/PHOTO/SIGNATURE/DATE/COMMON/NONE，右侧预览随之实时变化。
- 警示区（注意/小心/警告）切到非 COMMON 类型时同样出现配置+预览并排。
- 窄化右栏宽度时配置/预览自动上下堆叠。
Expected: 行为符合预期；无控制台报错。

- [ ] **Step 4: （如有 Step 3 修补）提交**

仅当目视发现并修复了问题时：

```bash
git add src/components/editor/<改动文件>
git commit -m "fix(editor): <具体修复>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## 验收对照（spec coverage）

- spec §3.1 FormFieldPreview 12 型 → Task 1 ✓
- spec §3.2 StepFormFields 补 YESNO/SIGNATURE/DATE/PHOTO + METER 阈值 → Task 2 ✓
- spec §3.3 StepDetailPanel 4 处并排集成 + 响应式堆叠 → Task 3 ✓
- spec §4 测试（FormFieldPreview + StepFormFields 单测） → Task 1/2 ✓
- spec §5 验收（lint/typecheck/build/vitest + 实时切换 + 只读态） → Task 4 ✓
- spec §6 后端校验风险 → 已核查 `step_service._validate_input_schema` 仅校验 type 枚举，风险解除，无需任务
