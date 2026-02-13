import React from "react";
import { TextField } from "@mui/material";

export default function GlobalSearch({ value, onChange }) {
  return <TextField size="small" label="Global Search" value={value} onChange={(e) => onChange(e.target.value)} />;
}
