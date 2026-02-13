import React from "react";
import { Alert, Snackbar } from "@mui/material";

export default function NotificationBar({ open, message, severity = "info", onClose }) {
  return (
    <Snackbar open={open} autoHideDuration={3000} onClose={onClose}>
      <Alert severity={severity} variant="filled" onClose={onClose}>
        {message}
      </Alert>
    </Snackbar>
  );
}
