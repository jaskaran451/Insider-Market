# app/sec/parser.py

from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Union

import edgar

from utils.edgar_wrapper import FilingResult


# =========================================================
# UNIFIED OUTPUT MODEL
# =========================================================

@dataclass
class NormalizedFiling:
    accession_number: str
    form: str
    filing_date: str

    cik: Optional[str] = None
    company_name: Optional[str] = None

    data: Optional[Dict[str, Any]] = None
    raw: Optional[Any] = None


# =========================================================
# MAIN PARSER CLASS
# =========================================================

class FilingParser:
    """
    Converts EDGAR filings into structured intelligence objects.
    """

    def _get_object(self, filing):
        """
        Safely extract edgar object regardless of type
        """

        if hasattr(filing, "raw"):
            return filing.raw

        return filing
    # -----------------------------------------------------
    # ENTRY POINT
    # -----------------------------------------------------
    def parse(self, filing: FilingResult) -> NormalizedFiling:
        """
        Route filing to correct parser based on form type.
        """

        form = filing.form.upper()

        if "13F" in form:
            return self._parse_13f(filing)

        if form in ["4", "5"]:
            return self._parse_insider(filing)

        if "13D" in form or "13G" in form:
            return self._parse_ownership(filing)

        if form == "8-K":
            return self._parse_8k(filing)

        if "NPORT" in form:
            return self._parse_nport(filing)

        if "S-1" in form:
            return self._parse_s1(filing)

        # fallback
        return self._parse_generic(filing)

    # -----------------------------------------------------
    # 13F (INSTITUTIONAL HOLDINGS)
    # -----------------------------------------------------
    def _parse_13f(self, filing: FilingResult) -> NormalizedFiling:
        try:
            obj = self._get_object(filing)

            data_obj = edgar.obj(obj)

            return NormalizedFiling(
                    accession_number=filing.accession_number,
                    form=filing.form,
                    filing_date=filing.filing_date,
                    data={
                        "type": "institutional_holdings",
                        "holdings": getattr(obj, "holdings", None),
                        "fund_name": getattr(obj, "name", None)
                    },
                    raw=obj
                )

        except Exception as e:
            return self._fallback(filing, str(e))

    # -----------------------------------------------------
    # INSIDER TRADING (FORM 4 / 5)
    # -----------------------------------------------------
    def _parse_insider(self, filing: FilingResult) -> NormalizedFiling:
        try:
            obj = self._get_object(filing)

            data_obj = edgar.obj(obj)

            # -------------------------------------------------
            # STRUCTURED EXTRACTION
            # -------------------------------------------------
            activities = None
            dataframe = None
            summary = None

            # Transaction activities
            if hasattr(data_obj, "get_transaction_activities"):
                activities = data_obj.get_transaction_activities()

            # DataFrame export
            if hasattr(data_obj, "to_dataframe"):
                dataframe = data_obj.to_dataframe()

            # Ownership summary
            if hasattr(data_obj, "get_ownership_summary"):
                summary = data_obj.get_ownership_summary()

            return NormalizedFiling(
                accession_number=getattr(filing, "accession_number", ""),
                form=getattr(filing, "form", ""),
                filing_date=getattr(filing, "filing_date", ""),
                data={
                    "type": "insider_transaction",
                    "insider_name": getattr(data_obj, "insider_name", None),
                    "issuer": getattr(data_obj, "issuer", None),
                    "activities": activities,
                    "ownership_summary": summary,
                    "transactions_df": dataframe
                },
                raw=obj
            )

        except Exception as e:
            return self._fallback(filing, str(e))

    # -----------------------------------------------------
    # OWNERSHIP (13D / 13G)
    # -----------------------------------------------------
    def _parse_ownership(self, filing: FilingResult) -> NormalizedFiling:
        try:
            obj = edgar.obj(filing.raw)

            return NormalizedFiling(
                accession_number=filing.accession_number,
                form=filing.form,
                filing_date=filing.filing_date,
                data={
                    "type": "ownership_change",
                    "ownership": getattr(obj, "ownership", None)
                },
                raw=obj
            )

        except Exception as e:
            return self._fallback(filing, str(e))

    # -----------------------------------------------------
    # 8-K EVENTS
    # -----------------------------------------------------
    def _parse_8k(self, filing: FilingResult) -> NormalizedFiling:
        try:
            obj = self._get_object(filing)
            data_obj = edgar.obj(obj)


            return NormalizedFiling(
                accession_number=filing.accession_number,
                form=filing.form,
                filing_date=filing.filing_date,
                data={
                    "type": "corporate_event",
                    "events": getattr(obj, "events", None)
                },
                raw=obj
            )

        except Exception as e:
            return self._fallback(filing, str(e))

    # -----------------------------------------------------
    # NPORT (FUND HOLDINGS)
    # -----------------------------------------------------
    def _parse_nport(self, filing: FilingResult) -> NormalizedFiling:
        try:
            obj = self._get_object(filing)
            data_obj = edgar.obj(obj)

            return NormalizedFiling(
                accession_number=filing.accession_number,
                form=filing.form,
                filing_date=filing.filing_date,
                data={
                    "type": "fund_portfolio",
                    "positions": getattr(obj, "portfolio", None)
                },
                raw=obj
            )

        except Exception as e:
            return self._fallback(filing, str(e))

    # -----------------------------------------------------
    # S-1 (IPO FILINGS)
    # -----------------------------------------------------
    def _parse_s1(self, filing: FilingResult) -> NormalizedFiling:
        try:
            obj = self._get_object(filing)
            data_obj = edgar.obj(obj)

            return NormalizedFiling(
                accession_number=filing.accession_number,
                form=filing.form,
                filing_date=filing.filing_date,
                data={
                    "type": "ipo_filing",
                    "details": getattr(obj, "data", None)
                },
                raw=obj
            )

        except Exception as e:
            return self._fallback(filing, str(e))

    # -----------------------------------------------------
    # GENERIC FALLBACK
    # -----------------------------------------------------
    def _parse_generic(self, filing: FilingResult) -> NormalizedFiling:
        return NormalizedFiling(
            accession_number=filing.accession_number,
            form=filing.form,
            filing_date=filing.filing_date,
            data={
                "type": "generic_filing"
            },
            raw=filing.raw
        )

    # -----------------------------------------------------
    # ERROR HANDLING
    # -----------------------------------------------------
    def _fallback(self, filing: FilingResult, error: str) -> NormalizedFiling:
        return NormalizedFiling(
            accession_number=filing.accession_number,
            form=filing.form,
            filing_date=filing.filing_date,
            data={
                "type": "error",
                "message": error
            },
            raw=filing.raw
        )


# =========================================================
# SINGLETON
# =========================================================

filing_parser = FilingParser()