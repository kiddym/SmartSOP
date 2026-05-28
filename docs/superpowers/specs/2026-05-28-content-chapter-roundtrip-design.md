# 内容 ↔ 章节双向桥接(promote auto-extract + demote editorial flatten)设计

**日期:** 2026-05-28
**状态:** 已确认(brainstorm 完成 / 待 writing-plans)
**作者:** 协作设计(cui_yuming + Claude)
**前序工作:**
- [`2026-05-27-layer-overlay-auto-nest-design.md`](2026-05-27-layer-overlay-auto-nest-design.md) — auto-nest 上线后,Phase A/C 成为本期改动的天然位置
- memory `parser-no-mutation-principle` — parser 是"忠实表达者",结构调整放在 UI 层

## 背景

层级标定模式跑通 auto-nest 后(2026-05-27),`_phase_a_to_chapter` 把 content 升章节、`_phase_c_to_content` 把章节降内容,两条路径各自工作但**桥接 plain-text title 与 rich-text body 的逻辑过于机械**:

- **promote 现状**:`chapter.title = st.title or "未命名章节"`。截图场景下若 content 的 `title=""`,新章节标题就是 `未命名章节` — 用户得手动改;但绝大多数 parser 漏标二级标题的场景里,内容 body 就是一句短文本("3.1 质量部是记录的归口管理部门"),完全可以拿来当章节标题。
- **demote 现状**:`_phase_c_to_content` 只接"光杆司令章节"(无任何子节点);前端 `effectiveRole` 又把"有 leaf 子的章节"选「正文」悄悄夹回 chapter — 用户根本无法 demote 一个 promote 出来的章节。两条路径不对称。

本期把这两条桥接做严:

- promote 满足精严 precondition(纯文本 + ≤50 码点)时,**抽取 body 当 title**,不再创建子 content step
- demote 在镜像形态(无子 或 1 个无标题 content 子)下,**把 chapter.title 拉平进 body 头部**,并合并子 body

## 目标

1. **降低 parser 漏识别二级标题场景的 UX 摩擦**:当前需要"促成 promote → 手动改标题 → 删自动生成的 '未命名章节' 残留" ≥3 步;新设计 1 步完成
2. **打通 demote 路径**:章节回退到内容能用,且行为可预测(editorial flatten,标题并入正文头部)
3. **保留"决策权归用户"**:promote 的 auto-extract 只在精严 precondition 下触发,不揣摩;非镜像形态的 demote 硬拒并提示用户如何重组
4. **事务原子性**:抽取 + lift-child 与 Phase A/C 走同一事务,失败回滚

## 非目标

- ❌ Round-trip 严格对称 — 仅 auto-extract 路径(无子章节)保留严格 round-trip;title+body 路径透明放弃(见 §1 不变量)
- ❌ 为 Word 导入的"章节 + N 个 content 子"扩展 demote(用户需手动重组为 0 子或 1 mirror 子后再 demote)
- ❌ Layer 模式行内 title 预览(本期只做 apply 后 toast,Q5 选了最轻方案)
- ❌ ContentDetailPanel 加"升章节"按钮(memory `word-parse-audit-2026-05-27` 的 🟡 项,继续延后)
- ❌ 单行 `convert_to_chapter` / `convert_to_content` API 不动(无 UI 调用方,保留以备将来)
- ❌ Parser / ParseResult 任何改动

## 范围

| 模块 | 摘要 | 改动面 |
|---|---|---|
| 后端 service | `_phase_a_to_chapter` 加 `_try_extract_title_from_body` 抽取;`_phase_c_to_content` 替换为"无子/1 mirror 子 → editorial flatten;其他 → NOT_MIRROR_SHAPE" | `layer_apply_service.py` 内联 ~50 行 |
| 后端 schema | `LayerApplyResult` 加 `extracted_titles` + `collapsed_chapters` 两个 map | `schemas/node.py` |
| 前端 store | apply 成功后读 `extracted_titles` / `collapsed_chapters`,组合 toast | `procedureEditor.ts:applyLayerRoles` |
| 前端 layerMark | `effectiveRole` 删除 `hasLeafChildren` 强夹回,让用户能给有 leaf 子的章节选「正文」(由后端校验) | `layerMark.ts:33-46` |
| 前端 placeholder | ContentDetailPanel title placeholder 改成"内容块标题(可选)",删掉旧版误导信息 | `ContentDetailPanel.vue` |
| 测试 | 新增/替换 15 个后端单测覆盖触发/不触发/round-trip 1 成立/round-trip 2 不成立 | `test_layer_apply_service.py` |

