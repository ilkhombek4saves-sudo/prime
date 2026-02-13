import React, { useEffect, useState } from "react";
import {
  Card,
  CardContent,
  Chip,
  Grid,
  List,
  ListItem,
  ListItemText,
  Typography,
} from "@mui/material";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import api from "../services/api";
import { useWs } from "../services/wsContext";

function StatCard({ title, value, sub }) {
  return (
    <Card>
      <CardContent>
        <Typography variant="subtitle2" color="text.secondary">
          {title}
        </Typography>
        <Typography variant="h4" sx={{ my: 1 }}>
          {value ?? "—"}
        </Typography>
        {sub && (
          <Typography variant="caption" color="text.secondary">
            {sub}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
}

const WS_COLOR = {
  connected: "success",
  connecting: "warning",
  reconnecting: "warning",
  auth_failed: "error",
};

export default function DashboardPage() {
  const { status, recentEvents } = useWs();
  const [stats, setStats] = useState({ bots: 0, providers: 0, tasks: 0, sessions: 0 });
  const [taskChart, setTaskChart] = useState([]);

  useEffect(() => {
    const load = async () => {
      try {
        const [bots, providers, tasks, sessions] = await Promise.all([
          api.get("/bots").then((r) => r.data),
          api.get("/providers").then((r) => r.data),
          api.get("/tasks").then((r) => r.data),
          api.get("/sessions").then((r) => r.data),
        ]);

        setStats({
          bots: bots.filter((b) => b.active).length,
          providers: providers.filter((p) => p.active).length,
          tasks: tasks.length,
          sessions: sessions.length,
        });

        // Build chart buckets from task timestamps
        const buckets = {};
        tasks.forEach((t) => {
          const label = t.created_at
            ? new Date(t.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
            : "?";
          if (!buckets[label]) buckets[label] = { time: label, success: 0, failed: 0 };
          if (t.status === "success") buckets[label].success += 1;
          else if (t.status === "failed") buckets[label].failed += 1;
        });
        setTaskChart(Object.values(buckets).slice(-12));
      } catch {
        // backend may be starting up
      }
    };
    load();
  }, []);

  // Bump task counter on live WS task events
  useEffect(() => {
    const last = recentEvents[0];
    if (last?.event?.startsWith("task.")) {
      setStats((prev) => ({ ...prev, tasks: prev.tasks + 1 }));
    }
  }, [recentEvents]);

  return (
    <Grid container spacing={2}>
      <Grid item xs={12} md={3}>
        <StatCard title="Active Bots" value={stats.bots} />
      </Grid>
      <Grid item xs={12} md={3}>
        <StatCard title="Active Providers" value={stats.providers} />
      </Grid>
      <Grid item xs={12} md={3}>
        <StatCard title="Total Tasks" value={stats.tasks} />
      </Grid>
      <Grid item xs={12} md={3}>
        <Card>
          <CardContent>
            <Typography variant="subtitle2" color="text.secondary">
              Gateway
            </Typography>
            <Chip
              label={status}
              color={WS_COLOR[status] ?? "default"}
              size="small"
              sx={{ mt: 1, textTransform: "uppercase" }}
            />
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={12} md={8}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Tasks (last 12 periods)
            </Typography>
            {taskChart.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No task data yet.
              </Typography>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={taskChart}>
                  <Line type="monotone" dataKey="success" stroke="#2e7d32" name="Success" />
                  <Line type="monotone" dataKey="failed" stroke="#d32f2f" name="Failed" />
                  <CartesianGrid stroke="#ccc" strokeDasharray="3 3" />
                  <XAxis dataKey="time" />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={12} md={4}>
        <Card sx={{ height: "100%" }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Live Events
            </Typography>
            {recentEvents.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                Waiting for events…
              </Typography>
            ) : (
              <List dense disablePadding>
                {recentEvents.slice(0, 10).map((evt, i) => (
                  <ListItem key={i} disableGutters>
                    <ListItemText
                      primary={evt.event}
                      secondary={
                        evt.data ? JSON.stringify(evt.data).slice(0, 60) : undefined
                      }
                      primaryTypographyProps={{ variant: "caption", fontWeight: 600 }}
                      secondaryTypographyProps={{ variant: "caption" }}
                    />
                  </ListItem>
                ))}
              </List>
            )}
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );
}
