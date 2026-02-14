"""
Node Runtime Service — OpenClaw-style node execution with approval workflow.

This service manages execution of commands from connected nodes (like Claude Code,
sandboxed agents, or external tools). It supports:
- Capability-based permission system
- Command allowlists/denylists
- Operator approval queue for sensitive operations
- Auto-approval rules for trusted commands
- Execution sandboxing via Docker
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import shlex
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.persistence.models import (
    ExecutionStatus,
    NodeApprovalQueue,
    NodeExecution,
)
from app.services.event_bus import get_event_bus

event_bus = get_event_bus()


# Risk classification for commands
RISK_PATTERNS = {
    "critical": [
        r"rm\s+-rf\s+/",
        r"mkfs\.",
        r"dd\s+if=.*of=/dev",
        r":\(\)\s*\{\s*:\|\:\s*\&\s*\}",  # fork bomb
        r"curl.*\|.*sh",
        r"wget.*\|.*sh",
        r"curl.*\|.*bash",
    ],
    "high": [
        r"sudo\s+",
        r"rm\s+-rf",
        r"chmod\s+-R",
        r"chown\s+-R",
        r"docker\s+run\s+--privileged",
        r"kubectl\s+(delete|apply)",
    ],
    "medium": [
        r"git\s+(push|force)",
        r"scp\s+",
        r"rsync\s+.*--delete",
        r"docker\s+(build|run)",
    ],
}

# Commands that can be auto-approved for nodes with 'trusted' capability
TRUSTED_COMMANDS = {
    "ls", "cat", "head", "tail", "grep", "find", "pwd", "echo",
    "git", "status", "diff", "log", "show", "python", "python3",
    "pip", "npm", "yarn", "node", "cd", "mkdir", "touch",
    "code", "cursor", "vim", "nano", "less", "more",
}


@dataclass
class ExecutionResult:
    success: bool
    execution_id: UUID | None
    status: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    requires_approval: bool = False
    approval_queue_id: UUID | None = None
    message: str = ""


class NodeCapabilityError(RuntimeError):
    """Raised when node lacks required capability."""
    pass


class NodeRuntimeService:
    """Manages node execution lifecycle with optional approval workflow."""
    
    # Global setting: if True, all commands are auto-approved (no approval workflow)
    AUTO_APPROVE_ALL = True  # Set to False to enable approval queue
    
    def __init__(self, db: Session):
        self.db = db
    
    def _assess_risk(self, command: str, params: dict) -> str:
        """Assess risk level of a command."""
        full_cmd = f"{command} {params.get('args', '')}".lower()
        
        for level, patterns in RISK_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, full_cmd):
                    return level
        
        return "low"
    
    def _check_capabilities(
        self,
        node_caps: list[str],
        command: str,
        risk_level: str,
    ) -> bool:
        """Check if node has required capabilities for command."""
        if "*" in node_caps or "admin" in node_caps:
            return True
        
        if risk_level == "critical" and "exec.critical" not in node_caps:
            return False
        if risk_level == "high" and "exec.high" not in node_caps:
            return False
        
        # Basic execution capability required
        if "exec" not in node_caps and "exec.*" not in node_caps:
            return False
        
        return True
    
    def _can_auto_approve(
        self,
        node_caps: list[str],
        command: str,
        risk_level: str,
        auto_approve_rules: list[str] | None = None,
    ) -> tuple[bool, str | None]:
        """Check if execution can be auto-approved."""
        if "auto_approve" in node_caps or "exec.auto_approve" in node_caps:
            return True, "capability_auto_approve"
        
        # Trusted nodes can run safe commands
        if "trusted" in node_caps and risk_level == "low":
            base_cmd = command.split()[0] if command else ""
            if base_cmd in TRUSTED_COMMANDS:
                return True, "trusted_command"
        
        # Check custom rules
        if auto_approve_rules:
            for rule in auto_approve_rules:
                if re.search(rule, command, re.IGNORECASE):
                    return True, f"rule:{rule}"
        
        return False, None
    
    def request_execution(
        self,
        *,
        connection_id: str,
        node_id: str,
        node_name: str,
        node_caps: list[str],
        command: str,
        params: dict[str, Any] | None = None,
        working_dir: str | None = None,
        env_vars: dict[str, str] | None = None,
        idempotency_key: str | None = None,
        auto_approve_rules: list[str] | None = None,
        requested_by: UUID | None = None,
    ) -> ExecutionResult:
        """Request execution of a command from a node.
        
        This is the main entry point for OpenClaw-style node execution.
        It assesses risk, checks capabilities, and either executes immediately
        or queues for operator approval.
        """
        params = params or {}
        
        # Assess risk
        risk_level = self._assess_risk(command, params)
        
        # Check capabilities
        if not self._check_capabilities(node_caps, command, risk_level):
            return ExecutionResult(
                success=False,
                execution_id=None,
                status="rejected",
                message=f"Node lacks required capability for {risk_level} risk command",
            )
        
        # Determine if approval is required
        # If AUTO_APPROVE_ALL is True, skip approval workflow entirely
        if self.AUTO_APPROVE_ALL:
            requires_approval = False
            auto_approved = True
            auto_rule = "auto_approve_all"
        else:
            requires_approval = risk_level in ("high", "critical")
            
            # Check auto-approval
            auto_approved, auto_rule = self._can_auto_approve(
                node_caps, command, risk_level, auto_approve_rules
            )
            
            if auto_approved:
                requires_approval = False
        
        # Create execution record
        execution = NodeExecution(
            connection_id=connection_id,
            node_id=node_id,
            node_name=node_name,
            command=command,
            params=params,
            working_dir=working_dir,
            env_vars=env_vars or {},
            status=ExecutionStatus.pending if requires_approval else ExecutionStatus.approved,
            requires_approval=requires_approval,
            idempotency_key=idempotency_key,
        )
        
        if not requires_approval:
            execution.status = ExecutionStatus.approved
            execution.approved_at = datetime.now(timezone.utc)
            execution.approval_reason = auto_rule or "auto_approved"
        
        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)
        
        # If approval required, add to queue
        if requires_approval:
            queue_item = NodeApprovalQueue(
                execution_id=execution.id,
                connection_id=connection_id,
                node_id=node_id,
                node_name=node_name,
                command=command,
                params_summary=str(params)[:500],
                risk_level=risk_level,
                status="pending",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
                auto_approved=False,
            )
            self.db.add(queue_item)
            self.db.commit()
            self.db.refresh(queue_item)
            
            # Publish event for operators
            event_bus.publish_nowait(
                "node.execution.pending_approval",
                {
                    "execution_id": str(execution.id),
                    "queue_id": str(queue_item.id),
                    "node_id": node_id,
                    "node_name": node_name,
                    "command": command,
                    "risk_level": risk_level,
                    "connection_id": connection_id,
                },
            )
            
            return ExecutionResult(
                success=True,
                execution_id=execution.id,
                status="pending_approval",
                requires_approval=True,
                approval_queue_id=queue_item.id,
                message=f"Execution queued for approval (risk: {risk_level})",
            )
        
        # Auto-approved, execute immediately
        event_bus.publish_nowait(
            "node.execution.approved",
            {
                "execution_id": str(execution.id),
                "node_id": node_id,
                "command": command,
                "auto_approved": True,
                "reason": auto_rule,
            },
        )
        
        return ExecutionResult(
            success=True,
            execution_id=execution.id,
            status="approved",
            requires_approval=False,
            message=f"Execution auto-approved ({auto_rule or 'no_risk'})",
        )
    
    def approve_execution(
        self,
        *,
        queue_id: UUID,
        approved_by: UUID,
        reason: str | None = None,
    ) -> ExecutionResult:
        """Approve a pending execution from the queue."""
        queue_item = self.db.get(NodeApprovalQueue, queue_id)
        if not queue_item:
            return ExecutionResult(
                success=False,
                execution_id=None,
                status="error",
                message="Queue item not found",
            )
        
        if queue_item.status != "pending":
            return ExecutionResult(
                success=False,
                execution_id=None,
                status="error",
                message=f"Queue item is already {queue_item.status}",
            )
        
        if queue_item.expires_at < datetime.now(timezone.utc):
            queue_item.status = "expired"
            self.db.commit()
            return ExecutionResult(
                success=False,
                execution_id=None,
                status="expired",
                message="Approval request has expired",
            )
        
        # Update queue item
        queue_item.status = "approved"
        queue_item.resolved_at = datetime.now(timezone.utc)
        queue_item.resolved_by = approved_by
        queue_item.resolution_reason = reason or "approved_by_operator"
        
        # Update execution
        execution = self.db.get(NodeExecution, queue_item.execution_id)
        execution.status = ExecutionStatus.approved
        execution.approved_at = datetime.now(timezone.utc)
        execution.approved_by = approved_by
        execution.approval_reason = reason or "operator_approved"
        
        self.db.commit()
        
        # Notify via event bus
        event_bus.publish_nowait(
            "node.execution.approved",
            {
                "execution_id": str(execution.id),
                "queue_id": str(queue_id),
                "node_id": execution.node_id,
                "command": execution.command,
                "approved_by": str(approved_by),
            },
        )
        
        return ExecutionResult(
            success=True,
            execution_id=execution.id,
            status="approved",
            message="Execution approved by operator",
        )
    
    def reject_execution(
        self,
        *,
        queue_id: UUID,
        rejected_by: UUID,
        reason: str | None = None,
    ) -> ExecutionResult:
        """Reject a pending execution from the queue."""
        queue_item = self.db.get(NodeApprovalQueue, queue_id)
        if not queue_item:
            return ExecutionResult(
                success=False,
                execution_id=None,
                status="error",
                message="Queue item not found",
            )
        
        if queue_item.status != "pending":
            return ExecutionResult(
                success=False,
                execution_id=None,
                status="error",
                message=f"Queue item is already {queue_item.status}",
            )
        
        # Update queue item
        queue_item.status = "rejected"
        queue_item.resolved_at = datetime.now(timezone.utc)
        queue_item.resolved_by = rejected_by
        queue_item.resolution_reason = reason or "rejected_by_operator"
        
        # Update execution
        execution = self.db.get(NodeExecution, queue_item.execution_id)
        execution.status = ExecutionStatus.rejected
        execution.error_message = reason or "Rejected by operator"
        
        self.db.commit()
        
        # Notify via event bus
        event_bus.publish_nowait(
            "node.execution.rejected",
            {
                "execution_id": str(execution.id),
                "queue_id": str(queue_id),
                "node_id": execution.node_id,
                "command": execution.command,
                "rejected_by": str(rejected_by),
                "reason": reason,
            },
        )
        
        return ExecutionResult(
            success=True,
            execution_id=execution.id,
            status="rejected",
            message=f"Execution rejected: {reason or 'No reason provided'}",
        )
    
    def list_pending_approvals(
        self,
        connection_id: str | None = None,
        limit: int = 100,
    ) -> list[NodeApprovalQueue]:
        """List pending approval requests."""
        query = self.db.query(NodeApprovalQueue).filter(
            NodeApprovalQueue.status == "pending",
            NodeApprovalQueue.expires_at > datetime.now(timezone.utc),
        )
        
        if connection_id:
            query = query.filter(NodeApprovalQueue.connection_id == connection_id)
        
        return query.order_by(NodeApprovalQueue.created_at.desc()).limit(limit).all()
    
    async def execute_approved(
        self,
        execution_id: UUID,
        sandbox_service: Any | None = None,
    ) -> ExecutionResult:
        """Execute an approved command.
        
        This runs the actual command in sandbox or local environment.
        """
        execution = self.db.get(NodeExecution, execution_id)
        if not execution:
            return ExecutionResult(
                success=False,
                execution_id=None,
                status="error",
                message="Execution not found",
            )
        
        if execution.status != ExecutionStatus.approved:
            return ExecutionResult(
                success=False,
                execution_id=execution.id,
                status=execution.status.value,
                message=f"Execution is not approved (status: {execution.status.value})",
            )
        
        # Update status
        execution.status = ExecutionStatus.in_progress
        execution.started_at = datetime.now(timezone.utc)
        self.db.commit()
        
        # Publish start event
        event_bus.publish_nowait(
            "node.execution.started",
            {
                "execution_id": str(execution.id),
                "node_id": execution.node_id,
                "command": execution.command,
            },
        )
        
        try:
            # Build command
            cmd = execution.command
            if execution.params.get("args"):
                cmd = f"{cmd} {execution.params['args']}"
            
            # Execute in sandbox if available
            if sandbox_service:
                result = await sandbox_service.execute(
                    command=cmd,
                    working_dir=execution.working_dir,
                    env_vars=execution.env_vars,
                )
                execution.exit_code = result.get("exit_code", -1)
                execution.stdout = result.get("stdout", "")
                execution.stderr = result.get("stderr", "")
            else:
                # Local execution (use with caution)
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=execution.working_dir,
                    env={**dict(), **execution.env_vars} if execution.env_vars else None,
                )
                stdout, stderr = await proc.communicate()
                execution.exit_code = proc.returncode
                execution.stdout = stdout.decode("utf-8", errors="replace")
                execution.stderr = stderr.decode("utf-8", errors="replace")
            
            # Update status
            execution.status = ExecutionStatus.completed if execution.exit_code == 0 else ExecutionStatus.failed
            execution.completed_at = datetime.now(timezone.utc)
            
            self.db.commit()
            
            # Publish completion event
            event_bus.publish_nowait(
                "node.execution.completed",
                {
                    "execution_id": str(execution.id),
                    "node_id": execution.node_id,
                    "command": execution.command,
                    "exit_code": execution.exit_code,
                    "success": execution.exit_code == 0,
                },
            )
            
            return ExecutionResult(
                success=execution.exit_code == 0,
                execution_id=execution.id,
                status="completed" if execution.exit_code == 0 else "failed",
                stdout=execution.stdout or "",
                stderr=execution.stderr or "",
                exit_code=execution.exit_code,
            )
            
        except Exception as exc:
            execution.status = ExecutionStatus.failed
            execution.error_message = str(exc)
            execution.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            
            event_bus.publish_nowait(
                "node.execution.failed",
                {
                    "execution_id": str(execution.id),
                    "node_id": execution.node_id,
                    "error": str(exc),
                },
            )
            
            return ExecutionResult(
                success=False,
                execution_id=execution.id,
                status="failed",
                message=str(exc),
            )
