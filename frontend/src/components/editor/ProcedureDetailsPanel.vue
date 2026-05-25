<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'
import { listFields } from '@/api/fields'
import { collectDeprecatedFieldValues } from '@/utils/editor'
import { LEVEL_OF_USE_LABELS } from '@/utils/format'
import type { LevelOfUse } from '@/types/procedure'
import type { FieldDetailOut } from '@/types/field'

// 程序详情折叠面板（§1.2 / Q162）：元字段 + 自定义字段，折叠收纳。
const store = useProcedureEditorStore()
const p = computed(() => store.procedure)
const ro = computed(() => !store.editable)

// 已废弃字段（归档/删除后历史值不丢，只读展示，Q255/Q256）：拉归档字段定义贴标签，失败则回退 key。
const archivedFields = ref<FieldDetailOut[]>([])
onMounted(async () => {
  try {
    archivedFields.value = await listFields({ status: 'archived' })
  } catch {
    archivedFields.value = []
  }
})
const deprecatedEntries = computed(() =>
  collectDeprecatedFieldValues(
    p.value?.custom_values ?? {},
    store.fields.map((f) => f.key),
    archivedFields.value,
  ),
)

function setCustom(key: string, value: unknown): void {
  if (!p.value) return
  store.setMetaField('custom_values', { ...p.value.custom_values, [key]: value })
}
function customVal(key: string): unknown {
  const v = p.value?.custom_values?.[key]
  return v === undefined || v === null ? '' : v
}
function customValStr(key: string): string {
  const v = p.value?.custom_values?.[key]
  return v === undefined || v === null ? '' : String(v)
}
function customValArr(key: string): string[] {
  const v = p.value?.custom_values?.[key]
  if (Array.isArray(v)) return v as string[]
  return []
}
function fieldOpts(f: Pick<FieldDetailOut, 'options'>): Array<{ value: string; label: string }> {
  return f.options.map(o => ({ value: o.value, label: o.label }))
}
function customValLabels(key: string, opts: { value: string; label: string }[]): string {
  const vals = customValArr(key)
  return vals.map(v => opts.find(o => o.value === v)?.label ?? v).join(', ')
}
</script>

