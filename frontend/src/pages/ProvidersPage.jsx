import React, { useEffect, useState } from "react";
import {
  Box, Button, Chip, IconButton, MenuItem, Tooltip, Typography,
} from "@mui/material";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import DataTable from "../components/DataTable";
import AppModal from "../components/AppModal";
import FormInput from "../components/FormInput";
import api from "../services/api";

const PROVIDER_TYPES = ["OpenAI", "Anthropic", "DeepSeek", "Kimi", "Ollama", "Custom"];

export default function ProvidersPage() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [name, setName] = useState("");
  const [type, setType] = useState("OpenAI");
  const [apiBase, setApiBase] = useState("");
  const [deleteTarget, setDeleteTarget] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get("/providers");
      setRows(Array.isArray(res.data) ? res.data : res.data?.items || []);
    } catch {
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const resetForm = () => {
    setName("");
    setType("OpenAI");
    setApiBase("");
    setEditing(null);
  };

  const openCreate = () => {
    resetForm();
    setOpen(true);
  };

  const openEdit = (row) => {
    setEditing(row);
    setName(row.name || "");
    setType(row.type || "OpenAI");
    setApiBase(row.config?.api_base || "");
    setOpen(true);
  };

  const save = async () => {
    const payload = {
      name,
      type,
      active: true,
      config: {
        api_key: "env://API_KEY",
        api_base: apiBase,
        default_model: "default",
        models: { default: { max_tokens: 4096 } },
      },
    };
    if (editing) {
      await api.patch(`/providers/${editing.id}`, payload);
    } else {
      await api.post("/providers", payload);
    }
    setOpen(false);
    resetForm();
    await load();
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    await api.delete(`/providers/${deleteTarget.id}`);
    setDeleteTarget(null);
    await load();
  };

  const columns = [
    { key: "name", label: "Name" },
    { key: "type", label: "Type" },
    {
      key: "active",
      label: "Status",
      render: (val) => (
        <Chip
          label={val ? "Active" : "Inactive"}
          color={val ? "success" : "default"}
          size="small"
        />
      ),
    },
    {
      key: "_actions",
      label: "Actions",
      sortable: false,
      render: (_, row) => (
        <Box sx={{ display: "flex", gap: 0.5 }}>
          <Tooltip title="Edit">
            <IconButton size="small" onClick={(e) => { e.stopPropagation(); openEdit(row); }}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete">
            <IconButton size="small" color="error" onClick={(e) => { e.stopPropagation(); setDeleteTarget(row); }}>
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ];

  return (
    <Box>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
        <Typography variant="h5">Providers</Typography>
        <Button variant="contained" onClick={openCreate}>Add Provider</Button>
      </Box>

      <DataTable
        columns={columns}
        rows={rows}
        loading={loading}
        searchable
        emptyMessage="No providers configured. Add one to get started."
      />

      {/* Create / Edit modal */}
      <AppModal open={open} onClose={() => { setOpen(false); resetForm(); }}>
        <Typography variant="h6" sx={{ mb: 1 }}>
          {editing ? "Edit Provider" : "Create Provider"}
        </Typography>
        <FormInput label="Name" value={name} onChange={setName} required />
        <FormInput label="Type" value={type} onChange={setType} required />
        <FormInput label="API Base URL" value={apiBase} onChange={setApiBase} />
        <Box sx={{ mt: 2, display: "flex", gap: 1, justifyContent: "flex-end" }}>
          <Button onClick={() => { setOpen(false); resetForm(); }}>Cancel</Button>
          <Button variant="contained" onClick={save} disabled={!name.trim()}>
            {editing ? "Update" : "Create"}
          </Button>
        </Box>
      </AppModal>

      {/* Delete confirmation */}
      <AppModal open={!!deleteTarget} onClose={() => setDeleteTarget(null)}>
        <Typography variant="h6" sx={{ mb: 1 }}>Delete Provider</Typography>
        <Typography>
          Are you sure you want to delete <strong>{deleteTarget?.name}</strong>? This action cannot be undone.
        </Typography>
        <Box sx={{ mt: 2, display: "flex", gap: 1, justifyContent: "flex-end" }}>
          <Button onClick={() => setDeleteTarget(null)}>Cancel</Button>
          <Button variant="contained" color="error" onClick={handleDelete}>Delete</Button>
        </Box>
      </AppModal>
    </Box>
  );
}
