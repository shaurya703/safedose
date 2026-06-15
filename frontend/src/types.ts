export interface NSQRecord {
  id: string;
  drug_name: string;
  batch_no: string;
  manufacturer: string | null;
  mfg_date: string | null;
  expiry_date: string | null;
  failure_reason: string;
  failure_category: string;
  is_spurious: boolean;
  tested_by: string | null;
  source_alert: string;
  source_url: string;
  alert_period: string;
}

export interface CheckResult {
  query_drug: string | null;
  query_batch: string | null;
  match_type: "batch_flagged" | "drug_flagged" | "clear";
  severity: "danger" | "caution" | "clear";
  headline: string;
  detail: string;
  batch_matches: NSQRecord[];
  drug_matches: NSQRecord[];
  checked_alerts: number;
  dataset_period: string;
}

export interface Stats {
  total_records: number;
  spurious_count: number;
  distinct_drugs: number;
  distinct_manufacturers: number;
  alerts_ingested: string[];
  last_alert_period: string | null;
  by_category: Record<string, number>;
  generated_on: string;
}
