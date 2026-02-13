import React, { useState } from "react";
import { Box, Button, Container, Paper, Typography } from "@mui/material";
import { useNavigate } from "react-router-dom";
import FormInput from "../components/FormInput";
import NotificationBar from "../components/NotificationBar";
import api from "../services/api";

export default function LoginPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [notify, setNotify] = useState({ open: false, message: "", severity: "error" });

  const submit = async () => {
    if (!username || !password) {
      setNotify({ open: true, message: "Username and password are required", severity: "error" });
      return;
    }

    try {
      const res = await api.post("/auth/login", { username, password });
      localStorage.setItem("jwt", res.data.access_token);
      navigate("/");
    } catch {
      setNotify({ open: true, message: "Authentication failed", severity: "error" });
    }
  };

  return (
    <Container maxWidth="sm" sx={{ py: 8 }}>
      <Paper sx={{ p: 4 }}>
        <Typography variant="h5" gutterBottom>
          Admin Login
        </Typography>
        <Box>
          <FormInput label="Email / Username" value={username} onChange={setUsername} required />
          <FormInput label="Password" value={password} onChange={setPassword} required type="password" />
          <Button variant="contained" onClick={submit} fullWidth sx={{ mt: 2 }}>
            Sign in
          </Button>
        </Box>
      </Paper>
      <NotificationBar
        open={notify.open}
        message={notify.message}
        severity={notify.severity}
        onClose={() => setNotify((s) => ({ ...s, open: false }))}
      />
    </Container>
  );
}
