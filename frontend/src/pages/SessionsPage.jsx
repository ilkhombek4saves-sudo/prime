import React, { useEffect, useState } from "react";
import { Box, Typography } from "@mui/material";
import DataTable from "../components/DataTable";
import api from "../services/api";

export default function SessionsPage() {
  const [rows, setRows] = useState([]);

  useEffect(() => {
    api.get("/sessions").then((res) => setRows(res.data)).catch(() => {});
  }, []);

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>
        Sessions
      </Typography>
      <DataTable
        columns={[
          { key: "id", label: "ID" },
          { key: "status", label: "Status" },
          { key: "created_at", label: "Created" },
        ]}
        rows={rows}
      />
    </Box>
  );
}
