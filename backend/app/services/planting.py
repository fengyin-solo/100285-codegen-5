"""义务植树发苗业务规则。

权限按点位定死，所有判断都集中在本文件，路由层只负责取参与回包：

1. 只有本点位现任登记员能录发放；替别的点位登记当场驳回，并点出缺哪项权限。
2. 苗木管理员可退回已发放记录且必须写明缘由；其他岗对已发放记录只能查阅。
3. 人员轮换只更新点位现任登记员，已形成的发放记录始终标出原登记人。
4. 同一份报名表（报名编号）重复提交发放只认第一次，后续一律驳回。
5. 发放汇总里的苗木数实时按已发放记录累计，并与活动台账逐行对账。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

STAFF = "planting_staff"
POINTS = "planting_points"
LEDGER = "planting_ledger"
SIGNUPS = "planting_signups"
ISSUES = "planting_issues"

REGISTRAR_ROLE = "点位登记员"
MANAGER_ROLE = "苗木管理员"

ISSUE_ACTIVE = "已发放"
ISSUE_RETURNED = "已退回"

PERM_ISSUE = "发苗登记：本点位现任登记员"
PERM_RETURN = "发苗退回：苗木管理员"
PERM_VIEW = "发苗查阅：全部岗位"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _find_staff(staff_id: int) -> dict[str, Any] | None:
    return store.find(STAFF, staff_id)


def _find_point_by_code(point_code: str) -> dict[str, Any] | None:
    for point in store.rows(POINTS):
        if point.get("点位编号") == point_code:
            return point
    return None


class PlantingService:
    # ---------- 基础查阅 ----------
    def list_staff(self) -> list[dict[str, Any]]:
        return store.rows(STAFF)

    def list_points(self) -> list[dict[str, Any]]:
        return store.rows(POINTS)

    def list_signups(
        self,
        *,
        point_code: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(SIGNUPS)
        if point_code:
            rows = [row for row in rows if row.get("点位编号") == point_code]
        if status:
            rows = [row for row in rows if row.get("状态") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def list_issues(
        self,
        *,
        point_code: str | None = None,
        signup_no: str | None = None,
    ) -> list[dict[str, Any]]:
        """发放记录任何岗位都可查阅，返回顺序按录入时间倒序。"""
        rows = store.rows(ISSUES)
        if point_code:
            rows = [row for row in rows if row.get("点位编号") == point_code]
        if signup_no:
            rows = [row for row in rows if row.get("报名编号") == signup_no]
        return sorted(rows, key=lambda row: int(row.get("id", 0)), reverse=True)

    # ---------- 权限 ----------
    def current_operator(self, staff_id: int) -> dict[str, Any]:
        """给前端顶栏用：返回当前操作者及其在发苗环节的权限清单。"""
        staff = _find_staff(staff_id)
        if staff is None:
            return {
                "staff_id": staff_id,
                "姓名": "未知人员",
                "岗位": "无岗位",
                "所属点位": "",
                "permissions": [PERM_VIEW],
            }
        permissions = [PERM_VIEW]
        is_current_registrar = (
            staff.get("岗位") == REGISTRAR_ROLE
            and staff.get("在职")
            and any(point.get("现任登记员ID") == staff["id"] for point in store.rows(POINTS))
        )
        if is_current_registrar:
            permissions.append(PERM_ISSUE)
        if staff.get("岗位") == MANAGER_ROLE:
            permissions.append(PERM_RETURN)
        return {
            "staff_id": staff["id"],
            "姓名": staff.get("姓名"),
            "岗位": staff.get("岗位"),
            "所属点位": staff.get("所属点位", ""),
            "permissions": permissions,
        }

    def _denied(self, message: str, missing_perm: str = PERM_ISSUE) -> tuple[None, str, str]:
        """统一的驳回出口：消息里点出缺哪项权限，并带上所需权限码。"""
        return None, message, missing_perm

    # ---------- 录发放 ----------
    def issue(
        self, staff_id: int, signup_no: str, count: int | None
    ) -> tuple[dict[str, Any] | None, str, str]:
        """录一条发放记录。

        返回 (记录或None, 消息, 缺少的权限)；缺权限时第三项给出权限名称。
        校验顺序：本人在岗与岗位 → 报名表 → 是否首次提交 → 点位归属与现任 → 数量与台账额度。
        """
        staff = _find_staff(staff_id)
        if staff is None or not staff.get("在职"):
            return self._denied(
                f"当前登录人员（工号 {staff_id}）不在岗，无法录发放；需要权限「{PERM_ISSUE}」。",
                PERM_ISSUE,
            )
        if staff.get("岗位") != REGISTRAR_ROLE:
            if staff.get("岗位") == MANAGER_ROLE:
                return self._denied(
                    f"苗木管理员{staff.get('姓名')}只能退回发放，不能录发放；"
                    f"缺少权限「{PERM_ISSUE}」，请交由该点位现任登记员操作。",
                    PERM_ISSUE,
                )
            return self._denied(
                f"{staff.get('岗位')}{staff.get('姓名')}对发放记录只有查阅权，"
                f"缺少权限「{PERM_ISSUE}」。",
                PERM_ISSUE,
            )

        signup = self._find_signup(signup_no)
        if signup is None:
            return self._denied(f"报名表 {signup_no} 不存在，请核对报名编号。", "")

        target_point = signup.get("点位编号")
        own_point = staff.get("所属点位")
        point = _find_point_by_code(target_point)

        # 同一份报名表重复提交发放只认第一次：只要首条记录已存在，
        # 无论提交人是不是现任，都先按重复提交驳回，避免换个人再交就重开。
        existing = self._find_issue(signup_no)
        if existing is not None:
            first_by = existing.get("登记人姓名")
            if existing.get("状态") == ISSUE_RETURNED:
                reason = existing.get("退回缘由") or ""
                return self._denied(
                    f"报名表 {signup_no} 的发放已由{first_by}登记并被苗木管理员退回"
                    f"（缘由：{reason}）；首次发放记录保留、只认第一次，不能重复发放。",
                    "",
                )
            return self._denied(
                f"报名表 {signup_no} 已由{first_by}于{existing.get('发放时间')}发放"
                f"{existing.get('发放棵数')}棵；同一份报名表重复提交只认第一次。",
                "",
            )

        # 点位权限：只有本点位的登记员能录，跨点位当场驳回并点出缺哪项权限。
        if own_point != target_point:
            point_name = point.get("点位名称") if point else target_point
            current = point.get("现任登记员姓名") if point else "该点位现任登记员"
            return self._denied(
                f"当场驳回：{staff.get('姓名')}是{own_point or '其他点位'}的登记员，"
                f"无权替{point_name}（{target_point}）录发放；"
                f"缺少权限「{PERM_ISSUE} · {point_name}」，该点位以现任登记员{current}为准。",
                f"{PERM_ISSUE} · {point_name}",
            )

        # 同一个点位两个登记员冲突（现任与协助登记员、轮换前后任同时操作）时以现任为准：
        if point and point.get("现任登记员ID") != staff["id"]:
            return self._denied(
                f"当场驳回：{target_point} 现任登记员为{point.get('现任登记员姓名')}，"
                f"同一点位登记意见冲突时以现任登记员为准；缺少权限"
                f"「{PERM_ISSUE} · {point.get('点位名称')}现任登记员」。",
                f"{PERM_ISSUE} · {point.get('点位名称')}现任登记员",
            )

        qty = signup.get("拟领棵数")
        if count is None:
            count = int(qty)
        if not isinstance(count, int) or count <= 0:
            return self._denied("发放棵数必须是大于 0 的整数。", "")

        # 台账额度：本点位本树种累计已发 + 本次不得超过计划苗数
        ledger = self._find_ledger(target_point, signup.get("树种"))
        if ledger is None:
            return self._denied(
                f"活动台账缺少 {target_point} · {signup.get('树种')} 的计划行，"
                f"无法对账，暂不能发放。",
                "",
            )
        if count > int(qty):
            return self._denied(
                f"本次 {count} 棵超出报名表 {signup_no} 的拟领棵数 {qty} 棵。", ""
            )
        issued = int(ledger.get("已发苗数", 0))
        planned = int(ledger.get("计划苗数", 0))
        if issued + count > planned:
            return self._denied(
                f"{target_point} · {signup.get('树种')} 台账计划 {planned} 棵、"
                f"已发 {issued} 棵，再发 {count} 棵将超发（缺苗 {issued + count - planned} 棵），"
                f"与活动台账对不上，发放被拦下。",
                "",
            )

        rows = store.rows(ISSUES)
        entry = {
            "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1,
            "报名编号": signup_no,
            "点位编号": target_point,
            "点位名称": (_find_point_by_code(target_point) or {}).get("点位名称", target_point),
            "报名人": signup.get("报名人"),
            "树种": signup.get("树种"),
            "发放棵数": count,
            "登记人ID": staff["id"],
            "登记人姓名": staff.get("姓名"),
            "发放时间": _now(),
            "状态": ISSUE_ACTIVE,
            "退回缘由": "",
            "退回人": "",
            "退回时间": "",
        }
        rows.append(entry)
        signup["状态"] = ISSUE_ACTIVE
        ledger["已发苗数"] = issued + count
        return entry, f"已为报名表 {signup_no} 发放 {count} 棵{signup.get('树种')}", ""

    # ---------- 退回 ----------
    def return_issue(
        self, staff_id: int, issue_id: int, reason: str
    ) -> tuple[dict[str, Any] | None, str]:
        staff = _find_staff(staff_id)
        if staff is None or staff.get("岗位") != MANAGER_ROLE:
            who = staff.get("姓名") if staff else f"工号{staff_id}"
            role = staff.get("岗位", "无岗位") if staff else "无岗位"
            return None, (
                f"当场驳回：{role}{who}没有退回权限；"
                f"缺少权限「{PERM_RETURN}」，只有苗木管理员可以退回发放记录。"
            )
        reason = (reason or "").strip()
        if not reason:
            return None, "退回必须写明缘由，苗木管理员请补充退回原因后再提交。"
        entry = store.find(ISSUES, issue_id)
        if entry is None:
            return None, f"发放记录 {issue_id} 不存在或已归档。"
        if entry.get("状态") != ISSUE_ACTIVE:
            return None, f"发放记录 {issue_id} 已是「{entry.get('状态')}」状态，不能重复退回。"

        entry["状态"] = ISSUE_RETURNED
        entry["退回缘由"] = reason
        entry["退回人"] = staff.get("姓名")
        entry["退回时间"] = _now()
        # 原登记人字段保持不动，轮换后也能追溯
        signup = self._find_signup(entry.get("报名编号"))
        if signup is not None:
            signup["状态"] = ISSUE_RETURNED
        ledger = self._find_ledger(entry.get("点位编号"), entry.get("树种"))
        if ledger is not None:
            ledger["已发苗数"] = max(0, int(ledger.get("已发苗数", 0)) - int(entry["发放棵数"]))
        return entry, f"已退回 {entry.get('报名编号')} 的发放并登记缘由，台账已冲减。"

    # ---------- 人员轮换 ----------
    def rotate(self, point_code: str, new_staff_id: int) -> tuple[dict[str, Any] | None, str]:
        """轮换某点位的现任登记员；历史发放记录上的原登记人不改。"""
        point = _find_point_by_code(point_code)
        if point is None:
            return None, f"点位 {point_code} 不存在。"
        new_staff = _find_staff(new_staff_id)
        if new_staff is None:
            return None, f"新登记员（工号 {new_staff_id}）不存在。"
        if new_staff.get("岗位") != REGISTRAR_ROLE:
            return None, f"{new_staff.get('姓名')}不是点位登记员，不能接任 {point_code}。"
        if new_staff.get("所属点位") not in ("", point_code):
            return None, (
                f"{new_staff.get('姓名')}仍挂在{new_staff.get('所属点位')}，"
                f"不能跨点位接任 {point_code}。"
            )
        previous_id = point.get("现任登记员ID")
        previous = _find_staff(int(previous_id)) if previous_id else None
        if previous is not None and previous.get("id") != new_staff["id"]:
            previous["所属点位"] = ""
            previous["在职"] = False
            previous["说明"] = f"{point.get('点位名称')}原登记员，已轮换离岗"
        point["现任登记员ID"] = new_staff["id"]
        point["现任登记员姓名"] = new_staff.get("姓名")
        new_staff["所属点位"] = point_code
        new_staff["在职"] = True
        return point, (
            f"{point.get('点位名称')}（{point_code}）登记员已轮换为{new_staff.get('姓名')}；"
            f"历史发放记录仍标出原登记人{previous.get('姓名') if previous else '—'}。"
        )

    # ---------- 汇总对账 ----------
    def summary(self) -> dict[str, Any]:
        """按点位汇总发放，并逐行与活动台账对账。

        已发口径只统计状态为「已发放」的记录（退回的不计），
        汇总苗数与台账已发苗数必须一致，不一致的行标记为对账异常。
        """
        issues = [row for row in store.rows(ISSUES) if row.get("状态") == ISSUE_ACTIVE]
        by_point: dict[str, dict[str, int]] = {}
        for row in issues:
            point_map = by_point.setdefault(row["点位编号"], {})
            point_map[str(row["树种"])] = point_map.get(str(row["树种"]), 0) + int(row["发放棵数"])

        lines: list[dict[str, Any]] = []
        for ledger in store.rows(LEDGER):
            code = ledger["点位编号"]
            tree = ledger["树种"]
            counted = by_point.get(code, {}).get(tree, 0)
            planned = int(ledger["计划苗数"])
            booked = int(ledger["已发苗数"])
            lines.append({
                "点位编号": code,
                "点位名称": (_find_point_by_code(code) or {}).get("点位名称", code),
                "树种": tree,
                "计划苗数": planned,
                "台账已发苗数": booked,
                "汇总已发苗数": counted,
                "剩余苗数": planned - counted,
                "对账一致": counted == booked,
            })

        point_rows: list[dict[str, Any]] = []
        for point in store.rows(POINTS):
            code = point["点位编号"]
            code_lines = [line for line in lines if line["点位编号"] == code]
            point_rows.append({
                "点位编号": code,
                "点位名称": point["点位名称"],
                "现任登记员": point["现任登记员姓名"],
                "计划合计": sum(line["计划苗数"] for line in code_lines),
                "已发合计": sum(line["汇总已发苗数"] for line in code_lines),
                "缺苗数": sum(max(0, line["计划苗数"] - line["汇总已发苗数"]) for line in code_lines),
                "对账一致": all(line["对账一致"] for line in code_lines),
            })

        all_consistent = all(line["对账一致"] for line in lines)
        return {
            "reconciled": all_consistent,
            "message": "发放汇总与活动台账已对齐。" if all_consistent else "发放汇总与活动台账存在不一致，请核对异常行。",
            "points": point_rows,
            "ledger_lines": lines,
            "issue_count": len(issues),
        }

    # ---------- 内部查找 ----------
    def _find_signup(self, signup_no: str) -> dict[str, Any] | None:
        for row in store.rows(SIGNUPS):
            if row.get("报名编号") == signup_no:
                return row
        return None

    def _find_issue(self, signup_no: str) -> dict[str, Any] | None:
        for row in store.rows(ISSUES):
            if row.get("报名编号") == signup_no:
                return row
        return None

    def _find_ledger(self, point_code: str, tree: Any) -> dict[str, Any] | None:
        for row in store.rows(LEDGER):
            if row.get("点位编号") == point_code and row.get("树种") == tree:
                return row
        return None
