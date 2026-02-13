import React, { useEffect, useState } from "react";
import { Box, Button, MenuItem, TextField, Typography } from "@mui/material";
import api from "../services/api";

export default function SettingsPage() {
  const [settings, setSettings] = useState({ app_name: "", app_env: "", theme: "system", locale: "en" });

  useEffect(() => {
    api.get("/settings").then((res) => setSettings((prev) => ({ ...prev, ...res.data }))).catch(() => {});
  }, []);

  const importConfig = async () => {
    await api.post("/settings/import-config");
  };

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>
        Settings
      </Typography>
      <Typography>App: {settings.app_name}</Typography>
      <Typography>Environment: {settings.app_env}</Typography>
      <TextField
        select
        sx={{ mt: 2, minWidth: 200 }}
        label="Locale"
        value={settings.locale}
        onChange={(e) => setSettings((s) => ({ ...s, locale: e.target.value }))}
      >
        <MenuItem value="en">English</MenuItem>
        <MenuItem value="ru">Русский</MenuItem>
      </TextField>
      <Box sx={{ mt: 2 }}>
        <Button variant="outlined" onClick={importConfig}>
          Import Config Files
        </Button>
      </Box>
    </Box>
  );
}
