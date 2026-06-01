# C 项设计：EMF/WMF 无 LibreOffice 阻断告警 + 软依赖探测

> 状态：设计已与用户确认（2026-06-01）。
> 来源需求：`docs/word-parser-solution.md` §12.2C。
> 复用 A 项 `ParseWarning.severity` + `ParseConfirmDialog` 强确认、B 项 `.sop-ph` 占位 + content review 放行（import_service）。
> 本 spec 仅覆盖 C 项；A/B 已完成、D 已对齐。

---

## 1. 背景与现状核对（含一处文档漂移）

EMF/WMF 矢量图（Visio/旧 Office 流程图）需 `soffice` headless 转 PNG。`images.convert_to_png`（`utils/images.py:57-78`）在 soffice 缺失/转换失败时返 None。

**文档漂移（2026-06-01 发现并报告）**：`word-parser-solution.md` §12.2C 称当前行为是「返回 None → **降级占位符 + review**，不阻断」。但实际代码（`upload_service.write_temp_media:104-110`）转换失败时**既不加占位符、也不标 review**——原样保留 EMF/WMF 字节、`<img src>` 指向无法在浏览器渲染的 EMF；导入时 `asset_service.promote_temp` 对 EMF 仍 `_prepare` 失败返 None，`import_service._promote_temp_urls` 保留**会过期的临时 URL**。故现状是「静默留一张坏图（且导入后过期）」，比文档描述更糟。本 spec 把现状补成文档设想的「占位符 + review」并加阻断告警。

**已核实事实**：
- `images.soffice_available()`（`images.py:53`）已存在，但**仅测试用**，主流程未调用。
- `write_temp_media`（`upload_service.py`）是唯一做 EMF/WMF 转换的解析期入口；**仅被 `parse_service.parse:70` 调用**（改签名安全）。
- `parse_service._rewrite_placeholders`（`parse_service.py:94-108`）走 chapters 串替 `"media:rid"→"url"`。可在其后追加矢量失败处理。
- `result.warnings`（list[ParseWarning]）可在 `parse_service` 内追加，由 `build_parse_response` 透传（含 A 的 severity）。
- `main.py` 有 `lifespan` 启动钩子（:62）+ `/healthz`（:149）+ `/readyz`（:155，查 DB，失败 503）。
- B3 已让 `import_service` content 分支放行 `mark_status="review"`——C 的占位 content review 持久化**零新增**。
- 占位 `<img>` 形态 = normalizer 产 `<img src="media:rid"/>`（`ref.placeholder = f"media:{rid}"`）。

相关锚点：`utils/images.py:53-78`、`services/upload_service.py`（`write_temp_media`）、`services/parse_service.py:70-108`、`main.py:62-167`、`services/import_service.py:81`（B3 已放行 content review）。

---

## 2. 已确认的设计抉择

| # | 抉择 | 结论 |
|---|---|---|
| 1 | C 范围 | **完整版**：无法转换的矢量图 → 可见占位（`.sop-ph` 复用 B）+ content 节点标 review + `severity="blocking"` warning 触发 A 的强确认。结果干净（无过期坏图）。 |
| 2 | 软依赖探测 surface | **后端层**：`lifespan` 启动探测 + `logger.warning`；`/readyz` 加非致命 `soffice` 字段（缺失仍 200）。无前端管理后台 banner。 |
| 3 | 占位文案 | `[矢量图无法转换]`，块状 `<div class="sop-ph" data-ph="vector">`。 |
| 4 | health 字段落点 | `/readyz` 响应非致命 `soffice: "up"\|"down"`。 |

折中：用 A 的**强确认**而非硬拦截——拦的是「用户没意识到 N 张矢量图变占位」，不禁止导入。

---

## 3. 后端改动

### 3.1 `write_temp_media` 追踪矢量转换失败
`upload_service.write_temp_media` 返回签名从 `(mapping, assets)` 改为 `(mapping, assets, failed_vectors)`，`failed_vectors: set[str]` = 转换失败的矢量图 placeholder（`media:rid`）集合。循环内：
- 非矢量图：照旧（写盘、map、入 assets）。
- 矢量图转换成功（soffice 在）：照旧 png 路径。
- 矢量图转换失败（`convert_to_png` 返 None）：**不写原始 EMF、不 map、不入 assets**，把 `ref.placeholder` 加入 `failed_vectors`，`continue`。

