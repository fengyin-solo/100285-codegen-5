"""义务植树发苗接口。

发苗权限按点位定死，接口层只负责参数与身份透传，判定全部在 PlantingService；
权限/数量/重复提交等可预期驳回会被翻译成带 code 与 missing_permission 的错误体，
前端据此"当场驳回并点出缺哪项权限"。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, IssueSeedlingsPayload, PageResult, ReturnSeedlingsPayload
from app.services.planting import PlantingError, PlantingService

router = APIRouter(prefix="/api/planting", tags=["义务植树发苗"])

service = PlantingService()

# 权限类驳回用 403；数据不存在 404；重复/数量冲突 409/422
_FORBIDDEN_CODES = {"ROLE_FORBIDDEN", "NOT_OWN_STATION_REGISTRAR", "STATION_MISMATCH"}
_NOT_FOUND_CODES = {"OPERATOR_NOT_FOUND", "LEDGER_NOT_FOUND", "RECORD_NOT_FOUND"}
_CONFLICT_CODES = {"ALREADY_ISSUED", "ALREADY_RETURNED"}


def _raise(err: PlantingError) -> None:
    if err.code in _FORBIDDEN_CODES:
        status = 403
    elif err.code in _NOT_FOUND_CODES:
        status = 404
    elif err.code in _CONFLICT_CODES:
        status = 409
    else:  # QUANTITY_MISMATCH / REASON_REQUIRED
        status = 422
    detail: dict[str, Any] = {"message": err.message, "code": err.code}
    if err.missing_permission:
        detail["missing_permission"] = err.missing_permission
    raise HTTPException(status_code=status, detail=detail)


@router.get("/me")
def current_operator(operator_code: str = Query(..., description="当前在岗人员工号")) -> dict[str, Any]:
    """根据工号回显当前岗位与其本点位，前端据此控制可点的动作。"""
    operator = service._find_person(operator_code)
    if operator is None:
        raise HTTPException(
            status_code=404,
            detail={"message": f"工号 {operator_code} 不在岗位名册里", "code": "OPERATOR_NOT_FOUND"},
        )
    return operator


@router.get("/persons")
def list_persons() -> dict[str, Any]:
    """岗位名册：登记员、苗木管理员、其他岗各是谁。"""
    return {"items": service.list_persons()}


@router.get("/stations")
def list_stations() -> dict[str, Any]:
    """植树点位及其唯一归属登记员。"""
    return {"items": service.list_stations()}


@router.get("/roster")
def list_roster(
    station_code: str | None = Query(default=None, description="按点位过滤排班"),
) -> dict[str, Any]:
    """当天排班与轮换：标明每个班次坐在点位上的人是不是归属登记员。"""
    return {"items": service.list_roster(station_code)}


@router.get("/ledger")
def list_ledger(
    station_code: str | None = Query(default=None, description="按点位过滤活动台账"),
) -> dict[str, Any]:
    """活动报名台账：每条报名的点位、单位、树种、应发棵数，是发苗与对账的基准。"""
    return {"items": service.list_ledger(station_code)}


@router.get("/issues", response_model=PageResult[dict])
def list_issues(
    station_code: str | None = Query(default=None, description="按点位过滤"),
    status: str | None = Query(default=None, description="已发放 / 已退回"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """发放记录列表；任何岗位都可查阅，记录里始终保留原登记人快照。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_issues(station_code=station_code, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/issues/{record_id}", response_model=dict)
def get_issue(record_id: int) -> dict[str, Any]:
    record = service.get_issue(record_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={"message": f"发放记录 {record_id} 不存在", "code": "RECORD_NOT_FOUND"},
        )
    return record


@router.post("/issues", response_model=ActionResult, status_code=201)
def issue_seedlings(
    payload: IssueSeedlingsPayload,
    operator_code: str = Query(..., description="当前登记员工号"),
    shift: str | None = Query(default=None, description="当前班次，如 A/B，随记录留痕"),
) -> ActionResult:
    """登记发放：只认点位归属登记员，数量须等于台账，重复报名表只认第一次。"""
    try:
        record = service.issue(
            signup_code=payload.signup_code,
            quantity=payload.quantity,
            operator_code=operator_code,
            shift=shift,
        )
    except PlantingError as err:
        _raise(err)
        raise  # pragma: no cover - _raise 必抛
    return ActionResult(
        ok=True,
        message=f"已为报名编号 {record['报名编号']} 发放 {record['发放棵数']} 棵，"
                f"登记人 {record['登记人姓名']}（{record['点位名称']}）",
        entry=record,
    )


@router.post("/issues/{record_id}/return", response_model=ActionResult)
def return_seedlings(
    record_id: int,
    payload: ReturnSeedlingsPayload,
    operator_code: str = Query(..., description="操作人工号，须为苗木管理员"),
) -> ActionResult:
    """苗木管理员退回已发放记录并写明缘由；其他岗只能查阅，调用即被驳回。"""
    try:
        record = service.return_record(record_id, payload.reason, operator_code=operator_code)
    except PlantingError as err:
        _raise(err)
        raise  # pragma: no cover - _raise 必抛
    return ActionResult(
        ok=True,
        message=f"发放记录 {record_id} 已由苗木管理员{record['退回人姓名']}退回，"
                f"缘由：{record['退回缘由']}",
        entry=record,
    )


@router.get("/summary")
def summary(
    station_code: str | None = Query(default=None, description="按点位过滤；不传则全部点位"),
) -> dict[str, Any]:
    """发放汇总对账：以活动台账为基准核对应发/净发/退回/未发，平账才 consistent=true。"""
    return service.summary(station_code)
