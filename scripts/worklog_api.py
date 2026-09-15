#!/usr/bin/env python3
"""
明道云「工作表 API」工作日志写入工具（V2 开放接口，纯标准库，无第三方依赖）。

通过明道云 v2 开放 API（/v2/open/worksheet/*）向「工作日志」表插入/读取记录，
把「新增行记录 addRow」封装成命令行，供 AI（skill）在写工作日志时直接调用。

== 鉴权（关键，已实测验证） ==
明道云「应用授权」生成的 AppKey + SecretKey 中，那个「SecretKey」实际上是
一个**预生成的静态签名（Sign）**，调用接口时**直接原样当 sign 用**即可：
    - 无需计算签名
    - 无需拼接 AppKey/SecretKey/Timestamp
    - 无需传时间戳
请求体里：appKey=应用密钥，sign=SecretKey 值（原样）。
（注意：这与「组织密钥」不同——组织密钥才是 AppKey+SecretKey+Timestamp 做
SHA256 再 base64。应用密钥的 sign 就是那个值本身。）

== 字段值格式（已实测） ==
    - 文本（工作内容）：  value = "字符串"
    - 数值（工时）：      value = 2          （数字）
    - 日期（日期）：      value = "2026-09-09"
    - 单选（时段）：      value = "key"      （选项 key，字符串，非数组）
    - 关联（员工/项目）： value = "rowid"    （单条关联，字符串，非数组）

子命令：
    sign           打印鉴权信息（appKey + sign），供排查
    test-auth      发一次只读请求（getWorksheetInfo）验证鉴权是否通过
    list-projects  拉取「项目档案」表（rowid + 名称），供模糊匹配
    list-employees 拉取「员工档案」表（rowid + 姓名），供模糊匹配
    add-row        向工作日志表新增一条记录（员工、项目均为必填）
    delete-row     从工作日志表删除一条记录（撤回误写/清理测试数据）

项目经理带出（默认关闭）：
    2026-09-14 起默认不写「项目经理/项目经理用户」。原因：本部署有自动化会把日志的
    「员工」改写成项目经理值，疑似与写入项目经理字段相关。需要时加 --pm 单次开启，
    或在 config.json 设 "autofill_pm": true；--no-pm 可单次强制关闭。

用法示例：
    python worklog_api.py --config config.json test-auth
    python worklog_api.py --config config.json list-projects
    python worklog_api.py --config config.json list-employees
    python worklog_api.py --config config.json add-row \\
        --date 2026-09-04 --employee-rowid <员工rowid> --project-rowid <项目rowid> \\
        --content "开发2小时" --hours 2 --shift 全天
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# 让本脚本可直接 import 同目录的 match_project.py
sys.path.insert(0, str(Path(__file__).resolve().parent))
import match_project as mp  # noqa: E402

# 名称缓存目录（用户级，多个工具/junction 共用一份缓存）
_CACHE_DIR = Path.home() / ".workbuddy" / "cache" / "mingdao-worklog-api"
_EMPLOYEES_CACHE = _CACHE_DIR / "employees_full.json"
_PROJECTS_CACHE = _CACHE_DIR / "projects_full.json"


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(
            f"找不到配置文件：{path}\n"
            f"请先复制 config.example.json 为 config.json 并填入 appKey/secretKey。"
        )
    with path.open(encoding="utf-8") as f:
        cfg = json.load(f)
    required = ["appKey", "secretKey", "appId", "worklog_worksheet_id"]
    missing = [k for k in required if not cfg.get(k) or str(cfg[k]).startswith("在此填入")]
    if missing:
        raise SystemExit(
            f"config.json 缺少必要字段或仍是占位符：{missing}\n"
            f"请先复制 config.example.json 为 config.json 并填入 appKey/secretKey。"
        )
    return cfg


def _post(url: str, payload: dict[str, Any], timeout: int = 30) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return {"_http": e.code, "body": e.read().decode("utf-8", "replace")}
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {"_raw": body}


def _auth_body(cfg: dict[str, Any], worksheet_id: str, **extra: Any) -> dict[str, Any]:
    """构造带鉴权的请求体：appKey + sign(=secretKey 原样) + worksheetId。"""
    body = {
        "appKey": cfg["appKey"],
        "sign": cfg["secretKey"],  # 关键：sign 就是 SecretKey 值本身，无需计算
        "worksheetId": worksheet_id,
    }
    body.update(extra)
    return body


def _api_base(cfg: dict[str, Any]) -> str:
    return cfg.get("api_base", "https://api.mingdao.com").rstrip("/")


def cmd_sign(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    print(json.dumps({
        "appKey": cfg["appKey"],
        "sign": cfg["secretKey"],
        "note": "sign 即 SecretKey 值本身，直接使用，无需计算",
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_test_auth(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    url = f"{_api_base(cfg)}/v2/open/worksheet/getWorksheetInfo"
    resp = _post(url, _auth_body(cfg, cfg["worklog_worksheet_id"]))
    if resp.get("_http"):
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        return 1
    ok = bool(resp.get("success"))
    name = resp.get("data", {}).get("name", "?") if ok else ""
    print(json.dumps({"ok": ok, "worksheet_name": name, "response": resp}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


def _cmd_list_rows(cfg: dict[str, Any], worksheet_id: str, name_read_key: str,
                   view_id: str, page_size: int, label: str) -> int:
    if not worksheet_id or not name_read_key or not view_id:
        print(json.dumps({"ok": False, "error": f"{label}表的 worksheet_id/name_read_key/view_id 未在 config.json 配置"}, ensure_ascii=False))
        return 1
    url = f"{_api_base(cfg)}/v2/open/worksheet/getFilterRows"
    # 关键：明道云授权按「视图」粒度，getFilterRows 必须带被授权的 viewId，否则 10005
    resp = _post(url, _auth_body(cfg, worksheet_id, viewId=view_id, pageIndex=1, pageSize=page_size))
    if resp.get("_http"):
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        return 1
    if not resp.get("success"):
        code = resp.get("error_code")
        hint = ""
        if code == 10005:
            hint = ("（该视图无「获取行记录列表」权限。明道云授权按视图粒度，"
                    "请在【应用→授权管理】里为对应视图勾选读取权限；"
                    "不同视图返回的字段 key 可能不同——用别名还是 controlId，"
                    "需以 config.json 里的 *_name_read_key 为准）")
        print(json.dumps({"ok": False, "error_code": code, "error_msg": resp.get("error_msg"), "hint": hint}, ensure_ascii=False, indent=2))
        return 1
    rows = resp.get("data", {}).get("rows", [])
    out = []
    for r in rows:
        out.append({"rowid": r.get("rowid"), "name": r.get(name_read_key, "")})
    print(json.dumps({"ok": True, "count": len(out), "rows": out}, ensure_ascii=False, indent=2))
    return 0


def cmd_list_projects(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    items = _refresh_name_cache(cfg, "project", _PROJECTS_CACHE,
                                cfg.get("project_worksheet_id", ""),
                                cfg.get("project_name_read_key", ""),
                                cfg.get("project_view_id", ""),
                                args.page_size)
    if not items:
        return _cmd_list_rows(cfg, cfg.get("project_worksheet_id", ""),
                              cfg.get("project_name_read_key", ""),
                              cfg.get("project_view_id", ""), args.page_size, "项目档案")
    print(json.dumps({"ok": True, "count": len(items), "rows": items}, ensure_ascii=False, indent=2))
    print(f"(cache written: {_PROJECTS_CACHE}, {len(items)} rows)", file=sys.stderr)
    return 0


def cmd_list_employees(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    items = _refresh_name_cache(cfg, "employee", _EMPLOYEES_CACHE,
                                cfg.get("employee_worksheet_id", ""),
                                cfg.get("employee_name_read_key", ""),
                                cfg.get("employee_view_id", ""),
                                args.page_size)
    if not items:
        return _cmd_list_rows(cfg, cfg.get("employee_worksheet_id", ""),
                              cfg.get("employee_name_read_key", ""),
                              cfg.get("employee_view_id", ""), args.page_size, "员工档案")
    print(json.dumps({"ok": True, "count": len(items), "rows": items}, ensure_ascii=False, indent=2))
    print(f"(cache written: {_EMPLOYEES_CACHE}, {len(items)} rows)", file=sys.stderr)
    return 0


def _refresh_name_cache(cfg: dict[str, Any], label: str, cache_path: Path,
                        worksheet_id: str, name_read_key: str, view_id: str,
                        page_size: int) -> list[dict]:
    """从 API 拉一次列表并写到本地缓存；返回 [{rowid, name}, ...]。"""
    if not worksheet_id or not name_read_key or not view_id:
        return []
    url = f"{_api_base(cfg)}/v2/open/worksheet/getFilterRows"
    resp = _post(url, _auth_body(cfg, worksheet_id, viewId=view_id, pageIndex=1, pageSize=page_size))
    if not resp.get("success"):
        return []
    rows = resp.get("data", {}).get("rows", [])
    out = [{"rowid": r.get("rowid"), "name": r.get(name_read_key, "")} for r in rows]
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", encoding="utf-8") as f:
        json.dump({"ok": True, "count": len(out), "rows": out, "label": label}, f, ensure_ascii=False, indent=2)
    return out


def _load_name_cache(cache_path: Path) -> list[dict]:
    """从本地缓存读 [{rowid, name}, ...]，缓存不存在或解析失败返回空列表。"""
    if not cache_path.exists():
        return []
    try:
        with cache_path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    rows = data.get("rows") if isinstance(data, dict) else data
    return [{"rowid": r["rowid"], "name": r["name"]}
            for r in rows if isinstance(r, dict) and r.get("rowid") and r.get("name")]


def _ensure_employees_cache(cfg: dict[str, Any]) -> list[dict]:
    items = _load_name_cache(_EMPLOYEES_CACHE)
    if items:
        return items
    items = _refresh_name_cache(cfg, "employee", _EMPLOYEES_CACHE,
                                 cfg.get("employee_worksheet_id", ""),
                                 cfg.get("employee_name_read_key", ""),
                                 cfg.get("employee_view_id", ""),
                                 page_size=500)
    return items


def _ensure_projects_cache(cfg: dict[str, Any]) -> list[dict]:
    items = _load_name_cache(_PROJECTS_CACHE)
    if items:
        return items
    items = _refresh_name_cache(cfg, "project", _PROJECTS_CACHE,
                                 cfg.get("project_worksheet_id", ""),
                                 cfg.get("project_name_read_key", ""),
                                 cfg.get("project_view_id", ""),
                                 page_size=500)
    return items


def _match_one(items: list[dict], keyword: str, label: str) -> tuple[str, str]:
    """对员工/项目通用：返回 (rowid, matched_name)；找不到抛错。"""
    results = [r for r in mp.match(items, keyword, top=1) if r["score"] >= 70]
    if not results:
        top3 = [r["name"] for r in mp.match(items, keyword, top=3)]
        raise SystemExit(
            f"按 {label} 名 '{keyword}' 找不到匹配项。候选：{top3 if top3 else '（空）'}。"
            f"请去「{label}档案」表新建，或在 config.json 配置 default_{label}_rowid/default_{label}_name。"
        )
    return results[0]["rowid"], results[0]["name"]


def _resolve_employee(cfg: dict[str, Any], args: argparse.Namespace) -> tuple[str, str]:
    """按优先级解析员工 rowid：(1) --employee-rowid (2) --employee-name
    (3) config.default_employee_rowid (4) config.default_employee_name
    返回 (rowid, source_label)；失败抛错。
    """
    if getattr(args, "employee_rowid", None):
        return args.employee_rowid, "command_rowid"
    if getattr(args, "employee_name", None):
        items = _ensure_employees_cache(cfg)
        rowid, name = _match_one(items, args.employee_name, "员工")
        return rowid, f"command_name({name})"
    if cfg.get("default_employee_rowid"):
        return cfg["default_employee_rowid"], "config_rowid"
    if cfg.get("default_employee_name"):
        items = _ensure_employees_cache(cfg)
        rowid, name = _match_one(items, cfg["default_employee_name"], "员工")
        return rowid, f"config_name({name})"
    raise SystemExit(
        "缺少员工参数：请传 --employee-rowid 或 --employee-name，"
        "或在 config.json 里配置 default_employee_rowid / default_employee_name。"
    )


def _resolve_project(cfg: dict[str, Any], args: argparse.Namespace) -> tuple[str, str]:
    """按优先级解析项目 rowid：(1) --project-rowid (2) --project-name
    (3) config.default_project_rowid (4) config.default_project_name
    """
    if getattr(args, "project_rowid", None):
        return args.project_rowid, "command_rowid"
    if getattr(args, "project_name", None):
        items = _ensure_projects_cache(cfg)
        rowid, name = _match_one(items, args.project_name, "项目")
        return rowid, f"command_name({name})"
    if cfg.get("default_project_rowid"):
        return cfg["default_project_rowid"], "config_rowid"
    if cfg.get("default_project_name"):
        items = _ensure_projects_cache(cfg)
        rowid, name = _match_one(items, cfg["default_project_name"], "项目")
        return rowid, f"config_name({name})"
    raise SystemExit(
        "缺少项目参数：请传 --project-rowid 或 --project-name，"
        "或在 config.json 里配置 default_project_rowid / default_project_name。"
    )


def _lookup_employee_hap_account(cfg: dict[str, Any], employee_rowid: str) -> str:
    """通过 V3 单行接口读取员工档案，从「成员」/「外部账户」字段中拿 HAP accountId。

    内部员工的 HAP accountId 在字段「成员」（controlId 6938b7c20b2e62809471cb71）；
    外部员工的 accountId 在「外部账户」（controlId 69378a055326c71216b4a864），带 a# 前缀。
    返回第一个非空 accountId；都没有则返回 ""。
    """
    member_field = cfg.get("employee_member_control_id", "6938b7c20b2e62809471cb71")
    external_field = cfg.get("employee_external_control_id", "69378a055326c71216b4a864")
    ws = cfg.get("employee_worksheet_id", "")
    if not ws or not employee_rowid:
        return ""
    url = f"{_api_base(cfg)}/v3/app/worksheets/{ws}/rows/{employee_rowid}"
    req = urllib.request.Request(url, headers={"HAP-Appkey": cfg["appKey"], "HAP-Sign": cfg["secretKey"]})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode()).get("data", {})
    except (urllib.error.HTTPError, json.JSONDecodeError, KeyError):
        return ""
    for key in (member_field, external_field):
        items = data.get(key) or []
        if items:
            for it in items:
                acc = it.get("accountId") if isinstance(it, dict) else None
                if acc:
                    return acc
    return ""


def _lookup_project_pms(cfg: dict[str, Any], project_rowid: str) -> tuple[list[str], list[str]]:
    """反查项目档案，取项目经理。

    返回 (pm_rowids, pm_accountids)：
        - pm_rowids     「项目经理」关联字段里每项的 sid（= 员工档案 rowid），
                        用于填工作日志的「项目经理」（关联，单条取第一个）
        - pm_accountids 「项目经理（内部）」成员字段里每项的 accountId，
                        用于填工作日志的「项目经理用户」（成员，值=accountId 数组）
    任一环节失败/未配置都返回空列表，不阻断写日志。
    """
    pm_field = cfg.get("project_pm_control_id", "")
    pm_internal_field = cfg.get("project_pm_internal_control_id", "")
    ws = cfg.get("project_worksheet_id", "")
    if (not pm_field and not pm_internal_field) or not ws or not project_rowid:
        return [], []
    url = f"{_api_base(cfg)}/v3/app/worksheets/{ws}/rows/{project_rowid}"
    req = urllib.request.Request(url, headers={"HAP-Appkey": cfg["appKey"], "HAP-Sign": cfg["secretKey"]})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode()).get("data", {})
    except (urllib.error.HTTPError, json.JSONDecodeError, KeyError):
        return [], []
    pm_rowids = [it.get("sid") for it in (data.get(pm_field) or [])
                 if isinstance(it, dict) and it.get("sid")] if pm_field else []
    pm_accountids = [it.get("accountId") for it in (data.get(pm_internal_field) or [])
                     if isinstance(it, dict) and it.get("accountId")] if pm_internal_field else []
    return pm_rowids, pm_accountids


def cmd_add_row(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    fields = cfg["fields"]

    # 解析员工 / 项目（优先级：命令行 rowid > 命令行 name > config rowid > config name）
    employee_rowid, employee_source = _resolve_employee(cfg, args)
    project_rowid, project_source = _resolve_project(cfg, args)

    controls: list[dict[str, Any]] = []
    # 日期（Date，字符串）
    if args.date:
        controls.append({"controlId": fields["date"], "value": args.date})
    # 员工（单条关联，rowid 字符串）
    controls.append({"controlId": fields["employee"], "value": employee_rowid})
    # 项目（单条关联，rowid 字符串）
    controls.append({"controlId": fields["project"], "value": project_rowid})
    # 工作内容（文本）
    if args.content is not None:
        controls.append({"controlId": fields["content"], "value": args.content})
    # 工时（数字）
    if args.hours is not None:
        controls.append({"controlId": fields["hours"], "value": args.hours})
    # 时段（单选，key 字符串）
    if args.shift:
        shift_key = cfg.get("shift_keys", {}).get(args.shift, args.shift)
        controls.append({"controlId": fields["shift"], "value": shift_key})
    # 拥有者（HAP 系统字段 ownerid，value=HAP accountId 字符串）
    # 优先级：--owner-account-id > config.default_owner_account_id >
    #         自动按 employee_rowid 查员工档案（成员/外部账户字段）> 不写
    owner_id = args.owner_account_id or cfg.get("default_owner_account_id", "")
    owner_source = "command/config"
    if not owner_id and employee_rowid:
        owner_id = _lookup_employee_hap_account(cfg, employee_rowid)
        owner_source = "employee_profile"
    if owner_id:
        controls.append({"controlId": "ownerid", "value": owner_id})

    # 项目经理带出：默认关闭（2026-09-14）。本部署有自动化会把日志「员工」改写成
    # 项目经理值，疑似与写入项目经理字段相关；需要时 --pm 单次开启或 config autofill_pm=true。
    pm_note = ""
    pm_rowids: list[str] = []
    pm_accounts: list[str] = []
    pm_enabled = bool(cfg.get("autofill_pm", False))
    if args.pm:
        pm_enabled = True
    if args.no_pm:
        pm_enabled = False
    if pm_enabled:
        pm_control = cfg.get("worklog_pm_control_id", "")
        pm_user_control = cfg.get("worklog_pm_user_control_id", "")
        if pm_control or pm_user_control:
            pm_rowids, pm_accounts = _lookup_project_pms(cfg, project_rowid)
            if pm_control and pm_rowids:
                # 关联字段（单条）：value = rowid 字符串
                controls.append({"controlId": pm_control, "value": pm_rowids[0]})
            if pm_user_control and pm_accounts:
                # 成员字段：实测本部署 addRow 的成员控件只接受单个 accountId 字符串，
                # 数组会报 10001 JSON 解析错误；多经理项目取第一个
                controls.append({"controlId": pm_user_control, "value": pm_accounts[0]})
            if not pm_rowids and not pm_accounts:
                pm_note = "（项目未配置项目经理，未带出该字段）"

    url = f"{_api_base(cfg)}/v2/open/worksheet/addRow"
    payload = _auth_body(cfg, cfg["worklog_worksheet_id"], controls=controls,
                         triggerWorkflow=not args.no_workflow)

    if args.dry_run:
        # 脱敏后再打印：appKey/sign 属于凭证，绝不能进终端/对话
        masked = json.loads(json.dumps(payload))
        masked["sign"] = "***（已脱敏）***"
        masked["appKey"] = str(masked.get("appKey", ""))[:4] + "****"
        print("DRY-RUN（未真正发送）：")
        print(json.dumps({
            "url": url, "payload": masked,
            "_employee_source": employee_source,
            "_project_source": project_source,
            "_owner_source": owner_source,
            "_pm_rowids": pm_rowids,
            "_pm_accountids": pm_accounts,
            "_pm_note": pm_note,
        }, ensure_ascii=False, indent=2))
        return 0

    resp = _post(url, payload)
    if resp.get("_http"):
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        return 1

    ok = bool(resp.get("success"))
    print(json.dumps(resp, ensure_ascii=False, indent=2))
    if ok:
        owner_hint = f"，owner 来自{owner_source}={owner_id}" if owner_id else "（未设置 ownerid）"
        pm_hint = (f" | 项目经理={'/'.join(pm_rowids) or pm_note or '无'}"
                   if pm_enabled else " | 项目经理=未带出（默认关闭）")
        print(f"\n✓ 写入成功 rowid={resp.get('data')}", file=sys.stderr)
        print(f"  员工={employee_source} | 项目={project_source}{pm_hint}{owner_hint}", file=sys.stderr)
    else:
        print(f"\n✗ 写入失败（见上方响应）", file=sys.stderr)
    return 0 if ok else 1


def cmd_delete_row(args: argparse.Namespace) -> int:
    """删除工作日志行（按 rowid），用于撤回误写/清理测试数据。

    端点为 /v2/open/worksheet/deleteRow（单数，见 references/api_reference.md）。
    需要在「应用→授权管理」里给该授权开通删除权限，否则报 10005 数据操作无权限。
    """
    cfg = load_config(args.config)
    url = f"{_api_base(cfg)}/v2/open/worksheet/deleteRow"
    payload = _auth_body(cfg, cfg["worklog_worksheet_id"],
                         rowId=args.rowid, deleteType=args.delete_type)
    resp = _post(url, payload)
    if resp.get("_http"):
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        return 1
    ok = bool(resp.get("success"))
    print(json.dumps(resp, ensure_ascii=False, indent=2))
    hint = "" if ok else "（也可能是该应用授权未开通删除权限：明道云→应用→授权管理→勾选删除）"
    print(f"\n{'✓ 已删除' if ok else '✗ 删除失败'} rowid={args.rowid}{hint}",
          file=sys.stderr)
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parent.parent / "config.json",
                        help="config.json 路径（默认取 skill 目录下的 config.json）")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("sign", help="打印鉴权信息（appKey + sign）")
    sub.add_parser("test-auth", help="发只读请求验证鉴权与签名")

    p_proj = sub.add_parser("list-projects", help="拉取项目档案列表")
    p_proj.add_argument("--page-size", type=int, default=500)

    p_emp = sub.add_parser("list-employees", help="拉取员工档案列表")
    p_emp.add_argument("--page-size", type=int, default=500)

    p_add = sub.add_parser("add-row", help="新增一条工作日志")
    p_add.add_argument("--date", default=None, help="日期 YYYY-MM-DD（默认今天）")
    p_add.add_argument("--employee-rowid", default=None, help="员工 rowid（可选；优先于 --employee-name 和 config 默认）")
    p_add.add_argument("--employee-name", default=None, help="员工姓名，按名模糊匹配（可选）")
    p_add.add_argument("--project-rowid", default=None, help="项目 rowid（可选；优先于 --project-name 和 config 默认）")
    p_add.add_argument("--project-name", default=None, help="项目名，按名模糊匹配（可选）")
    p_add.add_argument("--content", default=None, help="工作内容文本")
    p_add.add_argument("--hours", type=float, default=None, help="工时（数字）")
    p_add.add_argument("--shift", default=None, help="时段：全天/上午/下午/其它")
    p_add.add_argument("--owner-account-id", default=None, help="拥有者（HAP accountId）。不传则取 config.json 的 default_owner_account_id；都没有则按员工档案自动查")
    p_add.add_argument("--no-pm", action="store_true", help="不自动带出项目经理（单次强制关闭）")
    p_add.add_argument("--pm", action="store_true", help="自动带出项目经理（单次开启；默认关闭）")
    p_add.add_argument("--no-workflow", action="store_true", help="不触发工作流")
    p_add.add_argument("--dry-run", action="store_true", help="只打印请求体，不发送")

    p_del = sub.add_parser("delete-row", help="从工作日志表删除一条记录（撤回误写/清理测试数据）")
    p_del.add_argument("rowid", help="要删除的行 rowid（add-row 成功时输出的 data）")
    p_del.add_argument("--delete-type", type=int, default=2, help="2=直接删除（默认），1=移入回收站")

    args = parser.parse_args(argv)

    handlers = {
        "sign": cmd_sign,
        "test-auth": cmd_test_auth,
        "list-projects": cmd_list_projects,
        "list-employees": cmd_list_employees,
        "add-row": cmd_add_row,
        "delete-row": cmd_delete_row,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
