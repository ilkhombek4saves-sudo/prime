import React from "react";
import { TextField } from "@mui/material";

export default function FormInput({ label, value, onChange, required = false, type = "text" }) {
  return (
    <TextField
      fullWidth
      margin="normal"
      required={required}
      label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      type={type}
    />
  );
}
