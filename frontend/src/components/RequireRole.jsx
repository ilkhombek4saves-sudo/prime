import React from "react";
import { Box, Paper, Typography } from "@mui/material";
import LockIcon from "@mui/icons-material/Lock";

/**
 * Route-level RBAC guard.
 * Reads user role from JWT payload stored in localStorage.
 * Usage: <RequireRole roles={["admin"]}><AdminPage /></RequireRole>
 */
export default function RequireRole({ roles, children }) {
  const token = localStorage.getItem("jwt");
  let userRole = "user";

  if (token) {
    try {
      const payload = JSON.parse(atob(token.split(".")[1]));
      userRole = payload.role || "user";
    } catch {
      // malformed token — treat as regular user
    }
  }

  if (roles && !roles.includes(userRole)) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: 300 }}>
        <Paper sx={{ p: 4, textAlign: "center", maxWidth: 400 }}>
          <LockIcon sx={{ fontSize: 48, color: "warning.main", mb: 2 }} />
          <Typography variant="h6" gutterBottom>
            Access Denied
          </Typography>
          <Typography variant="body2" color="text.secondary">
            You don't have permission to view this page. Contact your administrator.
          </Typography>
        </Paper>
      </Box>
    );
  }

  return children;
}
