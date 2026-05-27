# 前端编辑能力增强（融合式标题等结构后处理）设计

**日期：** 2026-05-27
**状态：** 草案（待 brainstorm）
**作者：** 协作设计（cui_yuming + Claude）

## 背景

Word 解析器打磨闭环（[`2026-05-27-word-parser-polish-design.md`](2026-05-27-word-parser-polish-design.md)）于 2026-05-27 达 5/5 严强阈值并完成 L1 重构（信号注册表）。综合评估后期发现：

- ~30 mainline + ~150 Tier 3 共约 **180 个"融合式" chapter**：原 docx 一个段落里同时包含"号+短标题+长正文"，例如 `3.1质量部是记录的归口管理部门，负责组织全公司记录表格的编制和校审。`
- 当前 parser 把整段作为 chapter title（正确——符合 spec §6 顺序保真不变量与"parser 不改原结构"原则）
- 但 UX 上：树标题被撑爆、content 子节点空、PDF 渲染换行不优

为什么不在 parser 端切？见 [`parser-comprehensive-evaluation.md`](../../parser-comprehensive-evaluation.md) §3.5：parser 切=算法猜，违反"决策权归用户"；只能 UI 端用户主导切。

## 目标（待 brainstorm 细化）

1. **降低融合式 chapter 的 UX 摩擦**：用户能快速完成"长标题转内容 / 拆 heading + content / 批量调整"，从当前 N 步操作降到 1-2 步
2. **不动 parser 与 backend API**：所有改进只在前端编辑器层；后端 ParseResult 形态不变
3. **保留"决策权归用户"**：所有重组操作都由用户显式触发，非自动

## 候选改进项（待 brainstorm 优选 / 优先级排序）

> ⚠️ 下列为讨论入口；具体特性、UX 流程、热键、可视样式均需 brainstorm 与 visual mockup 后才能定。

### A. 树标题截断展示
- 树视图 chapter 标题超 N 字（30？50？）截断 + tooltip / hover 展示全文
- 0 数据改动，纯 CSS / Vue 渲染层
- 优势：风险最低，可作为首批改进

### B. "标题转内容"快捷操作
- 在 chapter 节点上一键转换为 content 节点
- 若 chapter 有子节点，需决策：吸收为同级 / 并入上一章节 / 提示用户
- 涉及编辑器现有 markStatus / 类型转换基础设施扩展

### C. "拆 heading + content"手势
- 用户在融合式 chapter 标题里拖光标到 ":" / "。" / "，" 等位置 → 按热键 split node
- 拆完产出：原 chapter 标题缩到光标前 + 新增同 chapter 下首个 content 节点为光标后内容
- 需要决定：光标位置如何持久化、撤销栈如何记录

### D. 模式批量提升 UI 完整化
- 后端 `detected_patterns` 已产出（按编号前缀归组）；前端 review panel 是否已有"按模式选择性提升"完整 UI？需查
- 用户操作：看分组 → 勾选若干组 → 批量执行（如把所有 `N.N+CJK直连` 长段批量"拆 heading + content"）

### E. 长标题的"可视化拆分预览"
- 在标题字段下方放一个交互预览：自动按"："候选切点亮出 split 位置，用户点选确认
- 不自动切，但提供拆分建议

## 范围

**做（暂定）：** A + B + 部分 C / D（具体范围 brainstorm 时定）
**明确不做：**
- 任何 parser / 后端 API 改动
- 任何自动拆分（必须用户触发）
- 任何 docx 重导入或重新解析

## 必要前置条件

- 后端 ParseResult 形态保持 [`word-parser-solution.md`](../../word-parser-solution.md) 当前版（§6.1 段落粒度 1:1 不变量）
- 现有"接受待确认 / 拒绝 / 类型转换"基础设施可被复用

## 下一步

进入 brainstorming 流程：

1. 用户在 36 份样本里挑出 2-3 个"标题过长拖垮 UX"的典型 chapter，作为产品需求佐证
2. visual companion / mockup 对照 A-E 方案做交互对比
3. 选定优先级后写完整 spec → plan → 实施

> 本文档是 placeholder，**未经 brainstorm 不应直接进入实施**。
