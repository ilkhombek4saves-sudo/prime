import React, { createContext, useContext, useEffect, useRef, useState } from "react";
import { destroyGatewayWS, getGatewayWS } from "./ws";

const WsContext = createContext(null);

export function WsProvider({ children }) {
  const [status, setStatus] = useState("disconnected");
  const [recentEvents, setRecentEvents] = useState([]);
  const wsRef = useRef(null);

  useEffect(() => {
    const ws = getGatewayWS();
    wsRef.current = ws;

    const offStatus = ws.onStatus((s) => setStatus(s));
    const offEvent = (evt) => {
      setRecentEvents((prev) => [evt, ...prev].slice(0, 100));
    };
    const unsubEvent = ws.onEvent(offEvent);

    ws.connect();

    return () => {
      offStatus();
      unsubEvent();
    };
  }, []);

  return (
    <WsContext.Provider value={{ status, recentEvents, ws: wsRef }}>
      {children}
    </WsContext.Provider>
  );
}

/** Hook — use inside any component under WsProvider */
export function useWs() {
  const ctx = useContext(WsContext);
  if (!ctx) throw new Error("useWs must be used inside WsProvider");
  return ctx;
}

/** Standalone hook for connection status only (lighter) */
export function useWsStatus() {
  const { status } = useWs();
  return status;
}
