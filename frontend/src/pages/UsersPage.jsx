import React, { useEffect, useState } from "react";
import { Box, Button, Typography } from "@mui/material";
import FormInput from "../components/FormInput";
import DataTable from "../components/DataTable";
import api from "../services/api";

export default function UsersPage() {
  const [rows, setRows] = useState([]);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const load = () => api.get("/users").then((res) => setRows(res.data));

  useEffect(() => {
    load().catch(() => {});
  }, []);

  const create = async () => {
    await api.post("/users", { username, password, role: "user" });
    setUsername("");
    setPassword("");
    await load();
  };

  return (
    <Box>
      <Typography variant="h5">Users</Typography>
      <Box sx={{ display: "flex", gap: 2, my: 2 }}>
        <FormInput label="Username" value={username} onChange={setUsername} required />
        <FormInput label="Password" value={password} onChange={setPassword} required type="password" />
        <Button variant="contained" onClick={create}>
          Create
        </Button>
      </Box>
      <DataTable
        columns={[
          { key: "id", label: "ID" },
          { key: "username", label: "Username" },
          { key: "role", label: "Role" },
        ]}
        rows={rows}
      />
    </Box>
  );
}
