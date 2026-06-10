"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import type { ToolDefinition } from "@/types/api";

// ── Types ────────────────────────────────────────────────────────

/** A single entry in the call log */
export interface CallLogEntry {
  id: string;
  toolName: string;
  arguments: Record<string, unknown>;
  response: CallResponse;
  timestamp: number;
}

/** Response from a tool call */
export interface CallResponse {
  content: Array<{ type: string; text?: string }>;
  isError?: boolean;
  request_id?: string;
}

/** WebSocket message from the server */
interface WSMessage {
  jsonrpc: "2.0";
  id?: number;
  method?: string;
  params?: unknown;
  result?: unknown;
  error?: { code: number; message: string; data?: unknown };
}

/** Hook return type */
export interface UsePlaygroundReturn {
  tools: ToolDefinition[];
  selectedTool: ToolDefinition | null;
  response: CallResponse | null;
  callLog: CallLogEntry[];
  isConnected: boolean;
  reconnectAttempt: number;
  error: string | null;
  selectTool: (tool: ToolDefinition | null) => void;
  callTool: (toolName: string, args: Record<string, unknown>) => Promise<CallResponse>;
  clearLog: () => void;
  clearResponse: () => void;
  connect: () => void;
  disconnect: () => void;
}

// ── Helpers ──────────────────────────────────────────────────────

function normalizeTool(raw: Record<string, unknown>): Record<string, unknown> {
  return {
    input_schema: raw.inputSchema ?? raw.input_schema ?? {},
    ...raw,
  };
}

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(
    new RegExp(`(?:^|;\\s*)${name}=([^;]*)`),
  );
  return match ? decodeURIComponent(match[1] ?? "") : null;
}

function buildWsUrl(slug: string, accessToken?: string): string {
  const base =
    process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const wsBase = base.replace(/^http/, "ws");
  // Use the explicitly passed token (preferred) or fall back to document.cookie
  // for backward compatibility with non-SSR flows.
  const token = accessToken ?? getCookie("access_token");
  const params = token ? `?token=${encodeURIComponent(token)}` : "";
  return `${wsBase}/ws/playground/${encodeURIComponent(slug)}${params}`;
}

let globalRequestId = 0;
function nextRequestId(): number {
  globalRequestId += 1;
  return globalRequestId;
}

// ── Hook ─────────────────────────────────────────────────────────

const MAX_BACKOFF_MS = 30_000;
const INITIAL_BACKOFF_MS = 1_000;