---

## §1 目标与不变量

### 1.1 用户故事

**Story A — promote**:用户在层级标定模式给一个 title 为空、body 是"3.1 质量部是记录的归口管理部门"的 content 选「二级」。期望:新二级章节标题就是"3.1 质量部是记录的归口管理部门",树里无残留 `未命名章节` 子节点。

**Story B — demote**:用户在层级标定模式给一个 chapter("3.1 崔宇明", child=content(body="<p>负责...</p>")) 选「正文」。期望:章节降为 1 个 content,body 是 `<p>3.1 崔宇明</p><p>负责...</p>`(标题并入 body 头部,子被合并)。

**Story C — refuse**:用户给一个有 3 个子 content 的章节选「正文」。期望:后端 400,banner 提示"请先手动重组为 0 个或 1 个无标题内容块"。

### 1.2 不变量

**严格成立(round-trip 1 — auto-extract 路径)**:
```
content(title="", body="<p>X</p>")  [X 满足: 纯文本 ≤50 码点]
  ─ promote ─→  chapter(title="X", 无子)
  ─ demote ──→  content(title="", body="<p>X</p>")    ✓ 回到起点
```

**透明放弃(round-trip 2 — title+body 路径)**:
```
content(title="Y", body=B)
  ─ promote ─→  chapter(title="Y", child=content(body=B))
  ─ demote ──→  content(title="", body="<p>Y</p>" + B)   ✗ title 进了 body 头部
```

放弃原因:demote 的真实意图是"拉平这一级",而不是"分离标题与正文"。editorial flatten 更贴合用户直觉。spec 显式记录此非对称,**测试里加负例 `test_roundtrip_2_explicitly_breaks` 防止未来误改回严格 round-trip**。

---

## §2 promote auto-extract

### 2.1 触发条件(全部满足)

1. `st.title.strip() == ""` — 无显式标题
2. `st.content` 经 lxml 解析后,**正好 1 个顶层元素**,且元素类型为 `<p>`
3. 该 `<p>` 的**所有子节点都是文本节点**(`text`/`tail`),无任何子元素;HTML 实体(`&amp; &lt;` 等)解码为对应字符不影响判定
4. `<p>` 的文本内容(`p.text_content()`)长度 ≤ 50 个 **Unicode 码点**(Python `len()`)

任一不满足 → 回落到现行 `_phase_a_to_chapter` 行为(`title = st.title or "未命名章节"`,body 非空时建子 content step)。

### 2.2 实现

新增模块级 helper:
```python
def _try_extract_title_from_body(body: str) -> str | None:
    """body 满足 §2.1 #2-#4 → 返回提取的纯文本;否则返回 None。"""
    if not body or not body.strip():
        return None
    try:
        from lxml import html as lxml_html
        frag = lxml_html.fragment_fromstring(body, create_parent="div")
    except Exception:
        return None
    children = list(frag)
    if len(children) != 1:
        return None
    p = children[0]
    if p.tag != "p":
        return None
    if list(p):  # <p> 含任何子元素 → 不算纯文本
        return None
    text = (p.text or "")
    if len(text) > 50:
        return None
    if not text.strip():
        return None
    return text
```

`_phase_a_to_chapter` 改造(只列改动段,其他不变):
```python
extracted = None
if not (st.title and st.title.strip()):
    extracted = _try_extract_title_from_body(st.content or "")

new_ch = ProcedureChapter(
    procedure_id=proc.id,
    parent_id=resolved_parent,
    title=extracted or st.title or "未命名章节",
    sort_order=u["sort_order"],
    level=u["level"],
)
db.add(new_ch)
db.flush()

if extracted is not None:
    # auto-extract 命中:body 已搬到 title,不创建子 content step
    extracted_titles_out[row.id] = extracted
elif st.content and st.content.strip():
    # 回落:body 进子 content step(现行逻辑)
    child = ProcedureStep(... content=st.content ...)
    ...
```

`extracted_titles_out: dict[old_step_id, extracted_title]` 由 `_phase_a_to_chapter` 累积返回,顶层 `apply_layer_roles` 注入到 `LayerApplyResult`。

### 2.3 边界

