import type { CheckResult, NSQRecord, Stats } from "./types";

async function req<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const b = await res.json();
      if (b?.error?.message) msg = b.error.message;
    } catch {
      /* keep generic */
    }
    throw new Error(msg);
  }
  return res.json();
}

export const checkMedicine = (drug: string, batch: string) => {
  const qs = new URLSearchParams();
  if (drug.trim()) qs.set("drug", drug.trim());
  if (batch.trim()) qs.set("batch", batch.trim());
  return req<CheckResult>(`/api/check?${qs}`);
};

export const getStats = () => req<Stats>("/api/stats");

export const listAlerts = (params: { q?: string; category?: string; spurious?: boolean }) => {
  const qs = new URLSearchParams();
  if (params.q) qs.set("q", params.q);
  if (params.category) qs.set("category", params.category);
  if (params.spurious) qs.set("spurious", "true");
  return req<{ count: number; records: NSQRecord[] }>(`/api/alerts?${qs}`);
};

export const getMeta = () => req<{ disclaimer: string }>("/api/meta");
