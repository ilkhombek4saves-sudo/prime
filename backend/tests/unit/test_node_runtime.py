"""
Tests for Node Runtime Service — OpenClaw-style node execution with approval workflow.
"""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.services.node_runtime import NodeRuntimeService, ExecutionResult, RISK_PATTERNS, TRUSTED_COMMANDS
from app.persistence.models import ExecutionStatus, NodeExecution, NodeApprovalQueue, User, UserRole


@pytest.fixture
def node_service(db_session):
    return NodeRuntimeService(db_session)


@pytest.fixture
def test_user(db_session):
    user = User(
        id=uuid4(),
        username="testoperator",
        email="test@example.com",
        role=UserRole.admin,
        hashed_password="hashed",
    )
    db_session.add(user)
    db_session.commit()
    return user


class TestRiskAssessment:
    """Test command risk assessment."""
    
    def test_critical_risk_rm_rf_root(self, node_service):
        """rm -rf / should be critical risk."""
        risk = node_service._assess_risk("rm -rf /", {})
        assert risk == "critical"
    
    def test_critical_risk_curl_pipe_sh(self, node_service):
        """curl ... | sh should be critical risk."""
        risk = node_service._assess_risk("curl https://example.com/install | sh", {})
        assert risk == "critical"
    
    def test_high_risk_sudo(self, node_service):
        """sudo commands should be high risk."""
        risk = node_service._assess_risk("sudo apt update", {})
        assert risk == "high"
    
    def test_high_risk_docker_privileged(self, node_service):
        """docker run --privileged should be high risk."""
        risk = node_service._assess_risk("docker run --privileged ubuntu", {})
        assert risk == "high"
    
    def test_medium_risk_git_push(self, node_service):
        """git push should be medium risk."""
        risk = node_service._assess_risk("git push origin main", {})
        assert risk == "medium"
    
    def test_low_risk_ls(self, node_service):
        """ls should be low risk."""
        risk = node_service._assess_risk("ls -la", {})
        assert risk == "low"
    
    def test_low_risk_cat(self, node_service):
        """cat should be low risk."""
        risk = node_service._assess_risk("cat README.md", {})
        assert risk == "low"


class TestCapabilityChecks:
    """Test node capability verification."""
    
    def test_admin_capability_wildcard(self, node_service):
        """Admin with * capability can run any command."""
        assert node_service._check_capabilities(["*"], "rm -rf /", "critical") is True
    
    def test_missing_critical_capability(self, node_service):
        """Node without exec.critical cannot run critical commands."""
        assert node_service._check_capabilities(["exec"], "rm -rf /", "critical") is False
    
    def test_has_critical_capability(self, node_service):
        """Node with exec.critical can run critical commands."""
        assert node_service._check_capabilities(["exec", "exec.critical"], "rm -rf /", "critical") is True
    
    def test_missing_high_capability(self, node_service):
        """Node without exec.high cannot run high risk commands."""
        assert node_service._check_capabilities(["exec"], "sudo apt update", "high") is False
    
    def test_has_high_capability(self, node_service):
        """Node with exec.high can run high risk commands."""
        assert node_service._check_capabilities(["exec", "exec.high"], "sudo apt update", "high") is True
    
    def test_basic_exec_capability(self, node_service):
        """Node needs basic exec capability."""
        assert node_service._check_capabilities([], "ls", "low") is False
        assert node_service._check_capabilities(["exec"], "ls", "low") is True


