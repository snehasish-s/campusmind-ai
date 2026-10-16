"use client";
import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
export function CampusAlerts({ userId }: { userId: string }) {
  const seen = useRef<Set<string> | null>(null);
  const query = useQuery({
    queryKey: ["campus-browser-alerts", userId],
    queryFn: async () => {
      const r = await fetch("/api/notifications", {
        cache: "no-store",
        credentials: "same-origin",
      });
      if (!r.ok) return [];
      return r.json() as Promise<
        { id: string; title: string; message: string }[]
      >;
    },
    refetchInterval: 30000,
  });
  useEffect(() => {
    if (!query.data) return;
    if (!seen.current) {
      seen.current = new Set(query.data.map((n) => n.id));
      return;
    }
    for (const n of query.data) {
      if (
        !seen.current.has(n.id) &&
        "Notification" in window &&
        Notification.permission === "granted" &&
        localStorage.getItem("cm-notifications") === "enabled"
      ) {
        try {
          const alert = new Notification("CampusMind · " + n.title, {
            body: "An official update is available in your campus workspace.",
            tag: n.id,
          });
          alert.onclick = () => {
            window.focus();
            window.location.assign("/app/notifications");
          };
        } catch {
          /* Some mobile browsers only support push via a service worker. */
        }
      }
      seen.current.add(n.id);
    }
  }, [query.data]);
  return null;
}
