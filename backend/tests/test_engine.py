"""Unit tests for the matching engine and PDF parser."""

from pathlib import Path

import pytest

from app.engine import check, drug_similarity, drug_tokens
from app.parser import classify_failure, normalize_batch, parse_pdf, to_records
from app.schemas import FailureCategory, MatchType, NSQRecord

RAW_PDF = Path(__file__).resolve().parents[1] / "data" / "raw" / "NSQ_Alert_March-2025.pdf"


def rec(**kw) -> NSQRecord:
    base = dict(
        id="x", drug_name="Pantoprazole Tablets IP 40 mg", batch_no="SP240165",
        batch_no_normalized=normalize_batch("SP240165"), manufacturer="M/s ACME",
        mfg_date="06/2024", expiry_date="05/2026", failure_reason="Dissolution",
        failure_category="dissolution", is_spurious=False, tested_by="CDL Kolkata",
        source_alert="NSQ Alert 2025-03", source_url="https://cdsco.gov.in/x",
        alert_period="2025-03",
    )
    base.update(kw)
    return NSQRecord.model_validate(base)


class TestNormalization:
    @pytest.mark.parametrize("raw,expected", [
        ("AD-204", "AD204"), ("ad 204", "AD204"), ("AD204", "AD204"),
        ("SP/240165", "SP240165"), (" 0081 ", "0081"),
    ])
    def test_batch_normalization_collapses_punctuation(self, raw, expected):
        assert normalize_batch(raw) == expected

    def test_drug_tokens_drop_dosage_noise_and_brands(self):
        toks = drug_tokens("Pantoprazole Gastro-Resistant Tablets IP 40 mg (PanX)")
        assert "pantoprazole" in toks
        assert "tablets" not in toks and "panx" not in toks  # noise + brand removed

    def test_drug_similarity_matches_same_molecule(self):
        assert drug_similarity("Pantoprazole 40mg", "Pantoprazole Tablets IP 40 mg") > 0.45
        assert drug_similarity("Pantoprazole", "Amoxicillin Sodium") < 0.45


class TestFailureClassification:
    @pytest.mark.parametrize("reason,cat", [
        ("Declared Spurious", FailureCategory.spurious),
        ("Particulate Matter", FailureCategory.contamination),
        ("Dissolution (Buffer Stage)", FailureCategory.dissolution),
        ("Assay of Paracetamol", FailureCategory.assay),
        ("Misbranded / label claim", FailureCategory.labelling),
        ("Appearance of solution", FailureCategory.physical),
        ("Something unmapped", FailureCategory.other),
    ])
    def test_classify(self, reason, cat):
        assert classify_failure(reason) == cat


class TestCheckEngine:
    def test_exact_batch_with_matching_drug_is_danger(self):
        result = check([rec()], "Pantoprazole 40mg", "SP240165", 1, "2025-03")
        assert result.match_type == MatchType.batch_flagged
        assert result.severity == "danger"
        assert len(result.batch_matches) == 1

    def test_batch_only_query_flags(self):
        result = check([rec()], None, "sp 240165", 1, "2025-03")
        assert result.match_type == MatchType.batch_flagged

    def test_spurious_batch_headline(self):
        result = check([rec(is_spurious=True)], None, "SP240165", 1, "2025-03")
        assert "SPURIOUS" in result.headline.upper()

    def test_batch_collision_with_wrong_drug_is_caution_not_danger(self):
        # same batch number, completely different molecule -> don't overclaim
        result = check([rec()], "Metformin", "SP240165", 1, "2025-03")
        assert result.severity == "caution"
        assert result.match_type == MatchType.drug_flagged
        assert result.batch_matches  # still shown, never hidden

    def test_drug_name_match_other_batch_is_caution(self):
        result = check([rec()], "Pantoprazole", "ZZ999", 1, "2025-03")
        assert result.match_type == MatchType.drug_flagged
        assert result.severity == "caution"
        assert not result.batch_matches and result.drug_matches

    def test_clear_when_nothing_matches(self):
        result = check([rec()], "Metformin", "ZZ999", 1, "2025-03")
        assert result.match_type == MatchType.clear
        assert result.severity == "clear"

    def test_clear_copy_does_not_promise_safety(self):
        result = check([rec()], "Metformin", "ZZ999", 1, "2025-03")
        assert "not a guarantee" in result.detail.lower()


class TestRealPdf:
    @pytest.fixture(scope="class")
    def records(self):
        parsed = parse_pdf(str(RAW_PDF))
        return to_records(parsed, "2025-03", "NSQ Alert 2025-03", "https://cdsco.gov.in/x")

    def test_parses_real_alert(self, records):
        assert len(records) >= 50  # the March 2025 alert has 70 entries

    def test_every_record_has_batch_and_reason(self, records):
        for r in records:
            assert r["batch_no"] and r["failure_reason"] and r["drug_name"]

    def test_known_real_entry_present(self, records):
        # Adrenaline Bitartrate Injection, batch AD-204, was in the real alert
        norm = {r["batch_no_normalized"] for r in records}
        assert "AD204" in norm

    def test_end_to_end_flag_on_real_batch(self, records):
        domain = [NSQRecord.model_validate(r) for r in records]
        result = check(domain, "Adrenaline", "AD-204", 1, "2025-03")
        assert result.match_type == MatchType.batch_flagged
        assert result.severity == "danger"
