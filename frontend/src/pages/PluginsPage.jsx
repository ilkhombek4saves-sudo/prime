import React, { useEffect, useState } from "react";
import {
  Box, Button, Chip, IconButton, Tooltip, Typography,
} from "@mui/material";
import SettingsIcon from "@mui/icons-material/Settings";
import DeleteIcon from "@mui/icons-material/Delete";
import DownloadIcon from "@mui/icons-material/Download";
import DataTable from "../components/DataTable";
import AppModal from "../components/AppModal";
import FormInput from "../components/FormInput";
import api from "../services/api";

export default function PluginsPage() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [installOpen, setInstallOpen] = useState(false);
  const [pluginUrl, setPluginUrl] = useState("");
  const [configTarget, setConfigTarget] = useState(null);
  const [configJson, setConfigJson] = useState("");
  const [deleteTarget, setDeleteTarget] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get("/plugins");
      setRows(Array.isArray(res.data) ? res.data : res.data?.items || []);
    } catch {
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleInstall = async () => {
    if (!pluginUrl.trim()) return;
    await api.post("/plugins/install", { url: pluginUrl });
    setInstallOpen(false);
    setPluginUrl("");
    await load();
  };

  const openConfig = (plugin) => {
    setConfigTarget(plugin);
    setConfigJson(JSON.stringify(plugin.config || {}, null, 2));
  };

  const saveConfig = async () => {
    if (!configTarget) return;
    const config = JSON.parse(configJson);
    await api.patch(`/plugins/${configTarget.id}`, { config });
    setConfigTarget(null);
    await load();
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    await api.delete(`/plugins/${deleteTarget.id}`);
    setDeleteTarget(null);
    await load();
  };

  const columns = [
    { key: "name", label: "Name" },
    { key: "description", label: "Description" },
    {
      key: "enabled",
      label: "Status",
      render: (val) => (
        <Chip
          label={val !== false ? "Enabled" : "Disabled"}
          color={val !== false ? "success" : "default"}
          size="small"
        />
      ),
    },
    {
      key: "permissions",
      label: "Permissions",
      render: (val) => (val || []).join(", ") || "—",
    },
    {
      key: "_actions",
      label: "Actions",
      sortable: false,
      render: (_, row) => (
        <Box sx={{ display: "flex", gap: 0.5 }}>
          <Tooltip title="Configure">
            <IconButton size="small" onClick={(e) => { e.stopPropagation(); openConfig(row); }}>
              <SettingsIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Remove">
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
        <Typography variant="h5">Plugins</Typography>
        <Button variant="contained" startIcon={<DownloadIcon />} onClick={() => setInstallOpen(true)}>
          Install Plugin
        </Button>
      </Box>

      <DataTable
        columns={columns}
        rows={rows}
        loading={loading}
        searchable
        emptyMessage="No plugins installed."
      />

      {/* Install modal */}
      <AppModal open={installOpen} onClose={() => setInstallOpen(false)}>
        <Typography variant="h6" sx={{ mb: 1 }}>Install Plugin</Typography>
        <FormInput
          label="Plugin URL or package name"
          value={pluginUrl}
          onChange={setPluginUrl}
          required
        />
        <Box sx={{ mt: 2, display: "flex", gap: 1, justifyContent: "flex-end" }}>
          <Button onClick={() => setInstallOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleInstall} disabled={!pluginUrl.trim()}>
            Install
          </Button>
        </Box>
      </AppModal>

      {/* Configure modal */}
      <AppModal open={!!configTarget} onClose={() => setConfigTarget(null)}>
        <Typography variant="h6" sx={{ mb: 1 }}>
          Configure: {configTarget?.name}
        </Typography>
        <FormInput
          label="Configuration (JSON)"
          value={configJson}
          onChange={setConfigJson}
        />
        <Box sx={{ mt: 2, display: "flex", gap: 1, justifyContent: "flex-end" }}>
          <Button onClick={() => setConfigTarget(null)}>Cancel</Button>
          <Button variant="contained" onClick={saveConfig}>Save</Button>
        </Box>
      </AppModal>

      {/* Delete confirmation */}
      <AppModal open={!!deleteTarget} onClose={() => setDeleteTarget(null)}>
        <Typography variant="h6" sx={{ mb: 1 }}>Remove Plugin</Typography>
        <Typography>
          Are you sure you want to remove <strong>{deleteTarget?.name}</strong>?
        </Typography>
        <Box sx={{ mt: 2, display: "flex", gap: 1, justifyContent: "flex-end" }}>
          <Button onClick={() => setDeleteTarget(null)}>Cancel</Button>
          <Button variant="contained" color="error" onClick={handleDelete}>Remove</Button>
        </Box>
      </AppModal>
    </Box>
  );
}
