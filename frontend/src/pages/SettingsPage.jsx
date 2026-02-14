import React, { useEffect, useRef, useState } from "react";
import {
  Alert, Box, Button, Divider, MenuItem, Paper, Snackbar, TextField, Typography,
} from "@mui/material";
import UploadIcon from "@mui/icons-material/Upload";
import DownloadIcon from "@mui/icons-material/Download";
import SaveIcon from "@mui/icons-material/Save";
import api from "../services/api";

export default function SettingsPage() {
  const [settings, setSettings] = useState({
    app_name: "", app_env: "", theme: "system", locale: "en",
  });
  const [loading, setLoading] = useState(true);
  const [snackbar, setSnackbar] = useState({ open: false, message: "", severity: "success" });
  const fileInputRef = useRef(null);

  useEffect(() => {
    setLoading(true);
    api.get("/settings")
      .then((res) => setSettings((prev) => ({ ...prev, ...res.data })))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const showMessage = (message, severity = "success") => {
    setSnackbar({ open: true, message, severity });
  };

  const saveSettings = async () => {
    try {
      await api.patch("/settings", {
        locale: settings.locale,
        theme: settings.theme,
      });
      showMessage("Settings saved successfully.");
    } catch (err) {
      showMessage(err.response?.data?.detail || "Failed to save settings.", "error");
    }
  };

  const exportConfig = async () => {
    try {
      const res = await api.get("/settings/export-config", { responseType: "blob" });
      const url = URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = `prime-config-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      showMessage("Config exported.");
    } catch (err) {
      showMessage(err.response?.data?.detail || "Failed to export config.", "error");
    }
  };

  const importConfig = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const config = JSON.parse(text);
      await api.post("/settings/import-config", config);
      showMessage("Config imported successfully. Some changes may require restart.");
      // Reload settings
      const res = await api.get("/settings");
      setSettings((prev) => ({ ...prev, ...res.data }));
    } catch (err) {
      showMessage(err.response?.data?.detail || "Failed to import config. Check file format.", "error");
    }
    // Reset file input
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 3 }}>Settings</Typography>

      {/* Application Info */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>Application</Typography>
        <Box sx={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          <Box>
            <Typography variant="body2" color="text.secondary">App Name</Typography>
            <Typography variant="body1">{settings.app_name || "Prime"}</Typography>
          </Box>
          <Box>
            <Typography variant="body2" color="text.secondary">Environment</Typography>
            <Typography variant="body1" sx={{ textTransform: "capitalize" }}>
              {settings.app_env || "development"}
            </Typography>
          </Box>
        </Box>
      </Paper>

      {/* Preferences */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>Preferences</Typography>
        <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap", alignItems: "flex-start" }}>
          <TextField
            select
            label="Language"
            value={settings.locale}
            onChange={(e) => setSettings((s) => ({ ...s, locale: e.target.value }))}
            sx={{ minWidth: 200 }}
          >
            <MenuItem value="en">English</MenuItem>
            <MenuItem value="ru">Русский</MenuItem>
          </TextField>
          <TextField
            select
            label="Theme"
            value={settings.theme}
            onChange={(e) => setSettings((s) => ({ ...s, theme: e.target.value }))}
            sx={{ minWidth: 200 }}
          >
            <MenuItem value="system">System</MenuItem>
            <MenuItem value="light">Light</MenuItem>
            <MenuItem value="dark">Dark</MenuItem>
          </TextField>
        </Box>
        <Box sx={{ mt: 2 }}>
          <Button variant="contained" startIcon={<SaveIcon />} onClick={saveSettings}>
            Save Preferences
          </Button>
        </Box>
      </Paper>

      {/* Config Management */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>Configuration</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Export or import the full platform configuration as JSON.
        </Typography>
        <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
          <Button variant="outlined" startIcon={<DownloadIcon />} onClick={exportConfig}>
            Export Config
          </Button>
          <Button variant="outlined" startIcon={<UploadIcon />} onClick={() => fileInputRef.current?.click()}>
            Import Config
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            hidden
            onChange={importConfig}
          />
        </Box>
      </Paper>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert
          severity={snackbar.severity}
          onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
