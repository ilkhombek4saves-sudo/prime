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
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";
import AppModal from "../components/AppModal";
import api from "../services/api";

const CHANNELS = ["telegram", "discord", "slack", "whatsapp", "signal", "web", "api"];

const EMPTY = {
  agent_id: "",
  bot_id: "",
  channel: "telegram",
  account_id: "",
  peer: "",
  priority: 100,
  active: true,
};

export default function BindingsPage() {
  const [bindings, setBindings] = useState([]);
  const [agents, setAgents] = useState([]);
  const [bots, setBots] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState("");

  // Resolve panel
  const [resolveOpen, setResolveOpen] = useState(false);
  const [resolveForm, setResolveForm] = useState({ channel: "telegram", account_id: "", peer: "", bot_id: "" });
  const [resolveResult, setResolveResult] = useState(null);

  const load = useCallback(async () => {
    const [bndRes, agRes, botRes] = await Promise.all([
      api.get("/bindings"),
      api.get("/agents"),
      api.get("/bots"),
    ]);
    setBindings(bndRes.data);
    setAgents(agRes.data);
    setBots(botRes.data);
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

  const openEdit = (b) => {
    setEditing(b.id);
    setForm({
      agent_id: b.agent_id ?? "",
      bot_id: b.bot_id ?? "",
      channel: b.channel ?? "telegram",
      account_id: b.account_id ?? "",
      peer: b.peer ?? "",
      priority: b.priority ?? 100,
      active: b.active ?? true,
    });
    setError("");
    setOpen(true);
  };

  const save = async () => {
    if (!form.agent_id) { setError("Agent is required"); return; }
    if (!form.channel) { setError("Channel is required"); return; }
    setError("");
    try {
      const payload = {
        agent_id: form.agent_id,
        bot_id: form.bot_id || null,
        channel: form.channel,
        account_id: form.account_id.trim() || null,
        peer: form.peer.trim() || null,
        priority: Number(form.priority) || 100,
        active: form.active,
      };
      if (editing) {
        await api.put(`/bindings/${editing}`, payload);
      } else {
        await api.post("/bindings", payload);
      }
      setOpen(false);
      await load();
    } catch (e) {
      setError(e.response?.data?.detail || "Save failed");
    }
  };

  const remove = async (id, e) => {
    e.stopPropagation();
    if (!window.confirm("Delete this binding?")) return;
    try {
      await api.delete(`/bindings/${id}`);
      await load();
    } catch (e) {
      alert(e.response?.data?.detail || "Delete failed");
    }
  };

  const resolve = async () => {
    setResolveResult(null);
    try {
      const params = new URLSearchParams({ channel: resolveForm.channel });
      if (resolveForm.account_id) params.append("account_id", resolveForm.account_id);
      if (resolveForm.peer) params.append("peer", resolveForm.peer);
      if (resolveForm.bot_id) params.append("bot_id", resolveForm.bot_id);
      const res = await api.get(`/bindings/resolve?${params}`);
      setResolveResult(res.data);
    } catch (e) {
      setResolveResult({ matched: false, reason: e.response?.data?.detail || "error" });
    }
  };

  const agentName = (id) => agents.find((a) => a.id === id)?.name ?? "…";
  const botName = (id) => id ? (bots.find((b) => b.id === id)?.name ?? id.slice(0, 8) + "…") : "—";

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", mb: 2 }}>
        <Box>
          <Typography variant="h5">Bindings</Typography>
          <Typography variant="body2" color="text.secondary">
            Route incoming messages to agents based on channel, bot, and peer
          </Typography>
        </Box>
        <Box sx={{ display: "flex", gap: 1 }}>
          <Button variant="outlined" onClick={() => { setResolveOpen(true); setResolveResult(null); }}>
            Test Resolve
          </Button>
          <Button variant="contained" onClick={openCreate}>+ Add Binding</Button>
        </Box>
      </Box>

      {/* Table */}
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Agent</TableCell>
              <TableCell>Bot</TableCell>
              <TableCell>Channel</TableCell>
              <TableCell>
                <Tooltip title="Specific Telegram bot username / channel ID to match">
                  <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                    Account ID <HelpOutlineIcon sx={{ fontSize: 14, opacity: 0.5 }} />
                  </Box>
                </Tooltip>
              </TableCell>
              <TableCell>
                <Tooltip title="Specific chat ID or username to match (more specific = higher priority)">
                  <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                    Peer <HelpOutlineIcon sx={{ fontSize: 14, opacity: 0.5 }} />
                  </Box>
                </Tooltip>
              </TableCell>
              <TableCell>Priority</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {bindings.map((b) => (
              <TableRow
                key={b.id}
                hover
                sx={{ cursor: "pointer" }}
                onClick={() => openEdit(b)}
              >
                <TableCell>
                  <Typography variant="body2" fontWeight={600}>
                    {agentName(b.agent_id)}
                  </Typography>
                </TableCell>
                <TableCell>{botName(b.bot_id)}</TableCell>
                <TableCell>
                  <Chip size="small" label={b.channel} variant="outlined" />
                </TableCell>
                <TableCell sx={{ fontFamily: "monospace", fontSize: "0.8rem" }}>
                  {b.account_id ?? <span style={{ opacity: 0.4 }}>any</span>}
                </TableCell>
                <TableCell sx={{ fontFamily: "monospace", fontSize: "0.8rem" }}>
                  {b.peer ?? <span style={{ opacity: 0.4 }}>any</span>}
                </TableCell>
                <TableCell>{b.priority}</TableCell>
                <TableCell>
                  <Chip
                    size="small"
                    label={b.active ? "Active" : "Inactive"}
                    color={b.active ? "success" : "default"}
                  />
                </TableCell>
                <TableCell align="right" onClick={(e) => e.stopPropagation()}>
                  <Tooltip title="Edit">
                    <IconButton size="small" onClick={() => openEdit(b)}>
                      <EditIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Delete">
                    <IconButton size="small" color="error" onClick={(e) => remove(b.id, e)}>
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
            {bindings.length === 0 && (
              <TableRow>
                <TableCell colSpan={8} align="center" sx={{ py: 5, color: "text.secondary" }}>
                  No bindings yet — click "+ Add Binding" to route messages to an agent.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Routing legend */}
      <Paper variant="outlined" sx={{ mt: 2, p: 2 }}>
        <Typography variant="subtitle2" sx={{ mb: 0.5 }}>Routing logic</Typography>
        <Typography variant="caption" color="text.secondary" component="div">
          When a message arrives, the best matching binding wins.
          Specificity score: <strong>peer match +4</strong>, <strong>account_id match +2</strong>,
          <strong> bot match +1</strong>. Ties broken by <strong>priority</strong> (higher wins),
          then creation date.
        </Typography>
      </Paper>

      {/* Create / Edit modal */}
      <AppModal open={open} onClose={() => setOpen(false)}>
        <Typography variant="h6" sx={{ mb: 0.5 }}>
          {editing ? "Edit Binding" : "Create Binding"}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          Leave Account ID and Peer empty to match all messages on the channel.
        </Typography>

        {/* Agent + Bot */}
        <Box sx={{ display: "flex", gap: 2 }}>
          <FormControl fullWidth margin="normal" required error={!form.agent_id && !!error}>
            <InputLabel>Agent *</InputLabel>
            <Select
              value={form.agent_id}
              label="Agent *"
              onChange={(e) => set("agent_id")(e.target.value)}
            >
              {agents.length === 0 && (
                <MenuItem disabled value="">No agents — create one first</MenuItem>
              )}
              {agents.map((a) => (
                <MenuItem key={a.id} value={a.id}>
                  {a.name}
                  {!a.active && <Chip size="small" label="inactive" sx={{ ml: 1 }} />}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl fullWidth margin="normal">
            <InputLabel>Bot</InputLabel>
            <Select
              value={form.bot_id}
              label="Bot"
              onChange={(e) => set("bot_id")(e.target.value)}
            >
              <MenuItem value=""><em>— Any bot —</em></MenuItem>
              {bots.map((b) => (
                <MenuItem key={b.id} value={b.id}>{b.name}</MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>

        {/* Channel + Priority */}
        <Box sx={{ display: "flex", gap: 2 }}>
          <FormControl fullWidth margin="normal" required>
            <InputLabel>Channel *</InputLabel>
            <Select
              value={form.channel}
              label="Channel *"
              onChange={(e) => set("channel")(e.target.value)}
            >
              {CHANNELS.map((c) => (
                <MenuItem key={c} value={c}>{c}</MenuItem>
              ))}
            </Select>
          </FormControl>

          <TextField
            fullWidth type="number" label="Priority" margin="normal"
            value={form.priority}
            onChange={(e) => set("priority")(e.target.value)}
            inputProps={{ min: 0, max: 1000 }}
            helperText="Higher = preferred when multiple bindings match"
          />
        </Box>

        {/* Account ID + Peer */}
        <TextField
          fullWidth label="Account ID" margin="normal"
          value={form.account_id}
          onChange={(e) => set("account_id")(e.target.value)}
          placeholder="e.g. @MyBot or 123456789"
          helperText="Telegram bot username or numeric account to match (leave blank = any)"
        />
        <TextField
          fullWidth label="Peer" margin="normal"
          value={form.peer}
          onChange={(e) => set("peer")(e.target.value)}
          placeholder="e.g. -100123456789 or @username"
          helperText="Specific chat/group/user to route to this agent (leave blank = any)"
        />

        <FormControlLabel
          sx={{ mt: 1 }}
          control={
            <Switch
              checked={form.active}
              onChange={(e) => set("active")(e.target.checked)}
            />
          }
          label="Active"
        />

        {error && (
          <Typography color="error" variant="body2" sx={{ mt: 1 }}>
            {error}
          </Typography>
        )}

        <Box sx={{ display: "flex", gap: 2, mt: 2 }}>
          <Button variant="contained" onClick={save}>
            {editing ? "Save Changes" : "Create Binding"}
          </Button>
          <Button variant="outlined" onClick={() => setOpen(false)}>Cancel</Button>
        </Box>
      </AppModal>

      {/* Test Resolve modal */}
      <AppModal open={resolveOpen} onClose={() => setResolveOpen(false)}>
        <Typography variant="h6" sx={{ mb: 1 }}>Test Binding Resolution</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          Simulate an incoming message to see which agent would handle it.
        </Typography>

        <Box sx={{ display: "flex", gap: 2 }}>
          <FormControl fullWidth margin="normal">
            <InputLabel>Channel</InputLabel>
            <Select
              value={resolveForm.channel}
              label="Channel"
              onChange={(e) => setResolveForm((f) => ({ ...f, channel: e.target.value }))}
            >
              {CHANNELS.map((c) => <MenuItem key={c} value={c}>{c}</MenuItem>)}
            </Select>
          </FormControl>
          <FormControl fullWidth margin="normal">
            <InputLabel>Bot</InputLabel>
            <Select
              value={resolveForm.bot_id}
              label="Bot"
              onChange={(e) => setResolveForm((f) => ({ ...f, bot_id: e.target.value }))}
            >
              <MenuItem value=""><em>— None —</em></MenuItem>
              {bots.map((b) => <MenuItem key={b.id} value={b.id}>{b.name}</MenuItem>)}
            </Select>
          </FormControl>
        </Box>

        <TextField
          fullWidth label="Account ID" margin="normal"
          value={resolveForm.account_id}
          onChange={(e) => setResolveForm((f) => ({ ...f, account_id: e.target.value }))}
          placeholder="e.g. @MyBot"
        />
        <TextField
          fullWidth label="Peer" margin="normal"
          value={resolveForm.peer}
          onChange={(e) => setResolveForm((f) => ({ ...f, peer: e.target.value }))}
          placeholder="e.g. -100123456789"
        />

        <Button variant="contained" sx={{ mt: 1 }} onClick={resolve}>
          Resolve
        </Button>

        {resolveResult && (
          <Paper
            variant="outlined"
            sx={{
              mt: 2, p: 2,
              borderColor: resolveResult.matched ? "success.main" : "error.main",
            }}
          >
            {resolveResult.matched ? (
              <>
                <Typography color="success.main" fontWeight={600}>✓ Match found</Typography>
                <Typography variant="body2" sx={{ mt: 0.5 }}>
                  Agent: <strong>{agentName(resolveResult.agent_id)}</strong>
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Binding ID: {resolveResult.binding_id}
                </Typography>
              </>
            ) : (
              <>
                <Typography color="error.main" fontWeight={600}>✗ No match</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                  Reason: {resolveResult.reason}
                </Typography>
              </>
            )}
          </Paper>
        )}
      </AppModal>
    </Box>
  );
}
