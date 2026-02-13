import React, { useEffect, useState } from "react";
import { Box, Typography } from "@mui/material";
import DataTable from "../components/DataTable";
import api from "../services/api";

export default function PluginsPage() {
  const [rows, setRows] = useState([]);

  useEffect(() => {
    api.get("/plugins").then((res) => setRows(res.data)).catch(() => {});
  }, []);

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>
        Plugins
      </Typography>
      <DataTable
        columns={[
          { key: "name", label: "Name" },
          { key: "description", label: "Description" },
          { key: "permissions", label: "Permissions" },
        ]}
        rows={rows.map((r) => ({ ...r, permissions: (r.permissions || []).join(", ") }))}
      />
    </Box>
  );
}
