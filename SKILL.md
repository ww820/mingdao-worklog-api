---
name: mingdao-worklog-api
description: 用明道云「工作表 API」（HTTP 直连，非 hap-cli）向「工作日志」表插入记录。当用户要写/记一条工作日志、且希望走 API 开发文档（appKey/sign）而非 hap-cli 时触发，例如「用 API 插一条工作日志」「按工作表API写日志：琼中快就业 9月4日 8小时」「把今天的工作日志通过接口写进去」。核心是脚本 scripts/worklog_api.py 的 add-row 子命令：解析自然语言 → 匹配员工/项目 rowid → 构造 controls → POST addRow。员工和项目支持 config 预置（默认如「杨浪」），命令行可显式覆盖；输入里给出员工/项目名时按名模糊匹配。
agent_created: true
---

# mingdao-worklog-api

## Overview

通过明道云 v2 开放 API（`POST /v2/open/worksheet/addRow`）把一条工作日志写进
「思凡数字核算系统」的「工作日志」表。与 `hap-worklog-writer`（走 hap-cli）的区别是：
本 skill **不依赖 hap 登录**，直接拿 appKey + sign 发 HTTP 请求，适用于任何有 Python 的环境。

用户通常一句话描述一条日志 —— 员工 + 项目 + 日期 + 工时 + （可选）时段 + （可选）内容。
本 skill 负责：解析字段、把**员工名**和**项目名**分别模糊匹配成 rowid、构造 controls、
调用 addRow。员工与项目**支持 config 预置**（如 `default_employee_name: "杨浪"`），命令行可显式
传 `--employee-name` / `--project-name` / `--employee-rowid` / `--project-rowid` 覆盖。
拥有者（`ownerid`）默认按员工档案自动取，可通过 `--owner-account-id` 覆盖。

## 系统字段约定（实测）

明道云工作表有 3 个系统级账号字段：

| 字段 | 含义 | 能否在 addRow controls 里写入？ | 实测当前值 |
|---|---|---|---|
| `caid` | 创建人 | ⚠️ 不能直接写；但**写入 ownerid 后会自动同步成 ownerid 的值** | 跟 ownerid 一致；不写 ownerid 时 = `API`（应用授权身份） |
| `uaid` | 最后修改人 | ❌ 不能，只读 | 一般跟 caid 一致；addRow 后被工作流触发则 = `user-workflow` |
| **`ownerid`** | **拥有者** | ✅ **能**，controls 里加 `{"controlId":"ownerid","value":"<HAP accountId>"}` | 默认 `未指定`；写入后 `caid` 同步更新 |

**「拥有者/创建人」字段补充方式**（按优先级）：
1. `--owner-account-id <HAP accountId>` 命令行覆盖
2. `config.default_owner_account_id`（兜底默认）
3. **如果 1、2 都为空**：自动用 V3 单行查员工档案的「成员」/「外部账户」字段拿 HAP accountId
   - 内部员工 → 字段 `6938b7c20b2e62809471cb71`「成员」（UUID 格式 accountId）
   - 外部员工 → 字段 `69378a055326c71216b4a864`「外部账户」（`a#<UUID>` 格式）
4. 都没有：ownerid 留空（HAP 显示「未指定」）

**自动取数优先级**意味着：写工作日志只要给员工 rowid，**ownerid 和 caid 都会自动变成该员工的 HAP 账号**——不用每次手动传 `--owner-account-id`。

> ⚠️ 注意：`uaid`（最后修改人）**仍然不能直接控制**，且 addRow 后被工作流触发会被改成 `user-workflow`，这是 HAP 内置行为。

## 鉴权（关键，勿再踩坑）

明道云「**应用授权**」里的 `AppKey` + `SecretKey` 中，那个 `SecretKey` 实际上是一个
**预生成的静态签名（Sign）**。调用接口时**直接原样当 `sign` 用**：

