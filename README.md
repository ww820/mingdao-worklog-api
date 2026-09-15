# mingdao-worklog-api

> 在任意 agent 工具（WorkBuddy / Claude Code / OpenAI Codex / OpenCode / ZCode / Google Antigravity）里说一句"帮我写条工作日志"，自动写入你的明道云工作日志表。

本仓库封装了一份**直接调用明道云开放 API** 的 skill，**不依赖 `hap` CLI 登录**，也不要求登录明道云网页。

适用场景：开发者在工作流里频繁要写工作日志，嫌手动到明道云系统维护烦。

---

## ⚙️ 前置条件

> 安装脚本会自动检测并安装缺失依赖，**正常情况下你什么都不用装**。只有离线/受限环境才需要手动装。

### 必须依赖（缺了就跑不起来）

| 依赖 | 最低版本 | 作用 | 装法 |
|---|---|---|---|
| **Python** | 3.8+ | 跑 `worklog_api.py` 调 API | 安装脚本自动装；离线时见下表 |
| **明道云 appKey + secretKey** | — | 调 API 用 | 在「明道云 → 应用 → 应用授权」获取 |

### 可选依赖（按需）

| 依赖 | 什么时候需要 | 装法 |
|---|---|---|
| **Git** | 想用 commit-msg hook（提交时自动写日志）/ 想用 `git pull` 升级 | Windows: [Git for Windows](https://git-scm.com) ；macOS: `xcode-select --install`；Linux: `apt install git` |

> 💡 **Git 不是必须的**。装 skill / 写工作日志都不需要 git。
> - 在线安装走 `irm ... \| iex` 或 `curl ... \| bash`，本身不依赖 git
> - 没 git 时 install 脚本自动 fallback 到下载 GitHub zipball/tarball 解压
> - 没 git 时 commit-msg hook 步骤会自动跳过（不影响其它功能）
>
> 想用「git commit 自动写工作日志」时再装 git，install 脚本重跑一次即可补上 hook。

### 手动装 Python（仅当自动装失败时）

**推荐用 `uv`**（Astral 出品，~13MB 单 exe，跨平台一致，装好后 5 秒内可用）：

| 平台 | 一行命令 |
|---|---|
| **Windows** | `irm https://astral.sh/uv/install.ps1 \| iex` |
| **macOS** | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Linux** | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

装完后 `uv run python --version` 验证；之后 hook / install 脚本会自动用 `uv run` 跑 Python 脚本。

**或者装完整 Python**：

| 平台 | 装法 |
|---|---|
| Windows | `winget install Python.Python.3.12` 或从 [python.org](https://www.python.org/downloads/) 下载 |
| macOS | `brew install python3` |
| Ubuntu / Debian | `sudo apt install python3` |
| CentOS / RHEL | `sudo yum install python3` |
| Arch | `sudo pacman -S python` |

---

## ✨ 核心特性

- **一行命令安装到任何 agent 工具**：WorkBuddy / Claude Code / Codex / OpenCode / ZCode / Antigravity 全部支持
- **AGENTS.md 声明方式触发**：agent 启动时读 SKILL.md 描述，判断该不该调
- **可选 commit-msg hook**：`git commit -m "fix #log 项目:资产OA #time=2h"` 自动写工作日志
- **老板本/员工本共享一份源**：通过 junction / symlink 链接，凭证只填一次
- **跨平台**：Windows PowerShell + macOS/Linux Bash
- **ownerid/caid 自动联动**：写工作日志时，拥有者字段自动从员工档案取 HAP accountId，创建人同步

---

## 🚀 一行安装

### Windows (PowerShell)

```powershell
irm https://raw.githubusercontent.com/hemiyang2011-commits/mingdao-worklog-api/main/installer/install.ps1 | iex
```

回车后会提示：

```
[2/8] 获取明道云凭证 + 默认员工名称
  在「明道云 → 应用 → 应用授权」获取 appKey + secretKey
  appKey: 4989bba1409c354e
  secretKey (不回显): ********
  默认员工名称：不传员工参数时按这个名字写日志（必填，例如你的真实姓名）
  默认员工名称（必填，不能直接回车）: 杨浪
```

### macOS / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/hemiyang2011-commits/mingdao-worklog-api/main/installer/install.sh | bash
```

### 跳过交互（CI / 离线）

```bash
# bash
REPO_URL=https://github.com/hemiyang2011-commits/mingdao-worklog-api.git \
MINGDAO_APPKEY=xxx \
MINGDAO_SECRETKEY=yyy \
MINGDAO_DEFAULT_EMPLOYEE="<你的真实姓名>" \
    curl -fsSL .../install.sh | bash

# PowerShell
$env:REPO_URL="https://github.com/hemiyang2011-commits/mingdao-worklog-api.git"
$env:MINGDAO_APPKEY="xxx"
$env:MINGDAO_SECRETKEY="yyy"
$env:MINGDAO_DEFAULT_EMPLOYEE="<你的真实姓名>"
irm .../install.ps1 | iex
```

> Windows 脚本为了兼容 `irm ... | iex` **统一走环境变量传参**，不再使用 `-LocalSource` 等参数。

---

## 📦 安装脚本会做什么

| 步骤 | 行为 |
|---|---|
| 1 | 检测 `python3` 是否安装（git 可选，缺失时走 zipball/tarball 下载） |
| 2 | 询问 / 接收 appKey + secretKey（不回显）+ 默认员工名称（**必填**，从环境变量或交互输入） |
| 3 | git clone 到 `~/.workbuddy/skills/mingdao-worklog-api/`（已存在则 pull） |
| 4 | 写入 `config.json`（从 example + 凭证 + 默认员工） |
| 5 | 在 6 个 agent 工具目录建 junction / symlink（探测式，仅对存在的工具生效） |
| 6 | 写入 `~/.claude/CLAUDE.md` / `~/.codex/AGENTS.md` / `~/.agents/AGENTS.md` 三份声明（追加在已有内容尾部） |
| 7 | 若装了 git：询问是否安装 `commit-msg` hook；未装则自动跳过（默认 Y） |
| 8 | 跑 `test-auth` 验证链路通 |

> ⚠️ 安装脚本是**幂等的**——重复跑会跳过已完成步骤。更新 hook / config 时设环境变量 `WORKLOG_FORCE_CONFIG=1` 才会覆盖。

### 跳过交互（CI / 离线）

```bash
# bash
REPO_URL=https://github.com/hemiyang2011-commits/mingdao-worklog-api.git \
MINGDAO_APPKEY=xxx \
MINGDAO_SECRETKEY=yyy \
MINGDAO_DEFAULT_EMPLOYEE="<你的真实姓名>" \
    curl -fsSL .../install.sh | bash

# PowerShell
$env:REPO_URL="https://github.com/hemiyang2011-commits/mingdao-worklog-api.git"
$env:MINGDAO_APPKEY="xxx"
$env:MINGDAO_SECRETKEY="yyy"
$env:MINGDAO_DEFAULT_EMPLOYEE="<你的真实姓名>"
irm .../install.ps1 | iex
```

### 环境变量清单（PS 用 `$env:NAME`，bash 用 `NAME=value`）

| 变量 | 作用 |
|---|---|
| `MINGDAO_APPKEY` | 明道云 appKey（交互时会被问到） |
| `MINGDAO_SECRETKEY` | 明道云 secretKey（交互时不回显） |
| `MINGDAO_DEFAULT_EMPLOYEE` | 默认员工姓名（**必填**，CI / 跳过交互用） |
| `REPO_URL` | 自定义仓库，默认是 hemiyang2011-commits 的 GitHub |
| `BRANCH` | 自定义分支，默认 `main` |
| `WORKLOG_LOCAL_SOURCE` | 本地开发：从本地目录拷源文件，不走 git/zipball |
| `WORKLOG_TARGET_DIR` | 测试用：覆盖默认安装路径 |
| `WORKLOG_FORCE_CONFIG` | 若设置，强制覆盖已存在的 `config.json` |
| `WORKLOG_NO_HOOK` | 若设置，跳过 commit-msg hook 安装 |
| `UNATTENDED` | 若设置，全程不弹交互（必须同时设 appKey / secretKey / defaultEmployee） |

---

## 🎯 触发机制（重点）

我们提供**双保险**：

### 1. AGENTS.md 声明（默认开启）

agent 工具启动时会读自己的 `CLAUDE.md` / `AGENTS.md`，里面有关于「工作日志」声明：

> **触发场景**：用户说"写条工作日志" / 完成业务工作后 / commit 前
> **默认行为**：agent 主动问"要不要写条日志"，用户说"写" → 调 skill

**好处**：用户**完全控制权**，不会被静默写日志。

### 2. git commit-msg hook（可选安装）

如果第 7 步选了 Y，会装一个 commit-msg hook：

```bash
git commit -m "修复XX bug #log 项目:资产OA #time=2h"
```

| tag | 含义 |
|---|---|
| `#log` | 触发写工作日志（必填） |
| `#time=Nh` 或 `工时:Nh` | 工时数字（必填，缺则跳过不阻断 commit） |
| `项目:XXX` | 项目名（必填，会模糊匹配） |
| `[skip-worklog]` | 跳过本次 commit 的工作日志 |
| `--no-verify` | git 自带机制跳过所有 hook |

第一个 commit message 行去掉 tags 后作为「工作内容」。

**跳过方法**：

```bash
git commit -m "docs: README排版 #log #time=1h [skip-worklog]"
# 或
git commit --no-verify -m "重构"
```

---

## 🤖 各 agent 工具适配

安装脚本会探测式地把 skill 链接到下面 6 个目录（**只链接本机已存在的工具目录**，不会为没装的工具凭空创建）：

| 工具 | 链接目标目录（Windows 等同） | skill 来源 |
|---|---|---|
| **WorkBuddy** | `%USERPROFILE%\.workbuddy\skills\mingdao-worklog-api\` | 直接装在此目录，WorkBuddy 默认扫描 |
| **Claude Code** | `%USERPROFILE%\.claude\skills\mingdao-worklog-api\` | [Claude Code skills 文档](https://docs.claude.com/en/docs/claude-code/skills) |
| **OpenAI Codex** | `%USERPROFILE%\.codex\skills\mingdao-worklog-api\` | [Codex CLI skills 文档](https://github.com/openai/codex) |
| **OpenCode** | `%USERPROFILE%\.config\opencode\skills\mingdao-worklog-api\` | [OpenCode skills 文档](https://opencode.ai/docs/skills) |
| **ZCode（智谱）** | `%USERPROFILE%\.zcode\skills\mingdao-worklog-api\` | [ZCode Skill 文档](https://zcode.z.ai/docs/skill) |
| **Google Antigravity** | `%USERPROFILE%\.gemini\config\skills\mingdao-worklog-api\` | [Antigravity Skills 文档](https://antigravity.google/docs/skills) |

> macOS / Linux 把 `%USERPROFILE%` 换成 `~` 即可（路径都是 `~/.xxx/skills/...`）。
> Antigravity 同时也认 `.agents/skills/`，本脚本已经包含这个目录作为兜底。

### 在每个工具里的实际用法

#### WorkBuddy
直接在对话里说：
> "帮我写条工作日志：资产OA 系统 开发 2 小时"

WorkBuddy 启动时会扫描 `~/.workbuddy/skills/`，看到 SKILL.md 里的 description 就会自动调用。

#### Claude Code
在 Claude Code 里说话触发（agent 读 `~/.claude/skills/mingdao-worklog-api/SKILL.md`）：
```
@mingdao-worklog-api 帮我写条工作日志
```
或直接：
> "帮我写条工作日志：资产OA 系统 2 小时"

启动新会话时 Claude Code 也会读 `~/.claude/CLAUDE.md`，里面有这段声明后会主动问"要不要写条日志"。

#### OpenAI Codex
Codex CLI 启动时会读 `~/.codex/AGENTS.md` 里的声明（install 脚本已写入）。直接对话触发：
> "Add a worklog row for me: project 资产OA, 2 hours"

或在提示里 mention skill：`/mingdao-worklog-api 写一条今天的日志`。

#### OpenCode
OpenCode 启动时会扫描 `~/.config/opencode/skills/`（同时兼容 `~/.claude/skills/` 和 `~/.agents/skills/`，所以即使你装的不是 OpenCode 的 symlink 也能找到）。
```
> /mingdao-worklog-api 写一条工作日志
```
或在聊天里 mention：`use skill mingdao-worklog-api to log today's work`。

#### ZCode（智谱）
打开 ZCode → 设置 → 技能，确认「mingdao-worklog-api」出现在列表里并**启用**。
然后在聊天里输入 `$mingdao-worklog-api` 加你的需求：
```
$mingdao-worklog-api 帮我写条日志，2 小时，项目是资产OA 系统
```
或者用 ZCode 的导入功能从 Claude Code / Codex CLI 目录一键导入（无需手动软链）。

#### Google Antigravity
Antigravity 启动时扫描 `~/.gemini/config/skills/`（也认 `~/.agents/skills/`）。直接对话：
> "Use the mingdao-worklog-api skill to log today's work: 2 hours on 资产OA"

Antigravity CLI（`agy`）的话会把它转成 slash command `/mingdao-worklog-api`：
```
> /mingdao-worklog-api 写一条今天的日志
```

### 验证 skill 是否被识别

跑完 install 后，到对应工具的设置 / skills 列表里看有没有「mingdao-worklog-api」。如果没有：
1. 确认链接目录里能看到 `SKILL.md`：`ls ~/.workbuddy/skills/mingdao-worklog-api/SKILL.md`
2. 确认 frontmatter 含 `name: mingdao-worklog-api` 和 `description:` 字段
4. 重启 agent 工具（部分工具只在启动时扫一次）

---

## 🛠 日常使用

### 在 agent 里说一句话

> "帮我写条工作日志：资产OA 系统 开发 1 小时"

agent 自动：
1. 项目按"资产OA 系统"模糊匹配
2. 员工走 config 默认（install 时必填）
3. owner 自动从员工档案取 = 你自己的 HAP accountId
4. 时段默认"全天"
5. 调 `add-row` → 拿回新 rowid → 报给你

**项目经理带出默认关闭（2026-09-14 起）**：本部署有自动化会把日志「员工」改写成项目经理值，
疑似与写入项目经理字段相关，因此默认不写。需要时加 `--pm` 单次开启，或 config 设
`"autofill_pm": true`；`--no-pm` 可单次强制关闭。

### 命令行直接写（不进 agent）

```bash
python ~/.workbuddy/skills/mingdao-worklog-api/scripts/worklog_api.py \
    --config ~/.workbuddy/skills/mingdao-worklog-api/config.json \
    add-row \
    --date 2026-09-10 \
    --project-name "资产OA 系统" \
    --content "修复登录 bug" \
    --hours 2
```

### 替别人写

```bash
python ... add-row \
    --employee-name "<被替写的员工姓名>" \
    --project-name "三农二期" \
    --content "..." --hours 3
```

---

## 📂 仓库结构

```
mingdao-worklog-api/
├── README.md
├── LICENSE                          MIT
├── .gitignore                       排除 config.json / __pycache__
├── SKILL.md                         agent 启动时读的 skill 描述（YAML frontmatter + Markdown）
├── scripts/
│   ├── worklog_api.py               主脚本（list-projects / list-employees / add-row / test-auth / sign）
│   └── match_project.py             模糊匹配项目名 / 员工名
├── references/
│   └── api_reference.md             API 字段 ID 速查（按本应用定制）
├── config.example.json              公开模板（**不含凭证**，可放心 commit）
└── installer/
    ├── install.ps1                  Windows 一键安装
    ├── install.sh                   macOS / Linux 一键安装
    ├── uninstall.ps1                Windows 一键卸载
    ├── uninstall.sh                 macOS / Linux 一键卸载
    ├── AGENTS.fragment.md           AGENTS.md 声明片段模板（被 install 脚本读取并 append 到用户配置）
    └── hooks/
        └── commit-msg               git commit-msg hook 脚本
```

---

## 🔧 配置 `config.json`

复制 `config.example.json` 为 `config.json`，最少填两项：

```json
{
  "appKey":    "你的明道云 AppKey",
  "secretKey": "你的明道云 SecretKey（直接当 sign 用，无需计算签名）"
}
```

**注意**：`config.json` 已被 `.gitignore` 排除，**绝不**入库。

### 可选字段

| 字段 | 默认行为 |
|---|---|
| `default_employee_name` | 不传员工参数时按这个名字自动模糊匹配。空则每次必传。 |
| `default_employee_rowid` | 比 `default_employee_name` 优先；找到 rowid 直接用，不走匹配。 |
| `default_owner_account_id` | 不传 `--owner-account-id` 时用这个；缺省自动从员工档案取。 |

---

## 🧹 卸载

```powershell
# Windows
irm .../installer/uninstall.ps1 | iex

# 默认保留 config.json（含凭证） + skill 目录（避免误删）
# 加 -RemoveConfig -RemoveDir 强制删
```

```bash
# macOS / Linux
curl -fsSL .../installer/uninstall.sh | bash
# 或：./installer/uninstall.sh --remove-config --remove-dir
```

---

## ❓ 疑难排查

| 现象 | 排查 |
|---|---|
| 安装完 `test-auth` 返回 `ok: true` 但 add-row `10005 数据操作无权限` | 你还没授权这个应用的 API 访问全部视图（在明道云后台 → 应用 → API 开发 → 授权 / 数据权限里勾上「获取行记录列表」） |
| `agent 没主动问我要不要写日志` | AGENTS.md 声明没被写到。看 `~/.claude/CLAUDE.md` 末尾是否含 `WORKLOG_MINGDAO_BEGIN` 块 |
| `commit 没自动写日志，但 commit 没报错` | 可能选了 `--no-verify` 或 commit message 没 `#log` tag |
| `agent 写出来了但内容错了` | 项目名模糊匹配有多个候选。看 stderr `score=xx reason=...` 选对的 |

---

## 🔒 安全

- `config.json`（含凭证）**不入 git**，已写进 `.gitignore`
- 安装脚本读取输入时不回显 secretKey
- `commit-msg` hook 不会把凭证写到 commit message
- 仓库公开，但凭证是**每个用户自己填**的；fork 后也不会继承他人的凭证

---

## 📜 License

MIT — see [LICENSE](LICENSE)
