import React, { useCallback, useEffect, useState } from "react";
import {
  Box,
  Button,
  Chip,
  FormControl,
  FormControlLabel,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import AppModal from "../components/AppModal";
import api from "../services/api";

const DM_POLICIES = [
  { value: "pairing", label: "Pairing — users must pair first" },
  { value: "allowlist", label: "Allowlist — only listed user IDs" },
  { value: "open", label: "Open — anyone can chat" },
  { value: "disabled", label: "Disabled — bot won't respond in DMs" },
];

const DM_COLOR = { open: "success", pairing: "primary", allowlist: "warning", disabled: "error" };

const EMPTY = {
  name: "",
  description: "",
  default_provider_id: "",
  dm_policy: "pairing",
  system_prompt: "",
  web_search_enabled: false,
  memory_enabled: true,
  max_history_messages: 20,
  group_requires_mention: true,
  code_execution_enabled: false,
  active: true,
  allowed_user_ids: "",   // stored as comma-separated string in the form
  workspace_path: "",
};

export default function AgentsPage() {
  const [agents, setAgents] = useState([]);
  const [providers, setProviders] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const [agRes, provRes] = await Promise.all([api.get("/agents"), api.get("/providers")]);
    setAgents(agRes.data);
    setProviders(provRes.data);
  }, []);

  useEffect(() => {
    load().catch(() => {});
  }, [load]);

  const set = (field) => (val) => setForm((f) => ({ ...f, [field]: val }));

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY);
    setError("");
    setOpen(true);
  };

  const openEdit = (agent) => {
    setEditing(agent.id);
    setForm({
      name: agent.name ?? "",
      description: agent.description ?? "",
      default_provider_id: agent.default_provider_id ?? "",
      dm_policy: agent.dm_policy ?? "pairing",
      system_prompt: agent.system_prompt ?? "",
      web_search_enabled: agent.web_search_enabled ?? false,
      memory_enabled: agent.memory_enabled ?? true,
      max_history_messages: agent.max_history_messages ?? 20,
      group_requires_mention: agent.group_requires_mention ?? true,
      code_execution_enabled: agent.code_execution_enabled ?? false,
      active: agent.active ?? true,
      allowed_user_ids: (agent.allowed_user_ids ?? []).join(", "),
      workspace_path: agent.workspace_path ?? "",
    });
    setError("");
    setOpen(true);
  };

  const save = async () => {
    if (!form.name.trim()) { setError("Name is required"); return; }
    setError("");
    try {
      const allowedIds = form.allowed_user_ids
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
        .map(Number)
        .filter((n) => !isNaN(n));

      const payload = {
        name: form.name.trim(),
        description: form.description,
        default_provider_id: form.default_provider_id || null,
        workspace_path: form.workspace_path || null,
        dm_policy: form.dm_policy,
        allowed_user_ids: allowedIds,
        group_requires_mention: form.group_requires_mention,
        active: form.active,
        system_prompt: form.system_prompt || null,
        web_search_enabled: form.web_search_enabled,
        memory_enabled: form.memory_enabled,
        max_history_messages: Number(form.max_history_messages) || 20,
        code_execution_enabled: form.code_execution_enabled,
      };

      if (editing) {
        await api.put(`/agents/${editing}`, payload);
      } else {
        await api.post("/agents", payload);
      }
      setOpen(false);
      await load();
    } catch (e) {
      setError(e.response?.data?.detail || "Save failed");
    }
  };

  const remove = async (id, e) => {
    e.stopPropagation();
    if (!window.confirm("Delete this agent? All associated bindings will stop working.")) return;
    try {
      await api.delete(`/agents/${id}`);
      await load();
    } catch (e) {
      alert(e.response?.data?.detail || "Delete failed");
    }
  };

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", mb: 2 }}>
        <Box>
          <Typography variant="h5">Agents</Typography>
          <Typography variant="body2" color="text.secondary">
            AI agents receive messages and respond using the configured LLM provider
          </Typography>
        </Box>
        <Button variant="contained" onClick={openCreate}>+ Add Agent</Button>
      </Box>

      {/* Table */}
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>DM Policy</TableCell>
              <TableCell>Provider</TableCell>
              <TableCell>Web Search</TableCell>
              <TableCell>Memory</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {agents.map((a) => {
              const prov = providers.find((p) => p.id === a.default_provider_id);
              return (
                <TableRow
                  key={a.id}
                  hover
                  sx={{ cursor: "pointer" }}
                  onClick={() => openEdit(a)}
                >
                  <TableCell>
                    <Typography variant="body2" fontWeight={600}>{a.name}</Typography>
                    {a.description && (
                      <Typography variant="caption" color="text.secondary" noWrap sx={{ maxWidth: 220, display: "block" }}>
                        {a.description}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Chip size="small" label={a.dm_policy} color={DM_COLOR[a.dm_policy] ?? "default"} />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">{prov?.name ?? <em style={{ opacity: 0.5 }}>none</em>}</Typography>
                  </TableCell>
                  <TableCell>{a.web_search_enabled ? "✓" : "—"}</TableCell>
                  <TableCell>{a.memory_enabled ? "✓" : "—"}</TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={a.active ? "Active" : "Inactive"}
                      color={a.active ? "success" : "default"}
                    />
                  </TableCell>
                  <TableCell align="right" onClick={(e) => e.stopPropagation()}>
                    <Tooltip title="Edit">
                      <IconButton size="small" onClick={() => openEdit(a)}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete">
                      <IconButton size="small" color="error" onClick={(e) => remove(a.id, e)}>
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              );
            })}
            {agents.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 5, color: "text.secondary" }}>
                  No agents yet — click "+ Add Agent" to create your first one.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Create / Edit modal */}
      <AppModal open={open} onClose={() => setOpen(false)}>
        <Typography variant="h6" sx={{ mb: 0.5 }}>
          {editing ? "Edit Agent" : "Create Agent"}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {editing ? "Update agent configuration" : "Configure a new AI agent"}
        </Typography>

        {/* Basic info */}
        <TextField
          fullWidth required label="Name" margin="normal"
          value={form.name} onChange={(e) => set("name")(e.target.value)}
          placeholder="e.g. Support Bot"
        />
        <TextField
          fullWidth label="Description" margin="normal"
          value={form.description} onChange={(e) => set("description")(e.target.value)}
          placeholder="What does this agent do?"
        />
        <TextField
          fullWidth multiline minRows={4} label="System Prompt" margin="normal"
          value={form.system_prompt} onChange={(e) => set("system_prompt")(e.target.value)}
          placeholder={"You are a helpful assistant...\nRespond concisely and professionally."}
          helperText="Instructions sent to the LLM before every conversation"
        />

        {/* Provider + DM Policy */}
        <Box sx={{ display: "flex", gap: 2 }}>
          <FormControl fullWidth margin="normal">
            <InputLabel>Default Provider</InputLabel>
            <Select
              value={form.default_provider_id}
              label="Default Provider"
              onChange={(e) => set("default_provider_id")(e.target.value)}
            >
              <MenuItem value=""><em>— None (use config default) —</em></MenuItem>
              {providers.map((p) => (
                <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl fullWidth margin="normal">
            <InputLabel>DM Policy</InputLabel>
            <Select
              value={form.dm_policy}
              label="DM Policy"
              onChange={(e) => set("dm_policy")(e.target.value)}
            >
              {DM_POLICIES.map((p) => (
                <MenuItem key={p.value} value={p.value}>{p.label}</MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>

        {/* Memory + History */}
        <Box sx={{ display: "flex", gap: 2 }}>
          <TextField
            fullWidth type="number" label="Max History Messages" margin="normal"
            value={form.max_history_messages}
            onChange={(e) => set("max_history_messages")(e.target.value)}
            inputProps={{ min: 1, max: 200 }}
            helperText="Previous messages sent as context"
          />
          <TextField
            fullWidth label="Allowed User IDs" margin="normal"
            value={form.allowed_user_ids}
            onChange={(e) => set("allowed_user_ids")(e.target.value)}
            placeholder="123456, 789012"
            helperText="Comma-separated Telegram user IDs (for allowlist policy)"
          />
        </Box>

        <TextField
          fullWidth label="Workspace Path" margin="normal"
          value={form.workspace_path}
          onChange={(e) => set("workspace_path")(e.target.value)}
          placeholder="/workspace/my-agent"
          helperText="Optional local directory for file operations"
        />

        {/* Toggles */}
        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, mt: 1, mb: 0.5 }}>
          {[
            ["web_search_enabled", "Web Search"],
            ["memory_enabled", "Memory"],
            ["group_requires_mention", "Require @mention in groups"],
            ["code_execution_enabled", "Code Execution"],
            ["active", "Active"],
          ].map(([key, label]) => (
            <FormControlLabel
              key={key}
              sx={{ mr: 2 }}
              control={
                <Switch
                  checked={Boolean(form[key])}
                  onChange={(e) => set(key)(e.target.checked)}
                  size="small"
                />
              }
              label={<Typography variant="body2">{label}</Typography>}
            />
          ))}
        </Box>

        {error && (
          <Typography color="error" variant="body2" sx={{ mt: 1 }}>
            {error}
          </Typography>
        )}

        <Box sx={{ display: "flex", gap: 2, mt: 2 }}>
          <Button variant="contained" onClick={save}>
            {editing ? "Save Changes" : "Create Agent"}
          </Button>
          <Button variant="outlined" onClick={() => setOpen(false)}>Cancel</Button>
        </Box>
      </AppModal>
    </Box>
  );
}