export function usePlayground(serverSlug: string, accessToken?: string): UsePlaygroundReturn {
  const [tools, setTools] = useState<ToolDefinition[]>([]);
  const [selectedTool, setSelectedTool] = useState<ToolDefinition | null>(
    null,
  );
  const [response, setResponse] = useState<CallResponse | null>(null);
  const [callLog, setCallLog] = useState<CallLogEntry[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const pendingRequestsRef = useRef<
    Map<number, { resolve: (v: CallResponse) => void; reject: (e: Error) => void }>
  >(new Map());

  // ── Message handler ──────────────────────────────────────────

  const handleMessage = useCallback((event: MessageEvent) => {
    let msg: WSMessage;
    try {
      msg = JSON.parse(event.data) as WSMessage;
    } catch {
      return;
    }

    // tools/list response (could be a response to our request or a server push)
    if (msg.method === "notifications/tools/list" || (msg.id !== undefined && msg.result !== undefined && !pendingRequestsRef.current.has(msg.id))) {
      const result = msg.result ?? msg.params;
      if (result && typeof result === "object" && "tools" in (result as Record<string, unknown>)) {
        const toolList = (result as { tools: unknown }).tools;
        if (Array.isArray(toolList)) {
          setTools(toolList.map((t) => normalizeTool(t as Record<string, unknown>)) as unknown as ToolDefinition[]);
        }
      }
      return;
    }

    // Response to a pending request (tools/call)
    if (msg.id !== undefined && pendingRequestsRef.current.has(msg.id)) {
      const pending = pendingRequestsRef.current.get(msg.id);
      pendingRequestsRef.current.delete(msg.id);

      if (msg.error) {
        pending?.reject(
          new Error(msg.error.message ?? "Tool call failed"),
        );
      } else {
        pending?.resolve(msg.result as CallResponse);
      }
      return;
    }

    // tools/list as response to our list request
    if (msg.id !== undefined && msg.result !== undefined) {
      const pending = pendingRequestsRef.current.get(msg.id);
      if (pending) {
        pendingRequestsRef.current.delete(msg.id);
        pending.resolve(msg.result as CallResponse);
      }
    }
  }, []);

  // ── Connect ──────────────────────────────────────────────────

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    console.log("[DBG] connect() called, creating new WebSocket");
    const url = buildWsUrl(serverSlug, accessToken);
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) return;
      // Guard: only act if this WebSocket is still the active one
      if (wsRef.current !== ws) return;
      console.log("[DBG] WebSocket onopen fired", { readyState: ws.readyState, url: ws.url });
      setIsConnected(true);
      setReconnectAttempt(0);
      setError(null);

      // Request tool list on connect
      const listId = nextRequestId();
      const listRequest: WSMessage = {
        jsonrpc: "2.0",
        id: listId,
        method: "tools/list",
        params: {},
      };
      ws.send(JSON.stringify(listRequest));

      // Store a resolver for the list response
      pendingRequestsRef.current.set(listId, {
        resolve: (result: CallResponse) => {
          // The result should contain tools
          const data = result as unknown as Record<string, unknown>;
          if (data && typeof data === "object" && "tools" in data) {
            const toolList = (data as { tools: unknown }).tools;
            if (Array.isArray(toolList)) {
              setTools(toolList.map((t) => normalizeTool(t as Record<string, unknown>)) as unknown as ToolDefinition[]);
            }
          }
        },
        reject: () => {
          // Non-critical — tools may not be available yet
        },
      });
    };

    ws.onmessage = handleMessage;

    ws.onerror = (_event) => {
      console.log("[DBG] WebSocket onerror fired", { readyState: ws.readyState, url: ws.url });
      // onclose will handle reconnection
    };

    ws.onclose = (event) => {
      if (!mountedRef.current) return;
      // Guard: only act if this WebSocket is still the active one
      if (wsRef.current !== ws) return;
      console.log("[DBG] WebSocket onclose fired", { code: event.code, reason: event.reason, wasClean: event.wasClean, readyState: ws.readyState });
      wsRef.current = null;
      setIsConnected(false);

      // If the close was intentional (code 1000), don't reconnect
      if (event.code === 1000) return;

      // Reject all pending requests
      for (const [id, pending] of pendingRequestsRef.current) {
        pending.reject(new Error("WebSocket closed"));
        pendingRequestsRef.current.delete(id);
      }

      // Exponential backoff reconnect
      setReconnectAttempt((prev) => {
        const next = prev + 1;
        const delay = Math.min(
          INITIAL_BACKOFF_MS * Math.pow(2, prev),
          MAX_BACKOFF_MS,
        );

        if (mountedRef.current) {
          setError(`Disconnected. Reconnecting in ${Math.round(delay / 1000)}s...`);
          reconnectTimerRef.current = setTimeout(() => {
            if (mountedRef.current) connect();
          }, delay);
        }

        return next;
      });
    };
  }, [serverSlug, handleMessage, accessToken]);

  // ── Disconnect ───────────────────────────────────────────────

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close(1000, "Client disconnect");
      wsRef.current = null;
    }
    setIsConnected(false);
    setReconnectAttempt(0);
    setError(null);

    // Reject all pending requests
    for (const [, pending] of pendingRequestsRef.current) {
      pending.reject(new Error("Disconnected"));
    }
    pendingRequestsRef.current.clear();
  }, []);

  // ── Call tool ────────────────────────────────────────────────

  const callTool = useCallback(
    async (
      toolName: string,
      args: Record<string, unknown>,
    ): Promise<CallResponse> => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        const state = ws ? ws.readyState : "null";
        console.log(`[DBG] callTool: ws is ${state}, throwing`, { toolName, isConnected });
        throw new Error("Not connected to playground");
      }

      console.log(`[DBG] callTool: ws is OPEN, sending tools/call`, { toolName, args });
      const id = nextRequestId();
      const request: WSMessage = {
        jsonrpc: "2.0",
        id,
        method: "tools/call",
        params: { name: toolName, arguments: args },
      };

      return new Promise<CallResponse>((resolve, reject) => {
        pendingRequestsRef.current.set(id, {
          resolve: (result: CallResponse) => {
            // Add to call log
            const entry: CallLogEntry = {
              id: `call-${id}-${Date.now()}`,
              toolName,
              arguments: args,
              response: result,
              timestamp: Date.now(),
            };
            setCallLog((prev) => [...prev, entry]);
            setResponse(result);
            resolve(result);
          },
          reject: (err: Error) => {
            const errorResponse: CallResponse = {
              content: [{ type: "text", text: err.message }],
              isError: true,
            };
            // Add to call log so failed calls appear in history
            const entry: CallLogEntry = {
              id: `call-${id}-${Date.now()}`,
              toolName,
              arguments: args,
              response: errorResponse,
              timestamp: Date.now(),
            };
            setCallLog((prev) => [...prev, entry]);
            setResponse(errorResponse);
            reject(err);
          },
        });

        ws.send(JSON.stringify(request));
      });
    },
    [isConnected],
  );

  // ── Select tool ──────────────────────────────────────────────

  const selectTool = useCallback((tool: ToolDefinition | null) => {
    setSelectedTool(tool);
    setResponse(null);
  }, []);

  // ── Clear helpers ────────────────────────────────────────────

  const clearLog = useCallback(() => {
    setCallLog([]);
  }, []);

  const clearResponse = useCallback(() => {
    setResponse(null);
  }, []);

  // ── Lifecycle ────────────────────────────────────────────────

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    tools,
    selectedTool,
    response,
    callLog,
    isConnected,
    reconnectAttempt,
    error,
    selectTool,
    callTool,
    clearLog,
    clearResponse,
    connect,
    disconnect,
  };
}
