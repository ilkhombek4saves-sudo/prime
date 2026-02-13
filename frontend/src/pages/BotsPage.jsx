import React, { useEffect, useState } from "react";
import { Box, Button, Switch, Typography } from "@mui/material";
import DataTable from "../components/DataTable";
import AppModal from "../components/AppModal";
import FormInput from "../components/FormInput";
import api from "../services/api";

export default function BotsPage() {
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [token, setToken] = useState("");
  const [active, setActive] = useState(true);

  const load = async () => {
    const res = await api.get("/bots");
    setRows(res.data);
  };

  useEffect(() => {
    load().catch(() => {});
  }, []);

  const save = async () => {
    await api.post("/bots", {
      name,
      token,
      channels: ["telegram"],
      allowed_user_ids: [],
      active,
      provider_defaults: {},
    });
    setOpen(false);
    setName("");
    setToken("");
    await load();
  };

  return (
    <Box>
      <Box sx={{ display: "flex", justifyContent: "space-between", mb: 2 }}>
        <Typography variant="h5">Bots</Typography>
        <Button variant="contained" onClick={() => setOpen(true)}>
          Add
        </Button>
      </Box>
      <DataTable
        columns={[
          { key: "name", label: "Name" },
          { key: "channels", label: "Channels" },
          { key: "active", label: "Active" },
        ]}
        rows={rows.map((r) => ({ ...r, channels: (r.channels || []).join(", "), active: r.active ? "Yes" : "No" }))}
      />

      <AppModal open={open} onClose={() => setOpen(false)}>
        <Typography variant="h6">Create bot</Typography>
        <FormInput label="Name" value={name} onChange={setName} required />
        <FormInput label="Token" value={token} onChange={setToken} required />
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, my: 2 }}>
          <Typography>Active</Typography>
          <Switch checked={active} onChange={(e) => setActive(e.target.checked)} />
        </Box>
        <Button variant="contained" onClick={save}>
          Save
        </Button>
      </AppModal>
    </Box>
  );
}