<template>
  <el-collapse v-if="p" class="details">
    <el-collapse-item title="程序详情 / 自定义字段" name="meta">
      <el-form label-width="110px" label-position="left">
        <el-form-item label="名称">
          <el-input :model-value="p.name" :disabled="ro" maxlength="200" @input="(v: string) => store.setMetaField('name', v)" />
        </el-form-item>
        <el-form-item label="用途级别">
          <el-select :model-value="p.level_of_use" :disabled="ro" @change="(v: LevelOfUse) => store.setMetaField('level_of_use', v)">
            <el-option v-for="(label, val) in LEVEL_OF_USE_LABELS" :key="val" :value="val" :label="label" />
          </el-select>
        </el-form-item>
        <div class="row2">
          <el-form-item label="风险等级">
            <el-input-number :model-value="p.risk_level" :min="1" :max="5" :disabled="ro" @change="(v: number | undefined) => store.setMetaField('risk_level', v ?? 1)" />
          </el-form-item>
          <el-form-item label="质量等级">
            <el-input-number :model-value="p.quality_level" :min="1" :max="5" :disabled="ro" @change="(v: number | undefined) => store.setMetaField('quality_level', v ?? 1)" />
          </el-form-item>
        </div>
        <el-form-item label="描述">
          <el-input :model-value="p.description" type="textarea" :rows="2" maxlength="10000" :disabled="ro" @input="(v: string) => store.setMetaField('description', v)" />
        </el-form-item>
        <el-form-item v-if="p.version > 1" label="版本更新说明">
          <el-input :model-value="p.version_update_notes" type="textarea" :rows="2" maxlength="10000" :disabled="ro" @input="(v: string) => store.setMetaField('version_update_notes', v)" />
        </el-form-item>

        <el-form-item label="PDF 签字栏">
          <el-switch
            :model-value="p.signoff_enabled"
            :disabled="ro"
            @change="(v: string | number | boolean) => store.setMetaField('signoff_enabled', !!v)"
          />
        </el-form-item>

        <template v-if="store.fields.length">
          <el-divider content-position="left">自定义字段</el-divider>
          <el-form-item v-for="f in store.fields" :key="f.id" :label="f.name" :required="f.required">
            <!-- read-only: plain text display -->
            <template v-if="ro">
              <span v-if="f.field_type === 'text' || f.field_type === 'textarea' || f.field_type === 'number' || f.field_type === 'date'" class="custom-readonly">{{ customValStr(f.key) }}</span>
              <span v-else-if="f.field_type === 'select'" class="custom-readonly">{{ fieldOpts(f).find(o => o.value === customValStr(f.key))?.label ?? customValStr(f.key) }}</span>
              <span v-else-if="f.field_type === 'multi_select' || f.field_type === 'checkbox'" class="custom-readonly">{{ customValLabels(f.key, fieldOpts(f)) }}</span>
              <span v-else class="custom-readonly">{{ customValStr(f.key) }}</span>
            </template>

            <!-- text -->
            <el-input
              v-else-if="f.field_type === 'text'"
              :model-value="customValStr(f.key)"
              type="text"
              @input="(v: string) => setCustom(f.key, v)"
            />

            <!-- textarea -->
            <el-input
              v-else-if="f.field_type === 'textarea'"
              :model-value="customValStr(f.key)"
              type="textarea"
              :rows="3"
              @input="(v: string) => setCustom(f.key, v)"
            />

            <!-- number -->
            <el-input-number
              v-else-if="f.field_type === 'number'"
              :model-value="customVal(f.key) === '' ? undefined : Number(customVal(f.key))"
              @change="(v: number | undefined) => setCustom(f.key, v)"
            />

            <!-- date -->
            <el-date-picker
              v-else-if="f.field_type === 'date'"
              :model-value="customValStr(f.key)"
              type="date"
              value-format="YYYY-MM-DD"
              @update:model-value="(v: string | null) => setCustom(f.key, v ?? '')"
            />

            <!-- select -->
            <el-select
              v-else-if="f.field_type === 'select'"
              :model-value="customValStr(f.key)"
              @update:model-value="(v: string) => setCustom(f.key, v)"
            >
              <el-option
                v-for="opt in fieldOpts(f)"
                :key="opt.value"
                :value="opt.value"
                :label="opt.label"
              />
            </el-select>

            <!-- multi_select -->
            <el-select
              v-else-if="f.field_type === 'multi_select'"
              :model-value="customValArr(f.key)"
              multiple
              @update:model-value="(v: string[]) => setCustom(f.key, v)"
            >
              <el-option
                v-for="opt in fieldOpts(f)"
                :key="opt.value"
                :value="opt.value"
                :label="opt.label"
              />
            </el-select>

            <!-- checkbox: single option → el-switch; multiple options → el-checkbox-group -->
            <template v-else-if="f.field_type === 'checkbox'">
              <el-switch
                v-if="fieldOpts(f).length <= 1"
                :model-value="Boolean(customVal(f.key))"
                @update:model-value="(v: boolean) => setCustom(f.key, v)"
              />
              <el-checkbox-group
                v-else
                :model-value="customValArr(f.key)"
                @update:model-value="(v: string[]) => setCustom(f.key, v)"
              >
                <el-checkbox
                  v-for="opt in fieldOpts(f)"
                  :key="opt.value"
                  :value="opt.value"
                  :label="opt.label"
                />
              </el-checkbox-group>
            </template>

            <!-- fallback: plain text input -->
            <el-input
              v-else
              :model-value="customValStr(f.key)"
              type="text"
              @input="(v: string) => setCustom(f.key, v)"
            />
          </el-form-item>
        </template>
      </el-form>
    </el-collapse-item>

    <el-collapse-item v-if="deprecatedEntries.length" name="deprecated">
      <template #title>
        <span class="deprecated-title">已废弃字段（{{ deprecatedEntries.length }}）</span>
      </template>
      <el-form label-width="110px" label-position="left">
        <el-form-item v-for="e in deprecatedEntries" :key="e.key" :label="e.label">
          <span class="custom-readonly">{{ e.value }}</span>
        </el-form-item>
      </el-form>
    </el-collapse-item>
  </el-collapse>
</template>

<style scoped>
.details {
  border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5);
}
.row2 {
  display: flex;
  gap: 16px;
}
.custom-readonly {
  color: var(--el-text-color-regular, #606266);
  word-break: break-word;
}
.deprecated-title {
  color: var(--el-text-color-secondary, #909399);
}
</style>