### 3.2 `parse_service` 矢量失败 → 占位 + review + blocking warning
`parse_service.parse` 在 `_rewrite_placeholders(result, mapping)` 之后：
```python
mapping, assets, failed_vectors = upload_service.write_temp_media(token, result.image_refs)
_rewrite_placeholders(result, mapping)
n_failed = _swap_failed_vectors(result, failed_vectors)
if n_failed:
    result.warnings.append(ParseWarning(
        stage="image",
        message=f"本环境无法转换 {n_failed} 张矢量图（EMF/WMF），将以占位符导入",
        severity="blocking",
    ))
```
新增 `_swap_failed_vectors(result, failed_vectors) -> int`：走 chapters，对每个 content/chapter 节点的 `rich_content`，把每个失败 placeholder 对应的 `<img src="media:{rid}"/>` 替换为 `<div class="sop-ph" data-ph="vector">[矢量图无法转换]</div>`；被替换的节点 `mark_status="review"`；返回替换的图片总数。（`ParsedNode` 是可变 dataclass，含 `mark_status`。）

> 导入侧零新增：占位是纯 HTML、无临时 URL，`_promote_temp_urls` 不碰；content review 由 B3 持久化。成功转换路径不变。

### 3.3 软依赖探测
- `main.py` `lifespan`：启动时
  ```python
  from app.parser.utils import images
  if not images.soffice_available():
      logger.warning("LibreOffice (soffice) 不可用：EMF/WMF 矢量图将无法转换，导入时以占位符代替")
  ```
- `/readyz`：在返回 200 的 JSON 加 `"soffice": "up" if images.soffice_available() else "down"`（soffice 缺失**不**改变 200/503 判定，仅作能力降级标记；db down 仍 503 且不含 soffice 字段或含均可，以 db 判定为先）。

### 3.4 不触及的完整性语义
- C001 不受影响：矢量图在 structure 阶段已被 `_emit_images` 抽取计数（C001 在 parse_service 矢量替换**之前**评估），替换发生在其后。矢量「抽取」成功、只是「转换」失败，二者正交。
- C007（B）不受影响：矢量占位在 parse_service 加，不进 `Block.placeholder_count`；矢量失败有专属 blocking warning。

---

## 4. 前端改动
- `.sop-ph` 块状样式选择器加 `data-ph='vector'`（与 smartart/chart 同款卡片，PdfPreviewDialog `:deep`）。
- 强确认弹窗 / warning 流：复用 A，**零新增**（blocking warning 自动进 `ParseConfirmDialog`；content review 自动进复查导航）。

---

## 5. 数据流（端到端）

```
docx 含 EMF/WMF
  → normalize：矢量图 → ImageRef(ext=.emf/.wmf) + <img src="media:rid"/>；C001 抽取计数正常
  → structure：含该 img 的 content 节点
  → parse_service：
      write_temp_media 转换 → soffice 缺失/失败 → failed_vectors += placeholder（不写 EMF/不入 assets）
      _swap_failed_vectors：<img src="media:rid"/> → <div class="sop-ph" data-ph="vector">[矢量图无法转换]</div>；节点 mark_status=review
      n_failed>0 → result.warnings += blocking warning
  → /parse 响应：占位 HTML + review 节点 + blocking warning
  → 前端：blocking warning → ParseConfirmDialog 强确认；放行后 import
  → import：占位纯 HTML 原样落库；content review 持久化（B3）；结果干净无过期坏图
启动：lifespan 探测 soffice 缺失 → logger.warning；/readyz 暴露 soffice: up/down
```

---

## 6. 测试计划（TDD）

### 后端（pytest）
- `write_temp_media`：monkeypatch `convert_to_png` 返 None（模拟无 soffice）+ 一张 EMF ImageRef → 返回的 `failed_vectors` 含其 placeholder、assets 不含它、temp media 不写该文件。
- `write_temp_media`：convert 成功（monkeypatch 返 png bytes）→ failed_vectors 空、走 png。
- `parse_service`（或 `_swap_failed_vectors` 单元）：失败矢量 → rich_content 中 `<img src="media:rid"/>` 换成 `data-ph="vector"` 占位、该节点 mark_status="review"、result.warnings 含 1 条 `severity="blocking"`；无失败 → 无该 warning。
- `/readyz`：monkeypatch `soffice_available` True/False → 响应 `soffice` 字段对应 up/down，且仍 200。
- `lifespan`/启动：monkeypatch `soffice_available=False` → 记 warning（可用 caplog 或对 lifespan 直接调用断言）。
- 回归：后端全量。

### 前端（vitest）
- `.sop-ph[data-ph="vector"]` 占位渲染（结构契约守护，复用 B5 `parsePlaceholder.spec.ts` 风格，加一条）。
- 回归：前端全量。

---

## 7. 范围边界（YAGNI / 非目标）
- 不做前端管理后台 banner（健康探测仅后端 surface）。
- 不改硬拦截（强确认而非禁止导入）。
- 不改「有 soffice 时正常转 PNG」行为。
- 不动 A（强确认机制本体）、B（公式/SmartArt 占位）。
- 不实现 EMF/WMF 的纯 Python 渲染兜底（无 soffice 即占位）。
- D（C005）已对齐，不在本 spec。
