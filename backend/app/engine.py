"""Matching engine: given a medicine name and/or batch number, decide whether
it appears on a CDSCO NSQ alert.

Design choices that matter for a *safety* tool:

- A flag is on a specific BATCH. An exact (normalized) batch match is the
  strong signal and is reported as danger.
- Short batch numbers ("0081") can collide across unrelated drugs, so an
  exact batch hit is only called a confident batch-flag when the drug name
  is also plausibly similar; otherwise it is surfaced as a caution with the
  matched record shown, never hidden.
- "Not found" never means "safe" — it means "not in this snapshot." The
  copy and the API both say so, because over-reassurance in a drug-safety
  tool is the dangerous failure mode.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from .parser import normalize_batch
from .schemas import CheckResult, MatchType, NSQRecord

_STOPWORDS = {
    "tablets", "tablet", "capsules", "capsule", "injection", "injectable",
    "ip", "bp", "usp", "oral", "solution", "suspension", "syrup", "mg", "ml",
    "gel", "cream", "ointment", "and", "for", "of", "the", "drops", "sodium",
    "hydrochloride", "hcl", "sulphate", "sulfate", "dihydrate", "gastro",
    "resistant", "er", "sr", "xr", "film", "coated", "dispersible",
}


def drug_tokens(name: str) -> set[str]:
    """Salt/molecule tokens, dropping dosage-form noise and bracketed brands."""
    core = re.sub(r"\(.*?\)", " ", name or "")          # drop "(Brand Name)"
    words = re.findall(r"[a-z]+", core.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def drug_similarity(a: str, b: str) -> float:
    ta, tb = drug_tokens(a), drug_tokens(b)
    if not ta or not tb:
        return 0.0
    jaccard = len(ta & tb) / len(ta | tb)
    seq = SequenceMatcher(None, a.lower(), b.lower()).ratio()
    return max(jaccard, seq * 0.9)


DRUG_MATCH_THRESHOLD = 0.45


def check(
    records: list[NSQRecord],
    drug: str | None,
    batch: str | None,
    alerts_count: int,
    dataset_period: str,
) -> CheckResult:
    drug = (drug or "").strip()
    batch = (batch or "").strip()
    nbatch = normalize_batch(batch) if batch else ""

    batch_hits: list[NSQRecord] = []
    if nbatch:
        batch_hits = [r for r in records if r.batch_no_normalized == nbatch]

    # Drug-name matches (other flagged batches of the same medicine).
    drug_hits: list[NSQRecord] = []
    if drug:
        scored = [(drug_similarity(drug, r.drug_name), r) for r in records]
        drug_hits = [r for s, r in sorted(scored, key=lambda x: -x[0])
                     if s >= DRUG_MATCH_THRESHOLD]

    if batch_hits:
        # Does any exact-batch hit also look like the same drug the user named?
        confident = (
            not drug
            or any(drug_similarity(drug, r.drug_name) >= DRUG_MATCH_THRESHOLD
                   for r in batch_hits)
        )
        spurious = any(r.is_spurious for r in batch_hits)
        if confident:
            return CheckResult(
                query_drug=drug or None,
                query_batch=batch or None,
                match_type=MatchType.batch_flagged,
                severity="danger",
                headline=(
                    "This batch is flagged as SPURIOUS by CDSCO"
                    if spurious else
                    "This batch is flagged as Not of Standard Quality"
                ),
                detail=(
                    "A government drug-testing lab found this exact batch "
                    "substandard or spurious. Do not use it. Take it back to "
                    "the pharmacy and report it on the CDSCO portal."
                ),
                batch_matches=batch_hits,
                drug_matches=[r for r in drug_hits if r not in batch_hits],
                checked_alerts=alerts_count,
                dataset_period=dataset_period,
            )
        # Batch number collides but the drug name doesn't match — surface it
        # honestly as a caution rather than a confident flag.
        return CheckResult(
            query_drug=drug or None,
            query_batch=batch or None,
            match_type=MatchType.drug_flagged,
            severity="caution",
            headline="A flagged batch shares this batch number — check carefully",
            detail=(
                "A flagged medicine has the same batch number but a different "
                "name. Batch numbers are not unique across manufacturers, so "
                "compare the manufacturer and drug name below with your strip."
            ),
            batch_matches=batch_hits,
            drug_matches=drug_hits,
            checked_alerts=alerts_count,
            dataset_period=dataset_period,
        )

    if drug_hits:
        return CheckResult(
            query_drug=drug or None,
            query_batch=batch or None,
            match_type=MatchType.drug_flagged,
            severity="caution",
            headline="Other batches of this medicine have been flagged",
            detail=(
                "Your batch number isn't on the list, but other batches of a "
                "medicine with this name have failed quality tests. Check your "
                "batch number against the flagged batches below."
            ),
            batch_matches=[],
            drug_matches=drug_hits,
            checked_alerts=alerts_count,
            dataset_period=dataset_period,
        )

    return CheckResult(
        query_drug=drug or None,
        query_batch=batch or None,
        match_type=MatchType.clear,
        severity="clear",
        headline="Not found in CDSCO alerts in this dataset",
        detail=(
            "This medicine and batch are not in the CDSCO NSQ alerts we have "
            "ingested. This is reassuring but not a guarantee of safety — our "
            "dataset is a snapshot, and not every substandard batch is caught. "
            "If the medicine looks or tastes wrong, stop and consult a pharmacist."
        ),
        batch_matches=[],
        drug_matches=[],
        checked_alerts=alerts_count,
        dataset_period=dataset_period,
    )
