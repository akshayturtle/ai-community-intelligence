import { useEffect, useRef, useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000/api/ws/dashboard";

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const queryClient = useQueryClient();
  const [connected, setConnected] = useState(false);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout>>(undefined);

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(WS_URL);

      ws.onopen = () => {
        setConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "heartbeat") return;

          // Invalidate relevant queries based on event type
          if (data.type === "new_post" || data.type === "post_update") {
            queryClient.invalidateQueries({ queryKey: ["overview"] });
            queryClient.invalidateQueries({ queryKey: ["pulse"] });
            queryClient.invalidateQueries({ queryKey: ["topics"] });
          } else if (data.type === "new_topic" || data.type === "topic_update") {
            queryClient.invalidateQueries({ queryKey: ["overview"] });
            queryClient.invalidateQueries({ queryKey: ["pulse"] });
            queryClient.invalidateQueries({ queryKey: ["debates"] });
            queryClient.invalidateQueries({ queryKey: ["topics"] });
          } else if (data.type === "new_news") {
            queryClient.invalidateQueries({ queryKey: ["overview"] });
            queryClient.invalidateQueries({ queryKey: ["news"] });
          } else if (data.type === "scraper_complete") {
            queryClient.invalidateQueries({ queryKey: ["overview"] });
            queryClient.invalidateQueries({ queryKey: ["health"] });
          }
        } catch {
          // Ignore parse errors
        }
      };

      ws.onclose = () => {
        setConnected(false);
        // Reconnect after 5s
        reconnectTimeout.current = setTimeout(connect, 5000);
      };

      ws.onerror = () => {
        ws.close();
      };

      wsRef.current = ws;
    } catch {
      // WebSocket not available, retry
      reconnectTimeout.current = setTimeout(connect, 5000);
    }
  }, [queryClient]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimeout.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { connected };
}