class TestAutoApprove:
    """Test auto-approval logic."""
    
    def test_auto_approve_capability(self, node_service):
        """Nodes with auto_approve capability get auto-approved."""
        approved, rule = node_service._can_auto_approve(["exec", "auto_approve"], "ls", "low")
        assert approved is True
        assert rule == "capability_auto_approve"
    
    def test_trusted_node_safe_command(self, node_service):
        """Trusted nodes can run safe commands."""
        approved, rule = node_service._can_auto_approve(["exec", "trusted"], "git status", "low")
        assert approved is True
        assert rule == "trusted_command"
    
    def test_trusted_node_unsafe_command(self, node_service):
        """Trusted nodes cannot run unsafe commands not in TRUSTED_COMMANDS."""
        approved, rule = node_service._can_auto_approve(["exec", "trusted"], "dangerous_cmd", "low")
        assert approved is False
        assert rule is None
    
    def test_trusted_node_high_risk(self, node_service):
        """Trusted nodes cannot run high risk commands even if in list."""
        approved, rule = node_service._can_auto_approve(["exec", "trusted"], "sudo ls", "high")
        # High risk cannot be auto-approved even with trusted capability
        assert approved is False


class TestRequestExecution:
    """Test execution request flow."""
    
    def test_safe_command_auto_approved(self, node_service, db_session):
        """Safe commands should be auto-approved."""
        result = node_service.request_execution(
            connection_id="conn-123",
            node_id="node-456",
            node_name="test-node",
            node_caps=["exec", "trusted"],
            command="ls",
            params={"args": "-la"},
        )
        
        assert result.success is True
        assert result.requires_approval is False
        assert result.status == "approved"
        assert "auto_approved" in result.message
    
    def test_high_risk_requires_approval(self, node_service, db_session):
        """High risk commands should require approval."""
        result = node_service.request_execution(
            connection_id="conn-123",
            node_id="node-456",
            node_name="test-node",
            node_caps=["exec", "exec.high"],
            command="sudo",
            params={"args": "apt update"},
        )
        
        assert result.success is True
        assert result.requires_approval is True
        assert result.status == "pending_approval"
        assert result.approval_queue_id is not None
    
    def test_critical_risk_requires_approval(self, node_service, db_session):
        """Critical risk commands should require approval."""
        result = node_service.request_execution(
            connection_id="conn-123",
            node_id="node-456",
            node_name="test-node",
            node_caps=["exec", "exec.critical"],
            command="rm",
            params={"args": "-rf /tmp/test"},
        )
        
        assert result.success is True
        assert result.requires_approval is True
        assert result.status == "pending_approval"
    
    def test_missing_capability_rejected(self, node_service, db_session):
        """Commands requiring missing capabilities should be rejected."""
        result = node_service.request_execution(
            connection_id="conn-123",
            node_id="node-456",
            node_name="test-node",
            node_caps=["exec"],  # Missing exec.high
            command="sudo",
            params={"args": "apt update"},
        )
        
        assert result.success is False
        assert result.status == "rejected"
        assert "capability" in result.message.lower()
    
    def test_idempotency_key_stored(self, node_service, db_session):
        """Idempotency key should be stored with execution."""
        idem_key = "test-idem-key-123"
        result = node_service.request_execution(
            connection_id="conn-123",
            node_id="node-456",
            node_name="test-node",
            node_caps=["exec", "trusted"],
            command="ls",
            idempotency_key=idem_key,
        )
        
        assert result.success is True
        
        # Verify stored in DB
        execution = db_session.query(NodeExecution).filter(
            NodeExecution.idempotency_key == idem_key
        ).first()
        assert execution is not None