- `body = ""` → `_try_extract_title_from_body` 返回 `None` → 回落,新章节 `title = st.title or "未命名章节"`(`st.title` 已为空 → "未命名章节"),无子(因为 body 为空原本也不建子)
- `body = "<p>x</p><p>y</p>"` → 多块 → 不抽 → 回落
- `body = "<p>x<b>y</b></p>"` → `<p>` 含子 `<b>` → 不抽 → 回落
- `body = "<p>" + "你" * 51 + "</p>"` → 51 码点 > 50 → 不抽 → 回落
- `body = "<p>3.1 &amp; 4.0</p>"` → 解析后 `p.text = "3.1 & 4.0"`,9 码点 → 抽取成功,新 title = `"3.1 & 4.0"`
- `body = "<p>  </p>"` → text 全空白 → 不抽(`text.strip()` 为空)→ 回落

---

## §3 demote editorial flatten

### 3.1 形态判定与分支

`_phase_c_to_content` 替换为:

```python
# 形态判定 — 子章节已被 _validate_chapter_children_for_content 拦下(CHAPTER_HAS_CHILDREN)
# 这里只处理叶子子节点
leaf_children = _leaf_children(db, proc.id, ch.id)  # 按 sort_order 排序
n = len(leaf_children)

if n > 1:
    raise bad_request("NOT_MIRROR_SHAPE",
                      f"章节 {ch.title or ch.id} 有 {n} 个叶子子节点,请先手动合并为 0 个或 1 个无标题内容块")

if n == 1:
    child = leaf_children[0]
    if child.kind != "content" or (child.title or "").strip() != "":
        raise bad_request("NOT_MIRROR_SHAPE",
                          f"章节 {ch.title or ch.id} 的叶子子节点 {child.id} 不是无标题内容块,请先手动重组")

# editorial flatten:title 包 <p> 进 body 头部,空 title 不前缀
title_html = f"<p>{_html.escape(ch.title)}</p>" if (ch.title or "").strip() else ""

if n == 0:
    body = title_html
else:
    body = title_html + (child.content or "")
    child.is_active = False
    child.deleted_at = utcnow()
    collapsed_chapters_out[ch.id] = child.id

new_step = ProcedureStep(
    procedure_id=proc.id,
    chapter_id=chapter_map.get(u["parent_id"], u["parent_id"]),
    kind="content",
    title="",
    content=body,
    input_schema={},
    sort_order=u["sort_order"],
)
db.add(new_step)
db.flush()
ch.is_active = False
ch.deleted_at = utcnow()
```

新增 helper:
```python
def _leaf_children(db: Session, proc_id: str, chapter_id: str) -> list[ProcedureStep]:
    return list(
        db.execute(
            select(ProcedureStep)
            .where(
                ProcedureStep.procedure_id == proc_id,
                ProcedureStep.chapter_id == chapter_id,
                ProcedureStep.is_active.is_(True),
            )
            .order_by(ProcedureStep.sort_order, ProcedureStep.id)
        ).scalars()
    )
```

### 3.2 预校验同步升级

`_validate_chapter_children_for_content` 不只检"有子章节",还要检镜像形态;让用户在 Apply 前看到合理错误,Phase C 内部仍保留 backstop:

```python
def _validate_chapter_children_for_content(
    db: Session, proc_id: str, updates: dict[str, dict]
) -> None:
    for node_id, u in updates.items():
        if u["kind"] != "to-content":
            continue
        ch = db.get(ProcedureChapter, node_id)
        if ch is None or not ch.is_active:
            continue
        if _has_chapter_children(db, proc_id, ch.id):
            raise bad_request("CHAPTER_HAS_CHILDREN", ...)
        leaves = _leaf_children(db, proc_id, ch.id)
        if len(leaves) > 1:
            raise bad_request("NOT_MIRROR_SHAPE", ...)
        if len(leaves) == 1 and (leaves[0].kind != "content" or (leaves[0].title or "").strip() != ""):
            raise bad_request("NOT_MIRROR_SHAPE", ...)
```

### 3.3 边界

- `ch.title = ""`, 0 子 → body = `""`,新 content body 空
- `ch.title = "Y"`, 0 子 → body = `"<p>Y</p>"`,**与现行行为一致**(无回归)
- `ch.title = "Y"`, 1 mirror 子(body=`"<p>B</p>"`)→ body = `"<p>Y</p><p>B</p>"`,子软删
- `ch.title = ""`, 1 mirror 子(body=`"<p>B</p>"`)→ body = `"<p>B</p>"`(不前缀空 `<p></p>`)
- `ch.title = 80 字 long title`, 1 mirror 子 → body = `"<p>80 字</p><p>B</p>"`,**无长度门槛**
- `ch.title = "<script>"`,任何形态 → body 里出现 `<p>&lt;script&gt;</p>`(`_html.escape` 兜底)

