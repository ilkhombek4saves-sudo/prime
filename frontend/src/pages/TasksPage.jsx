import React, { useEffect, useState } from "react";
import { Box, Button, Typography } from "@mui/material";
import DataTable from "../components/DataTable";
import api from "../services/api";

export default function TasksPage() {
  const [rows, setRows] = useState([]);

  const load = () => api.get("/tasks").then((res) => setRows(res.data));

  useEffect(() => {
    load().catch(() => {});
  }, []);

  const retry = async (task) => {
    await api.post(`/tasks/${task.id}/retry`);
    await load();
  };

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>
        Tasks
      </Typography>
      <DataTable
        columns={[
          { key: "id", label: "ID" },
          { key: "status", label: "Status" },
          { key: "created_at", label: "Created" },
        ]}
        rows={rows}
        onRowClick={retry}
      />
      <Typography variant="caption" sx={{ mt: 1, display: "block" }}>
        Click row to retry
      </Typography>
      <Button sx={{ mt: 2 }} onClick={load}>Refresh</Button>
    </Box>
  );
}
