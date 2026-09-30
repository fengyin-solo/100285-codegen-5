"""义务植树发苗业务规则。

权限按点位定死，不按"谁当天坐在这个点"放宽：
- 只有该点位的归属登记员能录发放；同点位出现第二个登记员时，以点位登记的归属登记员为准；
- 苗木管理员可以退回已发放记录，但必须写明缘由；
- 其他岗位（含轮换顶班的外点位登记员）对发放记录只能查阅。

数量口径与活动台账对齐：实发棵数必须等于台账应发棵数，否则发放不入账；
发放汇总恒等式为「台账应发 = 净发放 + 已退回 + 未发放」。
发放时把登记人姓名/班次快照进记录，人员轮换后原登记人仍可追溯。
同一份报名表（报名编号）重复提交发放只认第一次，即便第一次事后被退回也不重发。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

T_PERSON = "planting_person"
T_STATION = "planting_station"
T_ROSTER = "planting_roster"
T_LEDGER = "planting_ledger"
T_ISSUE = "planting_issue"

STATUS_ISSUED = "已发放"
STATUS_RETURNED = "已退回"

ROLE_REGISTRAR = "登记员"
ROLE_NURSERY = "苗木管理员"


class PlantingError(Exception):
    """发苗流程里可预期的驳回：带机器可读 code 与缺失权限说明。"""

    def __init__(self, code: str, message: str, missing_permission: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.missing_permission = missing_permission


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class PlantingService:
    # ---------- 基础名册 ----------
    def list_persons(self) -> list[dict[str, Any]]:
        return store.rows(T_PERSON)

    def list_stations(self) -> list[dict[str, Any]]:
        return store.rows(T_STATION)

    def list_roster(self, station_code: str | None = None) -> list[dict[str, Any]]:
        rows = store.rows(T_ROSTER)
        if station_code:
            rows = [row for row in rows if row.get("点位编号") == station_code]
        return rows

    def _find_person(self, operator_code: str) -> dict[str, Any] | None:
        code = (operator_code or "").strip()
        for row in store.rows(T_PERSON):
            if str(row.get("工号")) == code:
                return row
        return None

    def _find_station(self, station_code: str) -> dict[str, Any] | None:
        for row in store.rows(T_STATION):
            if str(row.get("点位编号")) == station_code:
                return row
        return None

    def _find_ledger(self, signup_code: str) -> dict[str, Any] | None:
        code = (signup_code or "").strip()
        for row in store.rows(T_LEDGER):
            if str(row.get("报名编号")) == code:
                return row
        return None

    def _first_issue(self, signup_code: str) -> dict[str, Any] | None:
        """同一报名编号只认第一条发放记录（含已退回），天然实现幂等。"""
        code = (signup_code or "").strip()
        for row in store.rows(T_ISSUE):
            if str(row.get("报名编号")) == code:
                return row
        return None

    # ---------- 活动台账 ----------
    def list_ledger(self, station_code: str | None = None) -> list[dict[str, Any]]:
        rows = store.rows(T_LEDGER)
        if station_code:
            rows = [row for row in rows if row.get("点位编号") == station_code]
        return rows

    # ---------- 发放记录 ----------
    def list_issues(
        self,
        *,
        station_code: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(T_ISSUE)
        if station_code:
            rows = [row for row in rows if row.get("点位编号") == station_code]
        if status:
            rows = [row for row in rows if row.get("状态") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_issue(self, record_id: int) -> dict[str, Any] | None:
        return store.find(T_ISSUE, record_id)

    def issue(
        self,
        *,
        signup_code: str,
        quantity: int | None,
        operator_code: str,
        shift: str | None = None,
    ) -> dict[str, Any]:
        """登记一次发苗。任一规则不满足都抛 PlantingError，当场驳回且不落任何数据。"""
        operator = self._find_person(operator_code)
        if operator is None:
            raise PlantingError(
                "OPERATOR_NOT_FOUND",
                f"工号 {operator_code} 不在本次义务植树岗位名册里，无法据此判定发苗权限",
            )

        # 规则1：只有登记员岗能录发放；苗木管理员及其他岗对发放只能查阅/退回。
        if operator.get("岗位") != ROLE_REGISTRAR:
            raise PlantingError(
                "ROLE_FORBIDDEN",
                f"{operator.get('姓名')} 的岗位是{operator.get('岗位')}，对发放记录只有查阅权限，不能登记发放",
                missing_permission="发放登记（登记员岗）",
            )

        ledger = self._find_ledger(signup_code)
        if ledger is None:
            raise PlantingError(
                "LEDGER_NOT_FOUND",
                f"报名编号 {signup_code} 不在本次活动台账里，没有应发棵数依据，发放未登记",
            )

        station_code = str(ledger.get("点位编号"))
        station = self._find_station(station_code)
        owner_code = str(station.get("归属登记员工号")) if station else ""
        owner_name = station.get("归属登记员姓名") if station else ""

        # 规则2：权限按点位定死——只认点位登记的归属登记员，不认当天顶班的人。
        if str(operator.get("工号")) != owner_code:
            target_perm = f"{station_code} {ledger.get('点位名称')}本点位发放登记"
            own_station = operator.get("本点位编号")
            if own_station == station_code:
                # 同一个点位挂了两名登记员：冲突时以归属登记员为准。
                raise PlantingError(
                    "NOT_OWN_STATION_REGISTRAR",
                    f"{station_code} 点位登记的归属登记员是{owner_name}，同点位登记冲突时以其为准；"
                    f"{operator.get('姓名')}无权录入该点位发放，发放已当场驳回",
                    missing_permission=f"{target_perm}（归属登记员：{owner_name}）",
                )
            own_label = f"{own_station} 点位" if own_station else "无固定点位"
            raise PlantingError(
                "STATION_MISMATCH",
                f"{operator.get('姓名')}是{own_label}的登记员，不能替 {station_code} "
                f"{ledger.get('点位名称')}登记发放；该点位以归属登记员{owner_name}为准，发放已当场驳回",
                missing_permission=target_perm,
            )

        # 规则3：同一份报名表重复提交，只认第一次（含第一次已被退回的情况）。
        existing = self._first_issue(signup_code)
        if existing is not None:
            tip = f"首次由{existing.get('登记人姓名')}于{existing.get('发放时间')}发放{existing.get('发放棵数')}棵"
            if existing.get("状态") == STATUS_RETURNED:
                tip += f"，该首次记录已被{existing.get('退回人姓名')}退回（缘由：{existing.get('退回缘由')}）"
            raise PlantingError(
                "ALREADY_ISSUED",
                f"报名编号 {signup_code} 已存在发放记录，{tip}；重复提交只认第一次，本次未入账",
            )

        # 规则4：实发棵数必须与活动台账应发棵数对得上，否则不入账。
        expected = int(ledger.get("应发棵数", 0))
        if quantity is None or int(quantity) != expected:
            actual = "未填" if quantity is None else f"{quantity} 棵"
            raise PlantingError(
                "QUANTITY_MISMATCH",
                f"报名编号 {signup_code} 活动台账应发 {expected} 棵，本次实发 {actual}，"
                f"数量对不上，发放未入账",
            )

        rows = store.rows(T_ISSUE)
        record = {
            "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1,
            "报名编号": ledger.get("报名编号"),
            "点位编号": station_code,
            "点位名称": ledger.get("点位名称"),
            "报名单位": ledger.get("报名单位"),
            "树种": ledger.get("树种"),
            "发放棵数": expected,
            "台账应发": expected,
            "状态": STATUS_ISSUED,
            "status": STATUS_ISSUED,
            # 人员快照：轮换后这条记录仍标出原登记人。
            "登记员工号": operator.get("工号"),
            "登记人姓名": operator.get("姓名"),
            "班次": (shift or "").strip() or None,
            "发放时间": _now(),
            "退回人姓名": None,
            "退回缘由": None,
            "退回时间": None,
            "pending": False,
            "abnormal": False,
        }
        rows.append(record)
        return record

    def return_record(
        self,
        record_id: int,
        reason: str,
        *,
        operator_code: str,
    ) -> dict[str, Any]:
        """苗木管理员退回一条已发放记录；其他岗位（含登记员）只能查阅，不能退回。"""
        operator = self._find_person(operator_code)
        if operator is None:
            raise PlantingError(
                "OPERATOR_NOT_FOUND",
                f"工号 {operator_code} 不在本次义务植树岗位名册里，无法据此判定退回权限",
            )
        if operator.get("岗位") != ROLE_NURSERY:
            raise PlantingError(
                "ROLE_FORBIDDEN",
                f"{operator.get('姓名')} 的岗位是{operator.get('岗位')}，对已发放记录只能查阅，不能退回",
                missing_permission="发放退回（苗木管理员）",
            )

        record = store.find(T_ISSUE, record_id)
        if record is None:
            raise PlantingError("RECORD_NOT_FOUND", f"发放记录 {record_id} 不存在，无法退回")
        if record.get("状态") == STATUS_RETURNED:
            raise PlantingError(
                "ALREADY_RETURNED",
                f"发放记录 {record_id} 已退回，不能重复退回",
            )

        reason_text = (reason or "").strip()
        if not reason_text:
            raise PlantingError("REASON_REQUIRED", "退回必须写明缘由，不能为空")

        record["状态"] = STATUS_RETURNED
        record["status"] = STATUS_RETURNED
        record["退回人姓名"] = operator.get("姓名")
        record["退回缘由"] = reason_text
        record["退回时间"] = _now()
        # 退回意味着该报名单位的苗没有真正落地，列入待处理并标异常，提醒补发/核对。
        record["pending"] = True
        record["abnormal"] = True
        return record

    # ---------- 发放汇总对账 ----------
    def summary(self, station_code: str | None = None) -> dict[str, Any]:
        """以活动台账为基准，逐条核对应发/净发/退回/未发，保证汇总苗木数与台账对得上。"""
        ledger_rows = self.list_ledger(station_code)
        details: list[dict[str, Any]] = []
        checks: list[str] = []

        totals = {"报名单位数": 0, "台账应发": 0, "净发放": 0, "已退回": 0, "未发放": 0, "退回笔数": 0}
        by_station: dict[str, dict[str, Any]] = {}

        for ledger in ledger_rows:
            issue = self._first_issue(str(ledger.get("报名编号")))
            expected = int(ledger.get("应发棵数", 0))
            issued = returned = outstanding = 0
            status = "未发放"
            registrar: str | None = None
            issued_at: str | None = None
            return_reason: str | None = None

            if issue is not None:
                qty = int(issue.get("发放棵数", 0))
                registrar = issue.get("登记人姓名")
                issued_at = issue.get("发放时间")
                if issue.get("状态") == STATUS_ISSUED:
                    issued = qty
                    status = STATUS_ISSUED
                else:
                    # 已退回：苗退回可重领，其"未在栽"由"已退回"承担，不再重复计入"未发放"；
                    # "未发放"只给从未出过发放记录的台账，保证三分类互斥、汇总与台账对得上。
                    returned = qty
                    outstanding = 0
                    status = STATUS_RETURNED
                    totals["退回笔数"] += 1
                    return_reason = issue.get("退回缘由")
            else:
                outstanding = expected

            net = issued
            row_ok = expected == net + returned + outstanding
            if not row_ok:
                checks.append(
                    f"报名编号 {ledger.get('报名编号')}：台账应发 {expected} ≠ 净发放 {net} + "
                    f"已退回 {returned} + 未发放 {outstanding}"
                )
            if issue is not None and int(issue.get("发放棵数", 0)) != expected:
                checks.append(
                    f"报名编号 {ledger.get('报名编号')}：发放棵数 {issue.get('发放棵数')} "
                    f"与台账应发 {expected} 不符"
                )

            details.append({
                "报名编号": ledger.get("报名编号"),
                "点位编号": ledger.get("点位编号"),
                "点位名称": ledger.get("点位名称"),
                "报名单位": ledger.get("报名单位"),
                "树种": ledger.get("树种"),
                "台账应发": expected,
                "净发放": net,
                "已退回": returned,
                "未发放": outstanding,
                "状态": status,
                "原登记人": registrar,
                "发放时间": issued_at,
                "退回缘由": return_reason,
                "对账": "平" if row_ok else "不平",
            })

            totals["报名单位数"] += 1
            totals["台账应发"] += expected
            totals["净发放"] += net
            totals["已退回"] += returned
            totals["未发放"] += outstanding

            bucket = by_station.setdefault(
                str(ledger.get("点位编号")),
                {"点位编号": ledger.get("点位编号"), "点位名称": ledger.get("点位名称"),
                 "台账应发": 0, "净发放": 0, "已退回": 0, "未发放": 0, "报名单位数": 0},
            )
            bucket["报名单位数"] += 1
            bucket["台账应发"] += expected
            bucket["净发放"] += net
            bucket["已退回"] += returned
            bucket["未发放"] += outstanding

        equation_ok = totals["台账应发"] == totals["净发放"] + totals["已退回"] + totals["未发放"]
        consistent = equation_ok and not checks

        return {
            "筛选点位": station_code or "全部点位",
            "totals": totals,
            "by_station": list(by_station.values()),
            "equation": "台账应发 = 净发放 + 已退回 + 未发放",
            "equation_ok": equation_ok,
            "consistent": consistent,
            "checks": checks,
            "items": details,
        }