---

## §4 前端调整

### 4.1 `effectiveRole` 放宽

`frontend/src/utils/layerMark.ts:33-46`:

```diff
   if (row.kind === 'chapter') {
-    // 章节：content 角色受 hasLeafChildren 约束
-    if (role === 'content' && row.hasLeafChildren) return defaultLayerRole(row)
     // 章节不可选 'keep'，夹回默认
     if (role === 'keep') return defaultLayerRole(row)
     return role
   }
```

`hasLeafChildren` 字段保留(可能其他地方用到,本期不动);仅去掉这条强夹回。这样用户可以给任何章节选「正文」,镜像 / 非镜像由后端判定 + 错误 banner 提示。

### 4.2 Toast 显示

apply 成功路径需把 `extracted_titles` + `collapsed_chapters` 透出给 UI 层显示 toast。两种放法都可接受,实施者选简单的那个:

- **方案 a**(放 store action):store.applyLayerRoles 返回值扩展为 `{ok: true, extracted: number, collapsed: number}`,调用方(`ChapterTreePanel`)看到非零就调 `ElMessage.success`
- **方案 b**(放 view 层):store action 返回 `result` 原样,`ChapterTreePanel` 在 then 里解析两个 map 并显示

文案规则:
```
extracted > 0           → "已为 N 个无标题章节自动提取标题"
collapsed > 0           → "已合并 M 个章节为内容块"
两者都 > 0              → 上两句 "；" 拼接
两者都 == 0             → 不弹 toast
```

`ElMessage` 已在编辑器多处使用,无新依赖。

### 4.3 类型与 placeholder

`frontend/src/types/node.ts`:
```diff
 export interface LayerApplyResult {
   chapter_map: Record<string, string>
   revision: number
+  extracted_titles?: Record<string, string>
+  collapsed_chapters?: Record<string, string>
 }
```

`frontend/src/components/editor/ContentDetailPanel.vue`(title input placeholder):
```diff
- placeholder="内容块标题（可选——填了之后才能在层级标定里升为章节）"
+ placeholder="内容块标题（可选）"
```

旧 placeholder 本来就不准(空 title 一直可升,只是回落 "未命名章节"),顺手清理。

### 4.4 不动的部分

- `validateLayerQ25` 不动 — 它只管同级互斥,与镜像形态无关
- `LayerRow` 类型不动 — 后端唯一权威,前端不需要知道子形态(Q6 决策)
- `computeLayerUpdates` / `computeLayerIndents` 不动

---

## §5 测试

### 5.1 后端(append 到 `backend/tests/unit/services/test_layer_apply_service.py`)

**promote auto-extract**:

1. `test_promote_auto_extract_pure_text_short` — title="", body=`<p>3.1 质量部</p>` → chapter.title="3.1 质量部",无子,`extracted_titles[s.id]="3.1 质量部"`
2. `test_promote_no_extract_body_too_long` — body 是 51 个中文字 → 回落,chapter.title="未命名章节",有子 content
3. `test_promote_no_extract_body_has_bold` — body=`<p><b>x</b></p>` → 回落
4. `test_promote_no_extract_body_multi_block` — body=`<p>x</p><p>y</p>` → 回落
5. `test_promote_no_extract_body_with_br` — body=`<p>x<br>y</p>` → 回落(`<br>` 是子元素)
6. `test_promote_no_extract_title_already_set` — title="X",body 纯短文本 → 不抽取,用 title="X"
7. `test_promote_extracts_with_html_entity` — body=`<p>3.1 &amp; 4.0</p>` → chapter.title=`"3.1 & 4.0"`
8. `test_promote_no_extract_empty_p` — body=`<p>  </p>` → 回落

**demote editorial flatten**:

