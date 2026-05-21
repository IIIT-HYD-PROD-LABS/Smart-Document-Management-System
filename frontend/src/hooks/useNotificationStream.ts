"use client";

import { useEffect, useRef, useState } from "react";
import Cookies from "js-cookie";
import { useCurrentClient } from "@/stores/currentClientStore";
import type { NotificationEnvelope } from "@/types/compliance";

const MAX_BUFFER = 50;

/**
 * Subscribe to /ws/notifications and buffer the most recent N envelopes.
 *
 * Auto-reconnects with exponential backoff on disconnect. Honors the
 * activeClientId from the Zustand store — switches re-open the socket
 * with the new client_id query parameter.
 *
 * Returns:
 *   - notifications: most-recent-first buffer
 *   - status: 'connecting' | 'open' | 'closed' | 'error'
 *   - markAllRead: clear unread count without closing the socket
 *   - unreadCount: number of items received since last markAllRead
 */
export function useNotificationStream() {
    const activeClientId = useCurrentClient(s => s.activeClientId);
    const [notifications, setNotifications] = useState<NotificationEnvelope[]>([]);
    const [status, setStatus] = useState<"connecting" | "open" | "closed" | "error">(
        "closed"
    );
    const [unreadCount, setUnreadCount] = useState(0);
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectAttempts = useRef(0);
    const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

    useEffect(() => {
        if (typeof window === "undefined") return;
        if (activeClientId === null) return;

        let cancelled = false;

        const connect = () => {
            if (cancelled) return;
            // Tokens are stored as cookies (see lib/api.ts, AuthContext) under
            // key "token" — NOT in localStorage. Reading the wrong source
            // silently kept this WebSocket from ever opening.
            const token = Cookies.get("token") ?? null;
            if (!token) return;

            const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
            const wsBase = apiBase.replace(/^http/, "ws");
            const url = `${wsBase}/ws/notifications?token=${encodeURIComponent(token)}&client_id=${activeClientId}`;
            const ws = new WebSocket(url);
            wsRef.current = ws;
            setStatus("connecting");

            ws.onopen = () => {
                if (cancelled) return;
                setStatus("open");
                reconnectAttempts.current = 0;
            };
            ws.onmessage = (ev) => {
                try {
                    const env = JSON.parse(ev.data) as NotificationEnvelope;
                    setNotifications(prev => [env, ...prev].slice(0, MAX_BUFFER));
                    setUnreadCount(c => c + 1);
                } catch {
                    /* ignore malformed */
                }
            };
            ws.onerror = () => {
                if (cancelled) return;
                setStatus("error");
            };
            ws.onclose = () => {
                if (cancelled) return;
                setStatus("closed");
                // Exponential backoff reconnect — capped at 30s
                const delay = Math.min(1000 * 2 ** reconnectAttempts.current, 30000);
                reconnectAttempts.current += 1;
                reconnectTimer.current = setTimeout(connect, delay);
            };
        };

        connect();

        return () => {
            cancelled = true;
            if (reconnectTimer.current) {
                clearTimeout(reconnectTimer.current);
                reconnectTimer.current = null;
            }
            if (wsRef.current) {
                wsRef.current.close();
                wsRef.current = null;
            }
        };
    }, [activeClientId]);

    const markAllRead = () => setUnreadCount(0);

    return { notifications, status, unreadCount, markAllRead };
}
