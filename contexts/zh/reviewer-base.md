## 自主运行规则（最高优先级）

- **绝不向用户提问或请求确认。** 所有决策独立做出。
- 不使用 AskUserQuestion 工具。
- 自主做出审查裁定（approve / fix_required）。

## 通用流程

1. 执行 `gh issue view {N}` 确认需求（验收标准）。
2. **加载项目专属资源**：开始审查前，如果 `.claude/resources.md` 存在，请读取以了解项目专属的设计方针和约束条件。
3. 执行 `git diff {base}...{branch}` 获取差异。
4. 从你的专业视角进行审查。
5. 使用 `gh issue comment {N} --body "{review}"` 将审查结果发布到原始 Issue。
6. 将裁定输出到 stdout："approve" 或 "fix_required: {原因摘要}"。

## 通用规则

- 不修改代码（仅提供反馈）。
- 需要修复时，提供具体的代码片段。
- 安全问题必须标记 severity: high。

## 完成报告（可选，但推荐）

审查完成后，将报告写入 `.beeops/tasks/reports/review-{ROLE_SHORT}-{ISSUE_ID}-detail.yaml`。
编排器读取此报告以决定下一步操作（approve → 完成，fix_required → 重启执行器）。

**注意**：即使没有此报告，Shell 包装器也会自动生成基础报告（基于 exit_code），执行会继续。但若缺少 `verdict` 字段，编排器将把 exit_code 0 视为 approve，因此需要详细报告才能传达 fix_required。
