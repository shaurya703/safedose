import {
  AlertTriangle,
  CircleAlert,
  CircleCheck,
  ExternalLink,
  Pill,
  Search,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useState } from "react";
import { checkMedicine, getMeta, getStats, listAlerts } from "./api";
import type { CheckResult, NSQRecord, Stats } from "./types";

const CATEGORY_LABEL: Record<string, string> = {
  spurious: "Spurious / counterfeit",
  contamination: "Contamination",
  dissolution: "Dissolution failure",
  assay: "Wrong drug content",
  labelling: "Mislabelling",
  physical: "Physical defect",
  other: "Other",
};

export default function App() {
  const [tab, setTab] = useState<"check" | "browse">("check");
  const [disclaimer, setDisclaimer] = useState("");

  useEffect(() => {
    getMeta().then((m) => setDisclaimer(m.disclaimer)).catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2 font-display text-lg font-bold">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary text-white">
              <ShieldCheck className="h-4.5 w-4.5" aria-hidden="true" />
            </span>
            SafeDose
          </div>
          <nav className="flex gap-1" aria-label="Main">
            {(["check", "browse"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                aria-pressed={tab === t}
                className={`rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 motion-reduce:transition-none ${
                  tab === t ? "bg-cyan-100 text-primary-dark" : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                {t === "check" ? "Check a medicine" : "Browse flagged"}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-4 pb-24">
        {tab === "check" ? <CheckTab /> : <BrowseTab />}
      </main>

      <footer className="border-t border-slate-200 bg-white py-6 text-center text-sm text-slate-600">
        <p className="mx-auto max-w-2xl px-4">{disclaimer}</p>
      </footer>
    </div>
  );
}

function CheckTab() {
  const [drug, setDrug] = useState("");
  const [batch, setBatch] = useState("");
  const [result, setResult] = useState<CheckResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    getStats().then(setStats).catch(() => {});
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!drug.trim() && !batch.trim()) {
      setError("Enter a medicine name and/or a batch number.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setResult(await checkMedicine(drug, batch));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="py-10">
      <div className="mx-auto max-w-xl text-center">
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
          Is your medicine batch <span className="text-primary">flagged?</span>
        </h1>
        <p className="mt-3 text-slate-700">
          India's drug regulator (CDSCO) publishes monthly lists of medicine
          batches found substandard, spurious or misbranded — buried in PDFs no
          one reads. Check yours against them in seconds.
        </p>
      </div>

      <form
        onSubmit={submit}
        className="mx-auto mt-8 max-w-xl rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block">
            <span className="text-sm font-semibold text-slate-700">Medicine name</span>
            <div className="relative mt-1">
              <Pill className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
              <input
                value={drug}
                onChange={(e) => setDrug(e.target.value)}
                placeholder="e.g. Pantoprazole 40mg"
                className="w-full rounded-xl border border-slate-300 bg-white p-3 pl-9 text-base focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              />
            </div>
          </label>
          <label className="block">
            <span className="text-sm font-semibold text-slate-700">Batch number</span>
            <input
              value={batch}
              onChange={(e) => setBatch(e.target.value)}
              placeholder="printed on the strip / box"
              className="mt-1 w-full rounded-xl border border-slate-300 bg-white p-3 text-base focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            />
          </label>
        </div>
        <button
          type="submit"
          disabled={loading}
          className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-primary py-3 font-semibold text-white transition-colors duration-200 hover:bg-primary-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:opacity-50 motion-reduce:transition-none"
        >
          <Search className="h-4 w-4" aria-hidden="true" />
          {loading ? "Checking…" : "Check this medicine"}
        </button>
        <p className="mt-2 text-center text-xs text-slate-500">
          The batch number matters most — a flag applies to one batch, not the whole brand.
        </p>
        {error && <p className="mt-3 text-center text-sm text-rose-600">{error}</p>}
      </form>

      {result && <ResultCard result={result} />}

      {stats && !result && (
        <div className="mx-auto mt-8 max-w-xl rounded-xl border border-slate-200 bg-white p-4 text-center text-sm text-slate-600">
          Dataset: <strong>{stats.total_records}</strong> flagged batches ·{" "}
          <strong>{stats.distinct_drugs}</strong> distinct medicines ·{" "}
          <strong>{stats.distinct_manufacturers}</strong> manufacturers, from CDSCO
          alert {stats.alerts_ingested.join(", ")}.
        </div>
      )}
    </div>
  );
}

function ResultCard({ result }: { result: CheckResult }) {
  const style = {
    danger: { Icon: AlertTriangle, box: "border-rose-300 bg-rose-50", chip: "bg-rose-600", text: "text-rose-900" },
    caution: { Icon: CircleAlert, box: "border-amber-300 bg-amber-50", chip: "bg-amber-500", text: "text-amber-900" },
    clear: { Icon: CircleCheck, box: "border-emerald-300 bg-emerald-50", chip: "bg-emerald-600", text: "text-emerald-900" },
  }[result.severity];

  return (
    <div className={`mx-auto mt-6 max-w-xl rounded-2xl border p-5 ${style.box}`} role="status">
      <div className="flex items-start gap-3">
        <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-full text-white ${style.chip}`}>
          <style.Icon className="h-5 w-5" aria-hidden="true" />
        </span>
        <div>
          <h2 className={`font-display text-lg font-bold ${style.text}`}>{result.headline}</h2>
          <p className="mt-1 text-sm text-slate-700">{result.detail}</p>
        </div>
      </div>

      {result.batch_matches.length > 0 && (
        <FlaggedList title="Matched flagged batch" records={result.batch_matches} />
      )}
      {result.drug_matches.length > 0 && (
        <FlaggedList
          title={`Other flagged batches of this medicine (${result.drug_matches.length})`}
          records={result.drug_matches}
        />
      )}

      <p className="mt-4 text-xs text-slate-500">
        Checked against {result.dataset_period}. Always confirm on{" "}
        <a href="https://cdsco.gov.in" target="_blank" rel="noopener noreferrer" className="underline hover:text-primary">
          cdsco.gov.in
        </a>{" "}
        and consult a pharmacist.
      </p>
    </div>
  );
}

function FlaggedList({ title, records }: { title: string; records: NSQRecord[] }) {
  return (
    <div className="mt-4">
      <h3 className="text-xs font-bold uppercase tracking-wide text-slate-600">{title}</h3>
      <ul className="mt-2 space-y-2">
        {records.slice(0, 6).map((r) => (
          <li key={r.id} className="rounded-xl border border-slate-200 bg-white p-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold">{r.drug_name}</span>
              {r.is_spurious && (
                <span className="rounded-full bg-rose-600 px-2 py-0.5 text-[11px] font-bold uppercase text-white">
                  Spurious
                </span>
              )}
            </div>
            <div className="mt-1 grid gap-x-4 gap-y-0.5 text-slate-600 sm:grid-cols-2">
              <span>Batch: <strong className="text-slate-800">{r.batch_no}</strong></span>
              <span>{CATEGORY_LABEL[r.failure_category] ?? r.failure_category}: {r.failure_reason}</span>
              {r.manufacturer && <span className="sm:col-span-2">Maker: {r.manufacturer}</span>}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function BrowseTab() {
  const [records, setRecords] = useState<NSQRecord[]>([]);
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [spuriousOnly, setSpuriousOnly] = useState(false);
  const [count, setCount] = useState(0);

  useEffect(() => {
    const t = setTimeout(() => {
      listAlerts({ q: q || undefined, category: category || undefined, spurious: spuriousOnly || undefined })
        .then((r) => {
          setRecords(r.records);
          setCount(r.count);
        })
        .catch(() => {});
    }, q ? 250 : 0);
    return () => clearTimeout(t);
  }, [q, category, spuriousOnly]);

  return (
    <div className="py-8">
      <h1 className="text-2xl font-bold">Flagged medicine batches</h1>
      <p className="mt-1 text-sm text-slate-700">
        Every batch in our dataset that CDSCO found Not of Standard Quality, spurious or misbranded.
      </p>

      <div className="mt-4 flex flex-col gap-3 sm:flex-row">
        <label className="relative w-full sm:max-w-xs">
          <span className="sr-only">Search flagged medicines</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search drug or manufacturer…"
            className="w-full rounded-xl border border-slate-300 bg-white p-3 pl-9 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          />
        </label>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          aria-label="Filter by failure type"
          className="cursor-pointer rounded-xl border border-slate-300 bg-white p-3 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          <option value="">All failure types</option>
          {Object.entries(CATEGORY_LABEL).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-slate-700">
          <input
            type="checkbox"
            checked={spuriousOnly}
            onChange={(e) => setSpuriousOnly(e.target.checked)}
            className="h-4 w-4 accent-rose-600"
          />
          Spurious only
        </label>
      </div>

      <p className="mt-4 text-xs text-slate-500">{count} batches</p>
      <ul className="mt-2 space-y-2">
        {records.map((r) => (
          <li key={r.id} className="rounded-xl border border-slate-200 bg-white p-4 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold">{r.drug_name}</span>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-slate-600">
                {CATEGORY_LABEL[r.failure_category] ?? r.failure_category}
              </span>
              {r.is_spurious && (
                <span className="rounded-full bg-rose-600 px-2 py-0.5 text-[11px] font-bold uppercase text-white">Spurious</span>
              )}
            </div>
            <div className="mt-1 grid gap-x-4 text-slate-600 sm:grid-cols-2">
              <span>Batch: <strong className="text-slate-800">{r.batch_no}</strong></span>
              <span>Reason: {r.failure_reason}</span>
              {r.manufacturer && <span className="sm:col-span-2">Maker: {r.manufacturer}</span>}
              <span className="sm:col-span-2">
                <a href={r.source_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-primary underline-offset-2 hover:underline">
                  {r.source_alert} <ExternalLink className="h-3 w-3" aria-hidden="true" />
                </a>
              </span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