- 请求体：`appKey` = 应用密钥，`sign` = SecretKey 值**原样**。
- **无需**计算签名、**无需**拼接 `AppKey=...&SecretKey=...&Timestamp=...`、**无需**传时间戳。

> 注意区分：只有「组织密钥」（组织管理 → 其他 → 组织密钥）才是
> `AppKey + SecretKey + Timestamp` 做 SHA256 再 base64 的那套签名。
> 本 skill 用的是「应用授权」密钥，sign 就是 SecretKey 值本身，实测直接使用即可通过。

## Preconditions（首次使用前必须完成）

1. **config.json 就位**：把 `config.example.json` 复制为同目录 `config.json`，填入
   `appKey`、`secretKey`。其余字段（工作表 ID、字段 ID、时段 key、员工/项目档案表信息）已按本应用预填。

   获取密钥（应用授权）：
   - 明道云 → 应用 → 目标应用 → **授权管理** → 新建/查看授权密钥。
   - `appKey`：授权里的 AppKey（16 位 hex）。
   - `secretKey`：授权里的 SecretKey（base64 串）——这就是 sign，接口里直接当 `sign` 传。

2. **Python 可用**：脚本是纯标准库（urllib/json），任意 Python 3.8+ 即可。

3. **验证鉴权**：
   ```bash
   python "<skill_dir>/scripts/worklog_api.py" --config "<skill_dir>/config.json" test-auth
   ```
   返回 `ok: true` 且 `worksheet_name` = 工作日志 即鉴权正确。

4. **读取权限（做「员工名/项目名 → rowid」匹配的前提）**：
   明道云授权是**按「视图」粒度**授权的，`getFilterRows` 必须带被授权的视图 `viewId`，
   否则 `10005 数据操作无权限`。本应用已实测可读的视图及 viewId 已写进 config.json：

   | 表 | 可读视图 | 读取字段 key |
   |---|---|---|
   | 员工档案 | 员工通讯录（`employee_view_id`） | `employeeName`（别名） |
   | 项目档案 | 项目（`project_view_id`） | `65e57b98af2cbab9cc8bb162`（controlId） |

   若换环境/换表后 `list-employees` / `list-projects` 又报 10005，去
   【应用 → 授权管理 → 编辑该授权】给对应**视图**勾「获取行记录列表」权限，
   并用 `getWorksheetInfo` 找到可读视图的 viewId 回填 config.json。

## Workflow

### Step 1. 解析用户输入

从一句话里抽出字段：

| 字段 | 缺省 | 提取方式 |
|---|---|---|
| 日期 | 今天 `YYYY-MM-DD` | 正则 `\d{4}-\d{1,2}-\d{1,2}` / `\d{1,2}月\d{1,2}日` / 「今天/昨天」 |
| 员工名 | **config 预置**（如 `default_employee_name: "杨浪"`） | 没显式提到员工 → 用 config；用户说「员工 XX」或「替 XX 记」→ 按名模糊匹配 |
| 项目名 | **config 预置**（如 `default_project_name: "..."`） | 同上 |
| 工时 | 必填 | `\d+\s*(小时|h|H|个工时)` 或「小时」前的整数 |
| 时段 | 全天 | 匹配 全天/上午/下午/其它 |
| 工作内容 | 剩余文本 | 未被上面消费的文本 |

只有工时缺失才追问；员工/项目有 config 兜底。

### Step 2. 解析「员工名 → rowid」和「项目名 → rowid」

员工、项目都是关联字段，只认 rowid。**`add-row` 子命令内部自动完成以下解析**，agent
不需要手写：调用脚本时，脚本会按以下优先级解析 rowid（员工、项目分别套用）：

1. `--employee-rowid` / `--project-rowid` 命令行 rowid（最高优先）
2. `--employee-name` / `--project-name` 按名模糊匹配（脚本内置 `match_project.py` 算法）
3. `config.default_employee_rowid` / `default_project_rowid` 直接用
4. `config.default_employee_name` / `default_project_name` 按名模糊匹配
5. 都没有 → 报错（让用户传或去档案表新建）

