

from edgar.core import limits
from edgar import set_identity
set_identity("SmartMoneyDashboard (your_email@gmail.com)")

import json
import argparse
from pathlib import Path
from edgar import Company, obj

OUTPUT_DIR=Path("test_outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

def safe_value(v):
    if v is None:
        return None
    if hasattr(v,"item"):
        try:
            return v.item()
        except Exception:
            pass
    return str(v) if not isinstance(v,(int,float,bool)) else v

def safe_filings(collection,limit=None):
    items=[]
    for idx,filing in enumerate(collection):
        if limit and idx>=limit:
            break
        items.append(filing)
    return items

def normalize_holding(row):
    return {
        "issuer":safe_value(row.get("Issuer")),
        "ticker":safe_value(row.get("Ticker")),
        "cusip":safe_value(row.get("Cusip")),
        "class":safe_value(row.get("Class")),
        "value":safe_value(row.get("Value")),
        "shares":safe_value(row.get("SharesPrnAmount")),
        "type":safe_value(row.get("Type")),
        "put_call":safe_value(row.get("PutCall")),
        "investment_discretion":safe_value(row.get("InvestmentDiscretion")),
        "sole_voting":safe_value(row.get("SoleVoting")),
        "shared_voting":safe_value(row.get("SharedVoting")),
        "non_voting":safe_value(row.get("NonVoting"))
    }

def parse_13f_filing(filing):
    data_obj=obj(filing)

    if not data_obj or not hasattr(data_obj,"infotable"):
        return None

    df=data_obj.infotable

    if df is None or df.empty:
        return None

    holdings=[]

    for _,row in df.iterrows():
        holdings.append(normalize_holding(row))

    return {
        "filing": {
            "manager":safe_value(getattr(filing,"company",None)),
            "cik":safe_value(getattr(filing,"cik",None)),
            "form":safe_value(getattr(filing,"form",None)),
            "filing_date":safe_value(getattr(filing,"filing_date",None)),
            "report_period":safe_value(getattr(data_obj,"report_period",None)),
            "accession_number":safe_value(getattr(filing,"accession_number",None)),
            "total_value":safe_value(getattr(data_obj,"total_value",None)),
            "total_holdings":safe_value(getattr(data_obj,"total_holdings",None))
        },
        "holdings":holdings
    }

def build_manager_13f_json(symbol,limit):
    print(f"\nSTEP 1: Load company/manager: {symbol}")

    company=Company(symbol)

    print(f"Company loaded: {company}")

    print("\nSTEP 2: Fetch 13F-HR filings")

    filings=company.get_filings(form=["13F-HR","13F-HR/A"])
    filings=safe_filings(filings,limit)

    print(f"13F filings found/tested: {len(filings)}")

    result={
        "query":symbol,
        "filings_count":len(filings),
        "filings":[]
    }

    for idx,filing in enumerate(filings,1):
        print(f"\nSTEP 3.{idx}: Parse filing {getattr(filing,'accession_number',None)}")

        try:
            parsed=parse_13f_filing(filing)

            if parsed:
                print(f"Report period: {parsed['filing']['report_period']}")
                print(f"Holdings: {len(parsed['holdings'])}")
                result["filings"].append(parsed)
            else:
                print("No infotable found")

        except Exception as e:
            print(f"Parse error: {e}")

    output_path=OUTPUT_DIR/f"{symbol.upper()}_13f_holdings.json"

    output_path.write_text(
        json.dumps(result,indent=2,default=str),
        encoding="utf-8"
    )

    print(f"\nSaved JSON: {output_path.resolve()}")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--symbol",default="NVDA")
    parser.add_argument("--limit",type=int,default=2)
    args=parser.parse_args()

    build_manager_13f_json(args.symbol,args.limit)