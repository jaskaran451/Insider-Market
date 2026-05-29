
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass
from edgar import Company, set_identity
import edgar

set_identity("SmartMoneyDashboard (your_email@gmail.com)")
def get_logo_of_company(symbol):
    company = Company(symbol)
    return company.get_icon()

# =========================================================
# CORE RESULT MODELS (STANDARDIZED OUTPUTS)
# =========================================================

@dataclass
class CompanyResult:
    cik: str
    name: str
    ticker: Optional[str] = None
    raw: Optional[Any] = None


@dataclass
class FundResult:
    cik: str
    name: str
    raw: Optional[Any] = None


@dataclass
class FilingResult:
    accession_number: str
    form: str
    filing_date: str
    raw: Optional[Any] = None


# =========================================================
# EDGAR WRAPPER CLASS
# =========================================================

class EdgarWrapper:
    """
    Production-safe abstraction over edgar package.
    All SEC interactions must go through this layer.
    """

    def __init__(self, mode: str = "NORMAL"):
        self.mode = mode

    # -----------------------------------------------------
    # MAIN RESOLVER (ENTRY POINT)
    # -----------------------------------------------------
    def find(self, query: Union[str, int]) -> Optional[Union[CompanyResult, FundResult, FilingResult]]:
        """
        Resolve any search input into a structured object.
        """
        try:
            result = edgar.find(query)

            if result is None:
                return None

            # -----------------------------
            # Filing
            # -----------------------------
            if hasattr(result, "accession_number"):
                entity = result
                return FilingResult(
                    accession_number=getattr(result, "accession_number", ""),
                    form=getattr(result, "form", ""),
                    filing_date=str(getattr(result, "filing_date", "")),
                    raw=entity
                )

            # -----------------------------
            # Company / Entity
            # -----------------------------
            if hasattr(result, "cik") and hasattr(result, "name"):
                entity = result
                return CompanyResult(
                    cik=str(result.cik),
                    name=result.name,
                    ticker=getattr(result, "ticker", None),
                    raw=entity
                )

            # -----------------------------
            # Fund Entity
            # -----------------------------
            if hasattr(result, "fund_type") or "fund" in str(type(result)).lower():
                entity = result
                return FundResult(
                    cik=str(getattr(result, "cik", "")),
                    name=getattr(result, "name", "Unknown Fund"),
                    raw=entity
                )

            return result

        except Exception as e:
            raise RuntimeError(f"EDGAR find() failed for query={query}: {str(e)}")




# =========================================================
# SINGLETON (USED ACROSS APP)
# =========================================================

edgar_client = EdgarWrapper()