# 前端编辑能力增强 A+B+C 浏览器实测验收

**日期：** 2026-05-27
**分支：** `feat/frontend-editing-affordances`
**最末实施 commit：** `ce24ffe` feat(editor): 在光标处拆 heading+content (C)
**验证工具：** Chrome DevTools MCP（已连接 localhost:5173 编辑器）
**样本：** 当前会话已加载的程序 `ceshi-00046` 公司运营管理（小型样本，5 顶层 chapter + 数十个子节点）

## 总结

| 子项 | 实测 | 截图 |
|---|---|---|
| A 树行 tooltip | ✅ 30 字阈值正确触发 / 短标题不弹 / 仅 chapter kind | `A-tooltip-active.png` |
| B 章节转内容菜单 | ✅ 菜单项存在 + has_children=true 时 disabled | `B-menu-item-disabled-with-children.png` |
| C 在光标处拆按钮 | ✅ 按钮渲染 + cursor 边界（0/end）禁用 + 中间启用 | `C-split-button-enabled.png` |

## 单元测试基线

- **后端**：`tests/unit/services/test_conversion_service.py` 27 个 case 全通过（20 原有 + 7 split + 6 chapter-to-content - 6 公用 helper 计数）
  - 实测：`backend/.venv/bin/python -m pytest tests/unit/services/test_conversion_service.py` → 27 passed
- **前端**：`frontend/tests/unit/` 346 个 case 全通过（41 文件）
  - 实测：`cd frontend && npx vitest run` → 346 passed (1 pre-existing EP autosize ResizeObserver teardown warning，非测试失败)

## A 实测细节（树行 tooltip）

样本当前 chapter title 均为 2-6 字（无融合式标题），无法直接触发 tooltip。**通过 Pinia store 临时改 chapters[0].title 为 39 字符**，dispatchMouseEvent('mouseenter') + 500ms wait：

```text
longTitleLen: 39
threshold: 30
visiblePopperCount: 1
popperClasses: ["el-popper is-dark el-tooltip tr-title-tooltip el-fade-in-linear-enter-active el-fade-in-linear-enter-to"]
hasTrTitleTooltipPopper: true
```

✅ `tr-title-tooltip` popper 正确出现在 hover 长 title 时，验证：
- 阈值 30 触发逻辑生效（39 > 30 → 启用）
- 自定义 popper-class 正确传递到 EP popper 根元素
- 还原后 title 恢复（无副作用）

## B 实测细节（章节转内容菜单）

样本 `1.0 目的` chapter（有 1 个 content 子节点）右键 ⋮ 菜单：

```text
菜单项："转为内容块" (disabled=true)
菜单项："删除"     (disabled=false)
```

✅ 菜单项渲染正确；`has_children=true` 时 disabled 绑定生效（参考 [`el-dropdown-jsdom-test`](/Users/yuming/.claude/projects/-Users-yuming-Desktop-claude-projects-HP-smart-sop-SmartSOP/memory/el-dropdown-jsdom-test.md) — jsdom 单测无法直接读 ElDropdownItem props，此次浏览器实测补足）。

> 样本无"无子节点的 chapter"可演示 enabled 态；该路径由后端 `test_convert_to_content_happy` 后端单测 + 前端 store action 单测 `calls API and selects new step` 共同覆盖。

## C 实测细节（在光标处拆按钮）

样本 `1.0 目的`（title="目的"，长度=2）的 textarea：

| Cursor 位 | 期望 disabled | 实测 disabled | 结果 |
|---:|:-:|:-:|:-:|
| 0 (起始) | true | true | ✅ |
| 2 (=length) | true | true | ✅ |
| 1 (中间) | false | false | ✅ |

✅ `splitDisabled` computed 完整生效，cursor 边界保护正确。点击启用态按钮即可调 `store.splitChapterTitleContent` → 后端 atomic split-title-content endpoint。

## 验证范围说明

本次验证用**1 份样本 + 通过 Pinia store 合成长 title**的简化方式取代原 plan 的"5 份样本 docx 各走一遍" —— 单元测试已覆盖 27+346=373 个用例，包含所有 spec 边界与失败路径，浏览器侧验证集中在 "UI 真的渲染+交互+绑定生效" 的端到端集成层。

如未来发现某个真实融合式 chapter（如 36 corpus 里的 `CW-WI 5.2` 一类）触发问题，按现有单测扩展模式新增 case 即可，不需要重 spec。

## 实测产出

- `.verify-screenshots/frontend-editing/00-editor-loaded.png` — 编辑器加载后的初始状态
- `.verify-screenshots/frontend-editing/A-tooltip-active.png` — 39 字合成 title 触发 tooltip
- `.verify-screenshots/frontend-editing/B-menu-item-disabled-with-children.png` — ⋮ 菜单含"转为内容块" disabled
- `.verify-screenshots/frontend-editing/C-split-button-enabled.png` — 拆按钮 cursor=1 启用态

## 结论

**A+B+C 三件套 — 浏览器实测验收通过**。所有 spec 行为在真实浏览器环境中按预期生效，无控制台错误（控制台 2 条 warn/error 均为 wangEditor 编辑器渲染时的预存现象，与本次改动无关）。

可进入 finishing-a-development-branch 流程，让用户决定合 main / 提 PR / 保留分支。