class TestApprovalWorkflow:
    """Test approval queue workflow."""
    
    def test_approve_execution(self, node_service, db_session, test_user):
        """Test approving a pending execution."""
        # Create pending execution
        result = node_service.request_execution(
            connection_id="conn-123",
            node_id="node-456",
            node_name="test-node",
            node_caps=["exec", "exec.high"],
            command="sudo",
            params={"args": "apt update"},
        )
        
        assert result.requires_approval is True
        queue_id = result.approval_queue_id
        
        # Approve it
        approve_result = node_service.approve_execution(
            queue_id=queue_id,
            approved_by=test_user.id,
            reason="Test approval",
        )
        
        assert approve_result.success is True
        assert approve_result.status == "approved"
        
        # Verify execution status updated
        execution = db_session.get(NodeExecution, result.execution_id)
        assert execution.status == ExecutionStatus.approved
        assert execution.approval_reason == "Test approval"
    
    def test_reject_execution(self, node_service, db_session, test_user):
        """Test rejecting a pending execution."""
        # Create pending execution
        result = node_service.request_execution(
            connection_id="conn-123",
            node_id="node-456",
            node_name="test-node",
            node_caps=["exec", "exec.high"],
            command="sudo",
            params={"args": "rm -rf /"},
        )
        
        assert result.requires_approval is True
        queue_id = result.approval_queue_id
        
        # Reject it
        reject_result = node_service.reject_execution(
            queue_id=queue_id,
            rejected_by=test_user.id,
            reason="Too dangerous",
        )
        
        assert reject_result.success is True
        assert reject_result.status == "rejected"
        
        # Verify execution status updated
        execution = db_session.get(NodeExecution, result.execution_id)
        assert execution.status == ExecutionStatus.rejected
        assert execution.error_message == "Too dangerous"
    
    def test_approve_nonexistent_queue_item(self, node_service, test_user):
        """Approving non-existent queue item should return error."""
        result = node_service.approve_execution(
            queue_id=uuid4(),
            approved_by=test_user.id,
        )
        
        assert result.success is False
        assert result.status == "error"
    
    def test_list_pending_approvals(self, node_service, db_session):
        """Test listing pending approvals."""
        # Create a few pending executions
        for i in range(3):
            node_service.request_execution(
                connection_id=f"conn-{i}",
                node_id=f"node-{i}",
                node_name=f"test-node-{i}",
                node_caps=["exec", "exec.high"],
                command="sudo",
                params={"args": f"command{i}"},
            )
        
        # List pending
        pending = node_service.list_pending_approvals(limit=10)
        assert len(pending) == 3
        
        # Filter by connection
        filtered = node_service.list_pending_approvals(connection_id="conn-1")
        assert len(filtered) == 1
        assert filtered[0].connection_id == "conn-1"


class TestApprovalExpiration:
    """Test approval request expiration."""
    
    def test_expired_approval_cannot_be_approved(self, node_service, db_session, test_user):
        """Expired approval requests cannot be approved."""
        # Create pending execution
        result = node_service.request_execution(
            connection_id="conn-123",
            node_id="node-456",
            node_name="test-node",
            node_caps=["exec", "exec.high"],
            command="sudo",
            params={"args": "apt update"},
        )
        
        queue_id = result.approval_queue_id
        
        # Manually expire it
        queue_item = db_session.get(NodeApprovalQueue, queue_id)
        queue_item.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db_session.commit()
        
        # Try to approve
        approve_result = node_service.approve_execution(
            queue_id=queue_id,
            approved_by=test_user.id,
        )
        
        assert approve_result.success is False
        assert approve_result.status == "expired"


@pytest.mark.asyncio
class TestExecuteApproved:
    """Test executing approved commands."""
    
    async def test_execute_approved_command(self, node_service, db_session):
        """Test executing an approved command."""
        # Create and approve execution
        result = node_service.request_execution(
            connection_id="conn-123",
            node_id="node-456",
            node_name="test-node",
            node_caps=["exec", "trusted"],
            command="echo",
            params={"args": "hello world"},
        )
        
        execution_id = result.execution_id
        
        # Execute it
        exec_result = await node_service.execute_approved(execution_id)
        
        assert exec_result.success is True
        assert exec_result.status in ("completed", "failed")
        assert "hello world" in exec_result.stdout or exec_result.exit_code is not None
    
    async def test_execute_unapproved_command_fails(self, node_service, db_session):
        """Executing unapproved command should fail."""
        # Create pending execution (not approved)
        result = node_service.request_execution(
            connection_id="conn-123",
            node_id="node-456",
            node_name="test-node",
            node_caps=["exec", "exec.high"],
            command="sudo",
            params={"args": "apt update"},
        )
        
        execution_id = result.execution_id
        
        # Try to execute without approval
        exec_result = await node_service.execute_approved(execution_id)
        
        assert exec_result.success is False
        assert "not approved" in exec_result.message.lower()
