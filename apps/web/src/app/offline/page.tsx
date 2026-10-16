"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
type Snapshot = {
  saved_at: string;
  timetable: {
    id: string;
    subject: string;
    weekday: number;
    starts: string;
    ends: string;
    room: string;
    valid_from: string;
    valid_until: string;
  }[];
};
export default function OfflinePage() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      try {
        const saved = localStorage.getItem("cm-offline-timetable");
        if (saved) setSnapshot(JSON.parse(saved));
      } catch {
        localStorage.removeItem("cm-offline-timetable");
      }
    });
    return () => cancelAnimationFrame(frame);
  }, []);
  return (
    <main className="offline-page">
      <h1>Your offline timetable</h1>
      <p>
        This is a saved snapshot. Connect to CampusMind to receive timetable
        changes, notices and current deadlines. Payments and submissions require
        a connection.
      </p>
      {snapshot ? (
        <>
          <p className="hint">
            Saved {new Date(snapshot.saved_at).toLocaleString()}. Check each
            class’s validity dates.
          </p>
          <div className="campus-stack">
            {snapshot.timetable.map((s) => (
              <section className="card card-pad" key={s.id}>
                <h2>{s.subject}</h2>
                <p>
                  {
                    [
                      "Monday",
                      "Tuesday",
                      "Wednesday",
                      "Thursday",
                      "Friday",
                      "Saturday",
                      "Sunday",
                    ][s.weekday]
                  }{" "}
                  · {s.starts}–{s.ends} · {s.room}
                </p>
                <p className="hint">
                  Valid {s.valid_from} to {s.valid_until}
                </p>
              </section>
            ))}
          </div>
          <Button
            variant="outline"
            onClick={() => {
              localStorage.removeItem("cm-offline-timetable");
              setSnapshot(null);
            }}
          >
            Remove saved schedule from this device
          </Button>
        </>
      ) : (
        <p>
          No timetable was saved on this device. When connected, open Today and
          choose “Save timetable on this device”.
        </p>
      )}
      <Button asChild>
        <Link href="/app/today">Reconnect to CampusMind</Link>
      </Button>
    </main>
  );
}