9. `test_demote_no_children_existing_behavior` — chapter("A",无子) → content(title="", body="<p>A</p>") + `collapsed_chapters` 不包含 ch(无子合并)
10. `test_demote_one_child_content_flattens` — chapter("Y", child(body="<p>B</p>")) → content(title="", body="<p>Y</p><p>B</p>"),child 软删,`collapsed_chapters[ch.id]=child.id`
11. `test_demote_long_title_flattens_no_length_gate` — chapter("80 字 title", child(body=B)) → flatten,body 含 80 字 `<p>` 前缀
12. `test_demote_empty_title_one_child_omits_p_prefix` — chapter("", child(body="<p>B</p>")) → content(body="<p>B</p>") 不前缀空 `<p></p>`
13. `test_demote_one_child_content_has_title_refuses` — 子有 title → `NOT_MIRROR_SHAPE`
14. `test_demote_one_child_step_refuses` — 子是 step → `NOT_MIRROR_SHAPE`
15. `test_demote_two_content_children_refuses` — 两子 → `NOT_MIRROR_SHAPE`
16. `test_demote_chapter_has_chapter_children_refuses` — 沿用 `CHAPTER_HAS_CHILDREN`

**round-trip 1 严格 / round-trip 2 不严格**:

17. `test_roundtrip_1_auto_extract_path` — content(title="", body="<p>3.1 X</p>") → promote → demote → 等于起点
18. `test_roundtrip_2_explicitly_breaks` — content(title="Y", body="<p>B</p>") → promote → demote → content(title="", body="<p>Y</p><p>B</p>");**断言** 与起点 NOT 相等(防止未来误改回严格 round-trip)

**混合 batch**:

19. `test_mixed_batch_extract_and_flatten_same_apply` — 同一次 apply 内既触发 auto-extract 又触发 lift-child,`LayerApplyResult` 两个 map 都非空

### 5.2 前端

- `frontend/tests/unit/utils/layerMark.spec.ts`:`effectiveRole` 测试更新 — 章节有 leaf 子时选 'content' 不再被夹回(返回 'content',而非 default chapter 角色)
- `frontend/tests/unit/store/procedureEditor.applyLayerRoles.spec.ts`:新增测试 mock 返回带 `extracted_titles + collapsed_chapters` 的 result,验证 `ElMessage.success` 被调用且内容拼接正确

---

## §6 风险与缓解

| 风险 | 缓解 |
|---|---|
| FE 放宽 effectiveRole 后,用户对"为什么这次 demote 拒绝"的预期变差 | 后端错误体附 `chapter_id` + `child_count` + `bad_children_ids`,banner 描述清楚怎么修才能 demote |
| 50 码点偶尔卡到合理短句 | spec 写明 50 是经验值,日后可考虑配置化,本期不做 |
| `<p>` 解析失败(异常 HTML)| `_try_extract_title_from_body` 全程 try/except,任何解析异常返回 `None` → 回落,不抛错 |
| Round-trip 2 不严格被未来人误改回严格 | `test_roundtrip_2_explicitly_breaks` 显式断言不等,改回就挂 |
| 长 title flatten 后无法再 auto-extract 回章节 | 这是预期(title 越长越不应该是章节),用户能感知到 |

## §7 验收标准

1. 截图场景(parser 漏识别的"3.1 质量部..."类 content 升 L2):升完得到标题就是这句话的章节,无子节点,无残留 `未命名章节`。
2. demote 一个 chapter(title="3.1 崔宇明", child(body="<p>负责...</p>")):得到 content(body="<p>3.1 崔宇明</p><p>负责...</p>")。
3. demote 一个 multi-leaf chapter:后端 400 `NOT_MIRROR_SHAPE`,banner 显示提示。
4. apply 成功后 toast 显示触发计数。
5. 所有前后端单测通过;`test_roundtrip_2_explicitly_breaks` 通过。

## §8 实施顺序建议(供 writing-plans 参考)

1. 后端:`_try_extract_title_from_body` helper + 单测(promote 8 个 case)
2. 后端:`_phase_a_to_chapter` 注入抽取 + `LayerApplyResult` 加 `extracted_titles`
3. 后端:`_leaf_children` helper + `_phase_c_to_content` 重写 + `_validate_chapter_children_for_content` 升级 + 单测(demote 7 个 case)
4. 后端:round-trip 与 mixed batch 测试
5. 前端:`effectiveRole` 放宽 + layerMark.spec 更新
6. 前端:`LayerApplyResult` 类型扩展 + applyLayerRoles toast + store spec 更新
7. 前端:ContentDetailPanel placeholder
8. 手动 dev 验证 + memory(本期可顺便清理 `pdf-content-no-title`、记一条 round-trip 2 非对称的设计决定)