> **说明**：步骤 2-4 中按名匹配时，脚本会读 `~/.workbuddy/cache/mingdao-worklog-api/employees_full.json` 或
> `projects_full.json`（首次没有缓存就调一次 `getFilterRows` 拉全表写到缓存）。多个 agent 工具通过 junction
> 共用这一份缓存，不会重复拉取。

### Step 3. 写入记录

```bash
python "<skill_dir>/scripts/worklog_api.py" --config "<skill_dir>/config.json" add-row \
    --date "2026-09-04" \
    --employee-name "杨浪"          # 可选；不传则走 config 默认
    --project-name "资产管理系统与OA系统"  # 可选；不传则走 config 默认
    --content "开发2小时" \
    --hours 2 \
    --shift 全天 \
    [--employee-rowid "<直接 rowid>"]   # 显式 rowid（优先级最高）
    [--project-rowid "<直接 rowid>"]
    [--owner-account-id "<HAP accountId>"]   # 覆盖 config 默认的 ownerid
```

- 时段传中文即可，脚本内部映射到 key。
- 想先看请求体不发请求，加 `--dry-run`。
- 员工/项目任一未传：脚本内部自动走 config 默认值（按名模糊匹配）。
- **项目经理带出默认关闭（2026-09-14）**：本部署有自动化会把日志「员工」改写成项目经理值，
  疑似与写入项目经理字段相关，因此默认不写这两个字段。需要时 `--pm` 单次开启，
  或 config 设 `"autofill_pm": true`；`--no-pm` 可单次强制关闭。开启时成员控件 value 是
  **单个 accountId 字符串**（数组会报 10001）。

### Step 4. 读回校验

成功返回：`{"data": "<新rowid>", "success": true}`。校验要点：
- `success == true` 且 `data` 非空 = 成功。
- 报告给用户：新 rowid、写入的字段值。
- 若 `success != true` 或返回非 JSON，**不要声称成功**，把原始响应摊给用户。

## Resources

### scripts/worklog_api.py
核心脚本。子命令：`sign`（打印 appKey/sign）、`test-auth`（验证鉴权）、`list-projects`、
`list-employees`、`add-row`（写日志；项目经理带出默认关闭）、`delete-row`（删日志行；
需在「应用→授权管理」开通删除权限，否则 10005）。纯标准库，直接 `python` 跑，不装依赖。

### scripts/match_project.py
名称模糊匹配（纯标准库，员工、项目通用），输出 JSON 数组到 stdout。

### references/api_reference.md
完整 API 文档摘要：鉴权方式、addRow 参数、错误码、字段/时段对照、各类型 value 写法。

## Failure modes（要暴露，别吞）

| 症状 | 可能原因 | 处理 |
|---|---|---|
| `10001 Http Headers verification failed` | sign 传错/被当时间戳签名算了 | sign 必须 = SecretKey 值原样，勿再算 |
| `10005 数据操作无权限` | 授权没勾对应视图/权限，或 getFilterRows 没带 viewId | 带被授权的 viewId（见 Preconditions 第 4 步） |
| `10002 参数值错误` | 字段 value 类型/格式错 | 对照 api_reference.md 第 6 节 |
| 员工/项目关联字段报错 | rowid 不存在 | 重跑 list-employees/list-projects，或去 config.json 改 default_*_rowid/default_*_name |
| 时段被拒 | key 不在集合内 | 对照 config.shift_keys |
| `test-auth` 通过但 add-row 失败「缺少员工/项目参数」 | config 既没 default_*_rowid 也没 default_*_name，命令行也没传 | 给 config.json 填默认员工名（如「杨浪」），或在命令行传 --employee-name |
| 按名匹配报「找不到匹配项」 | config 或命令行的名字与档案不一致 | 去员工/项目档案表核对名字，或更新 config.default_*_name |
