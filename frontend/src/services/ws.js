const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;
const RECONNECT_FACTOR = 2;

export class GatewayWS {
  constructor() {
    this._ws = null;
    this._stopped = false;
    this._reconnectDelay = RECONNECT_BASE_MS;
    this._reqCounter = 0;
    this._pending = new Map(); // id -> { resolve, reject, timeoutId }
    this._eventHandlers = new Set();
    this._statusHandlers = new Set();
    this._status = "disconnected";
  }

  get status() {
    return this._status;
  }

  _getToken() {
    return localStorage.getItem("jwt");
  }

  _getWsUrl() {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    return `${proto}://${window.location.host}/api/ws/events`;
  }

  _setStatus(status) {
    this._status = status;
    this._statusHandlers.forEach((h) => h(status));
  }

  _nextReqId() {
    return `req-${++this._reqCounter}-${Date.now()}`;
  }

  connect() {
    if (this._stopped) return;
    const token = this._getToken();
    if (!token) {
      this._setStatus("unauthenticated");
      return;
    }

    this._setStatus("connecting");
    const ws = new WebSocket(this._getWsUrl());
    this._ws = ws;

    ws.onmessage = (event) => {
      let msg;
      try {
        msg = JSON.parse(event.data);
      } catch {
        return;
      }
      this._handleMessage(msg);
    };

    ws.onerror = () => {
      // onclose fires after onerror — handle there
    };

    ws.onclose = () => {
      this._ws = null;
      // Reject all in-flight requests
      this._pending.forEach(({ reject, timeoutId }) => {
        clearTimeout(timeoutId);
        reject(new Error("WebSocket disconnected"));
      });
      this._pending.clear();

      if (!this._stopped) {
        this._setStatus("reconnecting");
        setTimeout(() => this.connect(), this._reconnectDelay);
        this._reconnectDelay = Math.min(
          this._reconnectDelay * RECONNECT_FACTOR,
          RECONNECT_MAX_MS
        );
      } else {
        this._setStatus("disconnected");
      }
    };
  }

  _handleMessage(msg) {
    // Step 1: server sends challenge, we respond with connect + JWT
    if (msg.type === "connect.challenge") {
      const token = this._getToken();
      if (!token) {
        this._ws?.close();
        return;
      }
      this._ws.send(
        JSON.stringify({
          type: "connect",
          token,
          nonce: msg.nonce,
          client: { name: "multibot-admin", version: "0.1.0" },
        })
      );
      return;
    }

    // Step 2: server confirms connected
    if (msg.type === "event") {
      if (msg.event === "presence.connected") {
        this._reconnectDelay = RECONNECT_BASE_MS; // reset backoff on success
        this._setStatus("connected");
      }
      this._eventHandlers.forEach((h) => h(msg));
      return;
    }

    // Response to a request
    if (msg.type === "res") {
      const pending = this._pending.get(msg.id);
      if (pending) {
        clearTimeout(pending.timeoutId);
        this._pending.delete(msg.id);
        pending.resolve(msg.result);
      }
      return;
    }

    // Error frame
    if (msg.type === "error") {
      const pending = this._pending.get(msg.id);
      if (pending) {
        clearTimeout(pending.timeoutId);
        this._pending.delete(msg.id);
        pending.reject(new Error(`[${msg.code}] ${msg.message}`));
      } else if (msg.code === "auth_failed" || msg.code === "invalid_nonce") {
        this._setStatus("auth_failed");
        this.stop();
      } else {
        this._eventHandlers.forEach((h) =>
          h({ type: "event", event: "gateway.error", data: msg })
        );
      }
    }
  }

  /**
   * Send a typed request and return a Promise that resolves with the result.
   * @param {string} method - e.g. "health.get", "tasks.list"
   * @param {object} params
   * @param {object} [opts]
   * @param {string} [opts.idempotencyKey] - required for side-effect methods
   * @param {number} [opts.timeoutMs=15000]
   */
  request(method, params = {}, opts = {}) {
    return new Promise((resolve, reject) => {
      if (!this._ws || this._ws.readyState !== WebSocket.OPEN) {
        reject(new Error("WebSocket not connected"));
        return;
      }
      const id = this._nextReqId();
      const timeoutMs = opts.timeoutMs ?? 15000;
      const timeoutId = setTimeout(() => {
        this._pending.delete(id);
        reject(new Error(`Request ${method} timed out after ${timeoutMs}ms`));
      }, timeoutMs);

      this._pending.set(id, { resolve, reject, timeoutId });

      const frame = { type: "req", id, method, params };
      if (opts.idempotencyKey) {
        frame.idempotency_key = opts.idempotencyKey;
      }
      this._ws.send(JSON.stringify(frame));
    });
  }

  /** Subscribe to server-pushed events. Returns an unsubscribe fn. */
  onEvent(handler) {
    this._eventHandlers.add(handler);
    return () => this._eventHandlers.delete(handler);
  }

  /** Subscribe to connection status changes. Returns an unsubscribe fn. */
  onStatus(handler) {
    this._statusHandlers.add(handler);
    return () => this._statusHandlers.delete(handler);
  }

  stop() {
    this._stopped = true;
    this._ws?.close();
  }
}

let _instance = null;

export function getGatewayWS() {
  if (!_instance) {
    _instance = new GatewayWS();
  }
  return _instance;
}

/** Call on logout to tear down the singleton. */
export function destroyGatewayWS() {
  if (_instance) {
    _instance.stop();
    _instance = null;
  }
}
