"""
Node Execution API — REST endpoints for OpenClaw-style node execution approval workflow.

This provides HTTP access to the node execution queue and approval system,
complementing the WebSocket control plane.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.persistence.database import SessionLocal
from app.persistence.models import User
from app.services.node_runtime import NodeRuntimeService

router = APIRouter(prefix="/node-executions", tags=["node-executions"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Schemas ───────────────────────────────────────────────────────────────────


class ExecutionRequest(BaseModel):
    connection_id: str
    node_id: str
    node_name: str = "unknown"
    node_caps: list[str] = []
    command: str
    params: dict[str, Any] = {}
    working_dir: str | None = None
    env_vars: dict[str, str] = {}
    idempotency_key: str | None = None
    auto_approve_rules: list[str] = []


class ExecutionResponse(BaseModel):
    success: bool
    execution_id: str | None
    status: str
    requires_approval: bool
    approval_queue_id: str | None
    message: str


class ApprovalItem(BaseModel):
    id: str
    execution_id: str
    connection_id: str
    node_id: str
    node_name: str
    command: str
    params_summary: str
    risk_level: str
    created_at: str
    expires_at: str


class ApprovalListResponse(BaseModel):
    items: list[ApprovalItem]
    count: int


class ApprovalActionRequest(BaseModel):
    reason: str | None = None


class ApprovalActionResponse(BaseModel):
    success: bool
    execution_id: str | None
    status: str
    message: str


class ExecutionStatusResponse(BaseModel):
    id: str
    status: str
    node_id: str
    command: str
    requires_approval: bool
    approved_at: str | None
    started_at: str | None
    completed_at: str | None
    exit_code: int | None
    stdout: str | None
    stderr: str | None
    error_message: str | None


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/request", response_model=ExecutionResponse)
def request_execution(
    req: ExecutionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Request execution of a command from a node.
    
    This is the main entry point for node execution. The command will be
    assessed for risk and either executed immediately or queued for approval.
    """
    service = NodeRuntimeService(db)
    
    result = service.request_execution(
        connection_id=req.connection_id,
        node_id=req.node_id,
        node_name=req.node_name,
        node_caps=req.node_caps,
        command=req.command,
        params=req.params,
        working_dir=req.working_dir,
        env_vars=req.env_vars,
        idempotency_key=req.idempotency_key,
        auto_approve_rules=req.auto_approve_rules,
    )
    
    return ExecutionResponse(
        success=result.success,
        execution_id=str(result.execution_id) if result.execution_id else None,
        status=result.status,
        requires_approval=result.requires_approval,
        approval_queue_id=str(result.approval_queue_id) if result.approval_queue_id else None,
        message=result.message,
    )


@router.get("/approvals/pending", response_model=ApprovalListResponse)
def list_pending_approvals(
    connection_id: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List pending node execution approvals.
    
    Operators can view the approval queue and decide which executions
    to approve or reject based on risk level and command details.
    """
    service = NodeRuntimeService(db)
    items = service.list_pending_approvals(connection_id=connection_id, limit=limit)
    
    return ApprovalListResponse(
        items=[
            ApprovalItem(
                id=str(item.id),
                execution_id=str(item.execution_id),
                connection_id=item.connection_id,
                node_id=item.node_id,
                node_name=item.node_name,
                command=item.command,
                params_summary=item.params_summary,
                risk_level=item.risk_level,
                created_at=item.created_at.isoformat() if item.created_at else "",
                expires_at=item.expires_at.isoformat() if item.expires_at else "",
            )
            for item in items
        ],
        count=len(items),
    )


@router.post("/approvals/{queue_id}/approve", response_model=ApprovalActionResponse)
def approve_execution(
    queue_id: UUID,
    req: ApprovalActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approve a pending node execution.
    
    Once approved, the execution can proceed to the actual command execution phase.
    """
    service = NodeRuntimeService(db)
    
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get('id')
    result = service.approve_execution(
        queue_id=queue_id,
        approved_by=user_id,
        reason=req.reason,
    )
    
    if not result.success and result.status == "error":
        raise HTTPException(status_code=404, detail=result.message)
    
    return ApprovalActionResponse(
        success=result.success,
        execution_id=str(result.execution_id) if result.execution_id else None,
        status=result.status,
        message=result.message,
    )


@router.post("/approvals/{queue_id}/reject", response_model=ApprovalActionResponse)
def reject_execution(
    queue_id: UUID,
    req: ApprovalActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reject a pending node execution.
    
    The execution will be marked as rejected and will not proceed.
    """
    service = NodeRuntimeService(db)
    
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get('id')
    result = service.reject_execution(
        queue_id=queue_id,
        rejected_by=user_id,
        reason=req.reason,
    )
    
    if not result.success and result.status == "error":
        raise HTTPException(status_code=404, detail=result.message)
    
    return ApprovalActionResponse(
        success=result.success,
        execution_id=str(result.execution_id) if result.execution_id else None,
        status=result.status,
        message=result.message,
    )


@router.get("/{execution_id}/status", response_model=ExecutionStatusResponse)
def get_execution_status(
    execution_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the status of a node execution.
    
    Returns full details including stdout/stderr if execution is completed.
    """
    from app.persistence.models import NodeExecution
    
    execution = db.get(NodeExecution, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    return ExecutionStatusResponse(
        id=str(execution.id),
        status=execution.status.value,
        node_id=execution.node_id,
        command=execution.command,
        requires_approval=execution.requires_approval,
        approved_at=execution.approved_at.isoformat() if execution.approved_at else None,
        started_at=execution.started_at.isoformat() if execution.started_at else None,
        completed_at=execution.completed_at.isoformat() if execution.completed_at else None,
        exit_code=execution.exit_code,
        stdout=execution.stdout,
        stderr=execution.stderr,
        error_message=execution.error_message,
    )


@router.post("/{execution_id}/run", response_model=ExecutionResponse)
async def run_execution(
    execution_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run an approved execution.
    
    This triggers the actual command execution. The execution must be
    in 'approved' status before it can be run.
    """
    from app.services.sandbox_service import SandboxService
    
    service = NodeRuntimeService(db)
    
    # Check if execution exists and is approved
    from app.persistence.models import NodeExecution
    execution = db.get(NodeExecution, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    if execution.status.value != "approved":
        raise HTTPException(
            status_code=400,
            detail=f"Execution is not approved (status: {execution.status.value})"
        )
    
    # Run execution
    result = await service.execute_approved(
        execution_id=execution_id,
        sandbox_service=SandboxService() if hasattr(SandboxService, 'execute') else None,
    )
    
    return ExecutionResponse(
        success=result.success,
        execution_id=str(result.execution_id) if result.execution_id else None,
        status=result.status,
        requires_approval=False,
        approval_queue_id=None,
        message=result.message or "Execution completed",
    )
