# Node Execution & Approval Workflow

OpenClaw-style node execution system for Prime. Allows connected nodes (like Claude Code,
sandboxed agents, or external tools) to request command execution with operator approval.

## Overview

This system provides:
- **Risk-based command assessment** — automatically classifies commands by risk level
- **Capability-based permissions** — nodes declare capabilities, commands require specific caps
- **Operator approval queue** — high-risk commands queue for operator review
- **Auto-approval rules** — trusted nodes can auto-approve safe commands
- **Full audit trail** — all executions logged with stdout/stderr

## Architecture

```
┌─────────────┐     request      ┌──────────────────┐
│   Node      │ ───────────────> │  NodeExecution   │
│  (Claude    │                  │    Service       │
│   Code)     │ <─────────────── │                  │
└─────────────┘   approve/run    └──────────────────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    │                     │                     │
                    ▼                     ▼                     ▼
            ┌──────────────┐    ┌────────────────┐    ┌──────────────┐
            │   Approved   │    │ Pending Queue  │    │  Rejected    │
            │   (run now)  │    │ (await operator)│   │   (denied)   │
            └──────────────┘    └────────────────┘    └──────────────┘
```

## Risk Levels

| Level | Description | Examples | Requires Approval |
|-------|-------------|----------|-------------------|
| `critical` | Dangerous system commands | `rm -rf /`, `curl \| sh`, fork bombs | Yes |
| `high` | Privileged operations | `sudo`, `docker --privileged`, `kubectl delete` | Yes |
| `medium` | Destructive changes | `git push --force`, `rsync --delete` | Configurable |
| `low` | Safe read-only commands | `ls`, `cat`, `git status` | No (if trusted) |

## Capabilities

Nodes declare capabilities on connect:

```json
{
  "node_caps": ["exec", "exec.high", "trusted", "auto_approve"]
}
```

| Capability | Description |
|------------|-------------|
| `exec` | Basic command execution |
| `exec.high` | Can run high-risk commands |
| `exec.critical` | Can run critical-risk commands |
| `trusted` | Auto-approval for safe commands |
| `auto_approve` | Auto-approval for all commands (dangerous!) |
| `*` | Admin wildcard — all permissions |

## WebSocket API

### Request Execution

```json
{
  "type": "req",
  "id": "req-123",
  "method": "node.execute",
  "params": {
    "connection_id": "conn-abc",
    "node_id": "claude-code-1",
    "node_name": "Claude Code",
    "node_caps": ["exec", "exec.high"],
    "command": "git",
    "params": {"args": "push origin main"},
    "working_dir": "/workspace/project",
    "idempotency_key": "push-abc-123"
  }
}
```

### Response

```json
{
  "type": "res",
  "id": "req-123",
  "ok": true,
  "payload": {
    "success": true,
    "execution_id": "uuid-here",
    "status": "pending_approval",
    "requires_approval": true,
    "approval_queue_id": "queue-uuid",
    "message": "Execution queued for approval (risk: high)"
  }
}
```

### List Pending Approvals

```json
{
  "type": "req",
  "id": "req-124",
  "method": "node.approvals.list",
  "params": {"limit": 10}
}
```

### Approve Execution

```json
{
  "type": "req",
  "id": "req-125",
  "method": "node.approvals.approve",
  "params": {
    "queue_id": "queue-uuid",
    "reason": "Looks safe"
  },
  "idempotency_key": "approve-xyz-789"
}
```

## REST API

### Request Execution

```bash
POST /api/node-executions/request
Authorization: Bearer <token>

{
  "connection_id": "conn-abc",
  "node_id": "claude-code-1",
  "node_name": "Claude Code",
  "node_caps": ["exec", "exec.high"],
  "command": "docker build -t myapp .",
  "working_dir": "/workspace/project"
}
```

### List Pending Approvals

```bash
GET /api/node-executions/approvals/pending
Authorization: Bearer <token>
```

### Approve

```bash
POST /api/node-executions/approvals/{queue_id}/approve
Authorization: Bearer <token>

{
  "reason": "Verified safe"
}
```

### Reject

```bash
POST /api/node-executions/approvals/{queue_id}/reject
Authorization: Bearer <token>

{
  "reason": "Too dangerous"
}
```

### Get Execution Status

```bash
GET /api/node-executions/{execution_id}/status
Authorization: Bearer <token>
```

### Run Approved Execution

```bash
POST /api/node-executions/{execution_id}/run
Authorization: Bearer <token>
```

## WebSocket Events

| Event | Description |
|-------|-------------|
| `node.execution.pending_approval` | New execution awaiting approval |
| `node.execution.approved` | Execution approved (auto or operator) |
| `node.execution.rejected` | Execution rejected |
| `node.execution.started` | Command started running |
| `node.execution.completed` | Command completed successfully |
| `node.execution.failed` | Command failed or was rejected |

Example:
```json
{
  "type": "event",
  "event": "node.execution.pending_approval",
  "payload": {
    "execution_id": "uuid",
    "queue_id": "queue-uuid",
    "node_id": "claude-code-1",
    "command": "sudo apt update",
    "risk_level": "high"
  },
  "ts": 1234567890
}
```

## Database Schema

### node_executions

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `connection_id` | string | WS connection that requested |
| `node_id` | string | Node identifier |
| `command` | string | Command to execute |
| `params` | JSON | Command arguments |
| `status` | enum | pending/approved/rejected/in_progress/completed/failed |
| `requires_approval` | bool | Whether approval was required |
| `approved_by` | UUID | Operator who approved |
| `exit_code` | int | Command exit code |
| `stdout` | text | Command output |
| `stderr` | text | Command errors |

### node_approval_queue

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `execution_id` | UUID | Linked execution |
| `command` | string | Command summary |
| `risk_level` | string | low/medium/high/critical |
| `status` | string | pending/approved/rejected/expired |
| `expires_at` | datetime | Approval request expiration |

## Auto-Approval Rules

Configure auto-approval patterns in request:

```json
{
  "auto_approve_rules": [
    "^git (status|log|diff)",
    "^ls",
    "^cat .*\\.md$"
  ]
}
```

Trusted nodes with safe commands are auto-approved by default.

## Integration with Claude Code

Claude Code (or similar agents) can connect via WebSocket:

1. Connect with `node_caps: ["exec", "exec.high", "trusted"]`
2. Request command execution via `node.execute`
3. If approved, run via `node.execute.run` or wait for operator approval
4. Receive streaming updates via WebSocket events

This enables OpenClaw-style workflows where agents can propose actions
but require operator confirmation for dangerous operations.
