<!--
  这是 mingdao-worklog-api skill 的 AGENTS.md 声明片段。
  安装脚本会读取本文件，按需写入：
    - ~/.claude/CLAUDE.md   （Claude Code）
    - ~/.codex/AGENTS.md    （OpenAI Codex）
    - ~/.agents/AGENTS.md   （OpenCode / ZCode / Antigravity 通用）

  对每个目标文件：脚本会在文件末尾追加本片段，并用专有标记包裹，便于以后卸载或升级时识别删除。
  触发机制是「AGENTS.md 声明 + commit-msg hook」双保险（hook 单独装，安装时询问）。
-->

<!-- WORKLOG_MINGDAO_BEGIN -->
## 工作日志写入（明道云 mingdao-worklog-api）

本机已安装 `mingdao-worklog-api` skill — 通过明道云 v2 开放 API 直接向「工作日志」表新增记录，不依赖 hap-cli。

### 触发场景（agent 主动询问是否写日志）

| 时机 | agent 行为 |
|---|---|
| 用户做完业务工作后 | 主动问：「要不要写条工作日志？」 |
| 用户执行 `git commit` 前 | 先问要不要把这次 commit 关联到一条工作日志 |
| 用户明确说「写条日志 XXX」 | 直接调 skill，不要再追问 |

### 默认行为约定

1. **询问而非静默**：除非用户明确说「直接写」/「顺便填」/「别问」，否则永远先确认再写。
2. **字段解析**：从用户输入解析项目 / 员工 / 工时 / 日期 / 时段 / 工作内容。优先用 `match_project.py` 模糊匹配员工和项目名。
3. **缺一即问**：员工 / 项目 / 工时这三项是必填，缺哪个就问哪个，不要编造。
4. **默认员工**走 `config.json` 里的 `default_employee_name`（install 时必填，记录安装者本人），传了 `--employee-name` 就临时覆盖。
5. **项目」与「工作内容」分离**：项目是 rowid 关联，工作内容是自由文本。
6. **项目经理带出默认关闭（2026-09-14）**：默认不写「项目经理 / 项目经理用户」。原因：本部署有自动化会把「员工」改写成项目经理值。需要时 `--pm` 单次开启，或 config 设 `"autofill_pm": true`。

### 调用脚本

```bash
python "<skill_dir>/scripts/worklog_api.py" \
    --config "<skill_dir>/config.json" \
    add-row \
    --date "<YYYY-MM-DD，默认今天>" \
    --employee-name "<可不传，走 config>" \
    --project-name "<项目关键词，必填>" \
    --content "<工作内容>" \
    --hours <数字，必填> \
    [--shift 全天/上午/下午/其它] \
    [--dry-run]    # 只想看请求体时
```

### commit-msg hook（如果已装）

commit message 含下列任一 tag 时自动写日志：

- `#log` — 触发写日志
- `#time=Nh` 或 `#工时=Nh` — 工时（必填）
- `项目:XXX` — 项目名（缺则跳过）
- `[skip-worklog]` 或 `--no-verify` — 跳过本次

示例：

```bash
git commit -m "修复登录bug #log 项目:资产OA #time=2h"
```

### 写完必校验

响应里 `success: true` 且 `data` 是新 rowid 才算成功，给用户回报 rowid。任何失败要把 stderr 全文贴给用户分析。

### 安全

- `config.json` 含 appKey + secretKey，**绝不输出到对话**，**不入 git**。
- 凭证只放在脚本参数里、命令行历史里允许（安装时已经写过），但 agent 自己不要 echo 出来。

<!-- WORKLOG_MINGDAO_END -->
