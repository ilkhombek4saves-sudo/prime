import React, { useEffect, useState } from "react";
import {
  Box, Button, Chip, IconButton, MenuItem, TextField, Tooltip, Typography,
} from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import CancelIcon from "@mui/icons-material/Cancel";
import ReplayIcon from "@mui/icons-material/Replay";
import VisibilityIcon from "@mui/icons-material/Visibility";
import DataTable from "../components/DataTable";
import AppModal from "../components/AppModal";
import api from "../services/api";

const STATUS_COLORS = {
  pending: "warning",
  running: "info",
  completed: "success",
  failed: "error",
  cancelled: "default",
};

export default function TasksPage() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");
  const [detailTask, setDetailTask] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const params = statusFilter !== "all" ? { status: statusFilter } : {};
      const res = await api.get("/tasks", { params });
      setRows(Array.isArray(res.data) ? res.data : res.data?.items || []);
    } catch {
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [statusFilter]);

  const retry = async (task) => {
    await api.post(`/tasks/${task.id}/retry`);
    await load();
  };

  const cancel = async (task) => {
    await api.post(`/tasks/${task.id}/cancel`);
    await load();
  };

  const viewDetail = async (task) => {
    try {
      const res = await api.get(`/tasks/${task.id}`);
      setDetailTask(res.data);
    } catch {
      setDetailTask(task);
    }
  };

  const columns = [
    { key: "id", label: "ID", render: (val) => val?.slice(0, 8) || val },
    {
      key: "status",
      label: "Status",
      render: (val) => (
        <Chip
          label={val || "unknown"}
          color={STATUS_COLORS[val] || "default"}
          size="small"
          sx={{ textTransform: "capitalize" }}
        />
      ),
    },
    { key: "type", label: "Type" },
    {
      key: "created_at",
      label: "Created",
      render: (val) => val ? new Date(val).toLocaleString() : "—",
    },
    {
      key: "_actions",
      label: "Actions",
      sortable: false,
      render: (_, row) => (
        <Box sx={{ display: "flex", gap: 0.5 }}>
          <Tooltip title="View details">
            <IconButton size="small" onClick={(e) => { e.stopPropagation(); viewDetail(row); }}>
              <VisibilityIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          {(row.status === "failed" || row.status === "cancelled") && (
            <Tooltip title="Retry">
              <IconButton size="small" color="primary" onClick={(e) => { e.stopPropagation(); retry(row); }}>
                <ReplayIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          {(row.status === "pending" || row.status === "running") && (
            <Tooltip title="Cancel">
              <IconButton size="small" color="error" onClick={(e) => { e.stopPropagation(); cancel(row); }}>
                <CancelIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      ),
    },
  ];

  return (
    <Box>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
        <Typography variant="h5">Tasks</Typography>
        <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
          <TextField
            select
            size="small"
            label="Status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            sx={{ minWidth: 140 }}
          >
            <MenuItem value="all">All</MenuItem>
            <MenuItem value="pending">Pending</MenuItem>
            <MenuItem value="running">Running</MenuItem>
            <MenuItem value="completed">Completed</MenuItem>
            <MenuItem value="failed">Failed</MenuItem>
            <MenuItem value="cancelled">Cancelled</MenuItem>
          </TextField>
          <Tooltip title="Refresh">
            <IconButton onClick={load}><RefreshIcon /></IconButton>
          </Tooltip>
        </Box>
      </Box>

      <DataTable
        columns={columns}
        rows={rows}
        loading={loading}
        searchable
        emptyMessage="No tasks found."
      />

      {/* Detail modal */}
      <AppModal open={!!detailTask} onClose={() => setDetailTask(null)}>
        <Typography variant="h6" sx={{ mb: 2 }}>Task Details</Typography>
        {detailTask && (
          <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
            <Typography variant="body2"><strong>ID:</strong> {detailTask.id}</Typography>
            <Typography variant="body2"><strong>Status:</strong> {detailTask.status}</Typography>
            <Typography variant="body2"><strong>Type:</strong> {detailTask.type || "—"}</Typography>
            <Typography variant="body2">
              <strong>Created:</strong> {detailTask.created_at ? new Date(detailTask.created_at).toLocaleString() : "—"}
            </Typography>
            {detailTask.updated_at && (
              <Typography variant="body2">
                <strong>Updated:</strong> {new Date(detailTask.updated_at).toLocaleString()}
              </Typography>
            )}
            {detailTask.error && (
              <Box sx={{ mt: 1, p: 1.5, bgcolor: "error.50", borderRadius: 1 }}>
                <Typography variant="body2" color="error.main">
                  <strong>Error:</strong> {detailTask.error}
                </Typography>
              </Box>
            )}
            {detailTask.result && (
              <Box sx={{ mt: 1, p: 1.5, bgcolor: "grey.100", borderRadius: 1, maxHeight: 200, overflow: "auto" }}>
                <Typography variant="body2" sx={{ fontFamily: "monospace", fontSize: 12, whiteSpace: "pre-wrap" }}>
                  {typeof detailTask.result === "string" ? detailTask.result : JSON.stringify(detailTask.result, null, 2)}
                </Typography>
              </Box>
            )}
          </Box>
        )}
        <Box sx={{ mt: 2, display: "flex", justifyContent: "flex-end" }}>
          <Button onClick={() => setDetailTask(null)}>Close</Button>
        </Box>
      </AppModal>
    </Box>
  );
}
