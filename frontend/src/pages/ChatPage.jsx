import React, { useMemo } from "react";
import { Box, Chip, Paper, Typography } from "@mui/material";
import { useWs } from "../services/wsContext";

export default function ChatPage() {
  const { status, recentEvents } = useWs();

  const rendered = useMemo(
    () =>
      recentEvents.map((event, index) => (
        <Typography key={`${event.event || event.type}-${index}`} sx={{ fontFamily: "monospace", fontSize: 13 }}>
          {JSON.stringify(event)}
        </Typography>
      )),
    [recentEvents]
  );

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>
        Chat Stream
      </Typography>
      <Chip label={`ws: ${status}`} size="small" sx={{ mb: 2, textTransform: "uppercase" }} />
      <Paper sx={{ p: 2, minHeight: 280, maxHeight: 520, overflowY: "auto" }}>
        {rendered.length ? rendered : <Typography color="text.secondary">No events yet</Typography>}
      </Paper>
    </Box>
  );
}
