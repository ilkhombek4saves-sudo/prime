import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  Box, Chip, Paper, Typography, TextField, IconButton, List, ListItem,
  ListItemText, Divider, CircularProgress, Avatar, Drawer, useMediaQuery,
} from "@mui/material";
import SendIcon from "@mui/icons-material/Send";
import SmartToyIcon from "@mui/icons-material/SmartToy";
import PersonIcon from "@mui/icons-material/Person";
import MenuIcon from "@mui/icons-material/Menu";
import AddIcon from "@mui/icons-material/Add";
import { useWs } from "../services/wsContext";
import api from "../services/api";

const SESSION_KEY = "chat_sessions";

function MessageBubble({ role, content }) {
  const isUser = role === "user";
  return (
    <Box sx={{ display: "flex", mb: 1.5, justifyContent: isUser ? "flex-end" : "flex-start" }}>
      {!isUser && (
        <Avatar sx={{ bgcolor: "primary.main", mr: 1, width: 32, height: 32 }}>
          <SmartToyIcon sx={{ fontSize: 18 }} />
        </Avatar>
      )}
      <Paper
        elevation={1}
        sx={{
          p: 1.5,
          maxWidth: "70%",
          bgcolor: isUser ? "primary.main" : "grey.100",
          color: isUser ? "primary.contrastText" : "text.primary",
          borderRadius: isUser ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          fontFamily: content && content.includes("```") ? "monospace" : "inherit",
          fontSize: 14,
        }}
      >
        {content || "..."}
      </Paper>
      {isUser && (
        <Avatar sx={{ bgcolor: "secondary.main", ml: 1, width: 32, height: 32 }}>
          <PersonIcon sx={{ fontSize: 18 }} />
        </Avatar>
      )}
    </Box>
  );
}

export default function ChatPage() {
  const { status } = useWs();
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const messagesEndRef = useRef(null);
  const isMobile = useMediaQuery("(max-width:768px)");

  // Load sessions
  useEffect(() => {
    api.get("/sessions?limit=50").then((res) => {
      const items = res.data?.items || res.data || [];
      setSessions(items);
      if (items.length > 0 && !activeSessionId) {
        setActiveSessionId(items[0].id);
      }
    }).catch(() => {});
  }, []);

  // Load messages for active session
  useEffect(() => {
    if (!activeSessionId) return;
    api.get(`/sessions/${activeSessionId}`).then((res) => {
      const data = res.data;
      setMessages(data?.messages || []);
    }).catch(() => setMessages([]));
  }, [activeSessionId]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");

    const userMsg = { role: "user", content: text, ts: new Date().toISOString() };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await api.post("/sessions/chat", {
        session_id: activeSessionId,
        message: text,
      });
      const reply = res.data;
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: reply?.response || reply?.content || JSON.stringify(reply), ts: new Date().toISOString() },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${err.response?.data?.detail || err.message}`, ts: new Date().toISOString() },
      ]);
    } finally {
      setLoading(false);
    }
  }, [input, loading, activeSessionId]);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const createSession = async () => {
    try {
      const res = await api.post("/sessions", { title: `Chat ${new Date().toLocaleString()}` });
      const newSession = res.data;
      setSessions((prev) => [newSession, ...prev]);
      setActiveSessionId(newSession.id);
      setMessages([]);
    } catch {
      // fallback: use local session
      const localId = `local-${Date.now()}`;
      const newSession = { id: localId, title: `Chat ${new Date().toLocaleString()}` };
      setSessions((prev) => [newSession, ...prev]);
      setActiveSessionId(localId);
      setMessages([]);
    }
  };

  const sessionList = (
    <Box sx={{ width: isMobile ? 260 : "100%", p: 1 }}>
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 1 }}>
        <Typography variant="subtitle2" color="text.secondary">Sessions</Typography>
        <IconButton size="small" onClick={createSession}><AddIcon /></IconButton>
      </Box>
      <Divider sx={{ mb: 1 }} />
      <List dense disablePadding>
        {sessions.map((s) => (
          <ListItem
            key={s.id}
            button
            selected={s.id === activeSessionId}
            onClick={() => { setActiveSessionId(s.id); setDrawerOpen(false); }}
            sx={{ borderRadius: 1, mb: 0.5 }}
          >
            <ListItemText
              primary={s.title || s.id?.slice(0, 8)}
              primaryTypographyProps={{ fontSize: 13, noWrap: true }}
            />
          </ListItem>
        ))}
        {sessions.length === 0 && (
          <Typography variant="body2" color="text.secondary" sx={{ p: 1 }}>
            No sessions yet. Create one to start chatting.
          </Typography>
        )}
      </List>
    </Box>
  );

  return (
    <Box sx={{ display: "flex", height: "calc(100vh - 120px)" }}>
      {/* Sidebar - sessions list */}
      {isMobile ? (
        <Drawer open={drawerOpen} onClose={() => setDrawerOpen(false)}>
          {sessionList}
        </Drawer>
      ) : (
        <Paper sx={{ width: 240, mr: 2, overflow: "auto", flexShrink: 0 }}>
          {sessionList}
        </Paper>
      )}

      {/* Main chat area */}
      <Box sx={{ flex: 1, display: "flex", flexDirection: "column" }}>
        {/* Header */}
        <Box sx={{ display: "flex", alignItems: "center", mb: 1 }}>
          {isMobile && (
            <IconButton onClick={() => setDrawerOpen(true)} sx={{ mr: 1 }}><MenuIcon /></IconButton>
          )}
          <Typography variant="h6">Chat</Typography>
          <Chip
            label={status}
            size="small"
            color={status === "connected" ? "success" : "default"}
            sx={{ ml: 1, textTransform: "uppercase" }}
          />
        </Box>

        {/* Messages */}
        <Paper sx={{ flex: 1, p: 2, overflow: "auto", mb: 1, bgcolor: "background.default" }}>
          {messages.length === 0 && (
            <Box sx={{ textAlign: "center", mt: 8 }}>
              <SmartToyIcon sx={{ fontSize: 48, color: "text.disabled" }} />
              <Typography color="text.secondary" sx={{ mt: 1 }}>
                Send a message to start the conversation
              </Typography>
            </Box>
          )}
          {messages.map((msg, i) => (
            <MessageBubble key={i} role={msg.role} content={msg.content} />
          ))}
          {loading && (
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, ml: 5 }}>
              <CircularProgress size={16} />
              <Typography variant="body2" color="text.secondary">Thinking...</Typography>
            </Box>
          )}
          <div ref={messagesEndRef} />
        </Paper>

        {/* Input */}
        <Paper sx={{ p: 1, display: "flex", alignItems: "flex-end", gap: 1 }}>
          <TextField
            fullWidth
            multiline
            maxRows={4}
            placeholder="Type a message... (Enter to send, Shift+Enter for new line)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
            size="small"
            sx={{ "& .MuiOutlinedInput-root": { borderRadius: 2 } }}
          />
          <IconButton
            color="primary"
            onClick={handleSend}
            disabled={!input.trim() || loading}
          >
            <SendIcon />
          </IconButton>
        </Paper>
      </Box>
    </Box>
  );
}
