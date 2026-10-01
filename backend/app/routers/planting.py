"""义务植树发苗接口：报名发放、退回、人员轮换与汇总对账。

当前操作者通过请求头 X-Staff-Id 传入（前端顶栏切换岗位）；
业务判断全部在 PlantingService，路由层不做权限裁决。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel

from app.schemas import ActionResult, PageResult
from app.services.planting import PERM_VIEW, PlantingService

router = APIRouter(prefix="/api/planting", tags=["义务植树发苗"])

service = PlantingService()


class IssueBody(BaseModel):
    signup_no: str
    count: int | None = None


class ReturnBody(BaseModel):
    reason: str = ""


class RotateBody(BaseModel):
    point_code: str
    new_staff_id: int


@router.get("/me")
def me(x_staff_id: int = Header(default=0, alias="X-Staff-Id")) -> dict[str, Any]:
    """当前操作者及其在发苗环节的权限清单。"""
    return service.current_operator(x_staff_id)


@router.get("/staff")
def list_staff() -> dict[str, Any]:
    """岗位与人员清单，供前端切换身份、演示权限驳回。"""
    return {"items": service.list_staff()}


@router.get("/points")
def list_points() -> dict[str, Any]:
    """点位与其现任登记员。"""
    return {"items": service.list_points()}


@router.get("/signups", response_model=PageResult[dict])
def list_signups(
    point_code: str | None = Query(default=None, description="按点位编号过滤"),
    status: str | None = Query(default=None, description="待发放、已发放、已退回"),
    page: int = 1,
    size: int = 100,
) -> PageResult[dict]:
    """报名表列表：发放对象入口，任何岗位都可查阅。"""
    items, total = service.list_signups(point_code=point_code, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/issues")
def list_issues(
    point_code: str | None = Query(default=None),
    signup_no: str | None = Query(default=None),
) -> dict[str, Any]:
    """已发放记录：所有岗位只读查看（{perm}）。""".format(perm=PERM_VIEW)
    return {"items": service.list_issues(point_code=point_code, signup_no=signup_no)}


@router.post("/issues", response_model=ActionResult)
def create_issue(
    body: IssueBody,
    x_staff_id: int = Header(default=0, alias="X-Staff-Id"),
) -> ActionResult:
    """录发放：仅本点位现任登记员可操作；跨点位、越权、重复提交都会当场驳回。"""
    entry, message, missing_perm = service.issue(x_staff_id, body.signup_no.strip(), body.count)
    if entry is None:
        return ActionResult(
            ok=False,
            message=message,
            entry={"missing_permission": missing_perm} if missing_perm else None,
        )
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/issues/{issue_id}/return", response_model=ActionResult)
def return_issue(
    issue_id: int,
    body: ReturnBody,
    x_staff_id: int = Header(default=0, alias="X-Staff-Id"),
) -> ActionResult:
    """苗木管理员退回发放记录，缘由必填；其他岗位调用会被驳回。"""
    entry, message = service.return_issue(x_staff_id, issue_id, body.reason)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/rotate", response_model=ActionResult)
def rotate(body: RotateBody) -> ActionResult:
    """轮换点位登记员：历史记录的原登记人不动。"""
    point, message = service.rotate(body.point_code.strip(), body.new_staff_id)
    if point is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=point)


@router.get("/summary")
def summary() -> dict[str, Any]:
    """发放汇总与活动台账对账：逐行比对汇总苗数与台账已发苗数。"""
    return service.summary()
