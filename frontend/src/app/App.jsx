import React, { useMemo, useState } from "react";
import { AppBar, Box, Button, Chip, Container, IconButton, Toolbar, Typography } from "@mui/material";
import { Link, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import MenuIcon from "@mui/icons-material/Menu";
import Brightness4Icon from "@mui/icons-material/Brightness4";
import Brightness7Icon from "@mui/icons-material/Brightness7";
import LoginPage from "../pages/LoginPage";
import DashboardPage from "../pages/DashboardPage";
import BotsPage from "../pages/BotsPage";
import ProvidersPage from "../pages/ProvidersPage";
import PluginsPage from "../pages/PluginsPage";
import SessionsPage from "../pages/SessionsPage";
import TasksPage from "../pages/TasksPage";
import UsersPage from "../pages/UsersPage";
import SettingsPage from "../pages/SettingsPage";
import ChatPage from "../pages/ChatPage";
import KnowledgeBasePage from "../pages/KnowledgeBasePage";
import OrganizationsPage from "../pages/OrganizationsPage";
import AgentsPage from "../pages/AgentsPage";
import BindingsPage from "../pages/BindingsPage";
import GlobalSearch from "../components/GlobalSearch";
import ErrorBoundary from "../components/ErrorBoundary";
import RequireRole from "../components/RequireRole";
import { useColorMode } from "../styles/theme";
import { WsProvider, useWsStatus } from "../services/wsContext";
import { destroyGatewayWS } from "../services/ws";

const menuItems = [
  ["Dashboard", "/"],
  ["Agents", "/agents"],
  ["Bindings", "/bindings"],
  ["Bots", "/bots"],
  ["Providers", "/providers"],
  ["Plugins", "/plugins"],
  ["Knowledge Bases", "/knowledge-bases"],
  ["Sessions", "/sessions"],
  ["Tasks", "/tasks"],
  ["Users", "/users"],
  ["Organizations", "/organizations"],
  ["Settings", "/settings"],
  ["Chat", "/chat"],
];

const STATUS_COLOR = {
  connected: "success",
  connecting: "warning",
  reconnecting: "warning",
  auth_failed: "error",
  disconnected: "default",
  unauthenticated: "default",
};

function WsStatusChip() {
  const status = useWsStatus();
  return (
    <Chip
      size="small"
      label={status}
      color={STATUS_COLOR[status] ?? "default"}
      sx={{ textTransform: "uppercase", fontSize: "0.65rem" }}
    />
  );
}

function AuthenticatedApp() {
  const { mode, toggleMode } = useColorMode();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");

  const links = useMemo(
    () => menuItems.filter(([label]) => label.toLowerCase().includes(search.toLowerCase())),
    [search]
  );

  const handleLogout = () => {
    localStorage.removeItem("jwt");
    destroyGatewayWS();
    navigate("/login");
  };

  return (
    <>
      <AppBar position="sticky">
        <Toolbar sx={{ gap: 2 }}>
          <MenuIcon />
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            MultiBot Admin
          </Typography>
          <WsStatusChip />
          <GlobalSearch value={search} onChange={setSearch} />
          <IconButton color="inherit" onClick={toggleMode}>
            {mode === "dark" ? <Brightness7Icon /> : <Brightness4Icon />}
          </IconButton>
          <Button color="inherit" onClick={handleLogout}>
            Logout
          </Button>
        </Toolbar>
      </AppBar>

      <Box sx={{ borderBottom: 1, borderColor: "divider", px: 2, py: 1, display: "flex", gap: 1, flexWrap: "wrap" }}>
        {links.map(([label, path]) => (
          <Button key={path} component={Link} to={path} size="small" variant="outlined">
            {label}
          </Button>
        ))}
      </Box>

      <Container sx={{ py: 3 }}>
        <ErrorBoundary>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/bots" element={<BotsPage />} />
            <Route path="/providers" element={<ProvidersPage />} />
            <Route path="/plugins" element={<PluginsPage />} />
            <Route path="/sessions" element={<SessionsPage />} />
            <Route path="/tasks" element={<TasksPage />} />
            <Route path="/users" element={<RequireRole roles={["admin"]}><UsersPage /></RequireRole>} />
            <Route path="/settings" element={<RequireRole roles={["admin"]}><SettingsPage /></RequireRole>} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/knowledge-bases" element={<KnowledgeBasePage />} />
            <Route path="/organizations" element={<RequireRole roles={["admin"]}><OrganizationsPage /></RequireRole>} />
            <Route path="/agents" element={<AgentsPage />} />
            <Route path="/bindings" element={<BindingsPage />} />
          </Routes>
        </ErrorBoundary>
      </Container>
    </>
  );
}

export default function App() {
  const token = localStorage.getItem("jwt");

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="*"
        element={
          token ? (
            <WsProvider>
              <AuthenticatedApp />
            </WsProvider>
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />
    </Routes>
  );
}
