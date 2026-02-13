import React, { useEffect, useState } from "react";
import { Box, Button, Typography } from "@mui/material";
import DataTable from "../components/DataTable";
import AppModal from "../components/AppModal";
import FormInput from "../components/FormInput";
import api from "../services/api";

export default function ProvidersPage() {
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [type, setType] = useState("OpenAI");
  const [apiBase, setApiBase] = useState("");

  const load = async () => {
    const res = await api.get("/providers");
    setRows(res.data);
  };

  useEffect(() => {
    load().catch(() => {});
  }, []);

  const save = async () => {
    await api.post("/providers", {
      name,
      type,
      active: true,
      config: {
        api_key: "env://API_KEY",
        api_base: apiBase,
        default_model: "default",
        models: { default: { max_tokens: 4096 } },
      },
    });
    setOpen(false);
    setName("");
    setApiBase("");
    await load();
  };

  return (
    <Box>
      <Box sx={{ display: "flex", justifyContent: "space-between", mb: 2 }}>
        <Typography variant="h5">Providers</Typography>
        <Button variant="contained" onClick={() => setOpen(true)}>
          Add
        </Button>
      </Box>
      <DataTable
        columns={[
          { key: "name", label: "Name" },
          { key: "type", label: "Type" },
          { key: "active", label: "Active" },
        ]}
        rows={rows.map((r) => ({ ...r, active: r.active ? "Yes" : "No" }))}
      />

      <AppModal open={open} onClose={() => setOpen(false)}>
        <Typography variant="h6">Create provider</Typography>
        <FormInput label="Name" value={name} onChange={setName} required />
        <FormInput label="Type" value={type} onChange={setType} required />
        <FormInput label="API Base URL" value={apiBase} onChange={setApiBase} />
        <Button variant="contained" onClick={save}>
          Save
        </Button>
      </AppModal>
    </Box>
  );
}
