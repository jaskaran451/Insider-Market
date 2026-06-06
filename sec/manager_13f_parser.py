import math
from edgar import Company,obj
from edgar import set_identity
set_identity("SmartMoneyDashboard (your_email@gmail.com)")
class Manager13FParser:
    def safe(self,value):
        if value is None:
            return None
        try:
            if math.isnan(value):
                return None
        except Exception:
            pass
        if hasattr(value,"item"):
            try:
                return value.item()
            except Exception:
                pass
        return value

    def number(self,value):
        value=self.safe(value)
        if value in [None,"","nan","NaN"]:
            return 0
        try:
            return float(str(value).replace(",",""))
        except Exception:
            return 0

    def safe_filings(self,filings,limit=None):
        items=[]
        for idx,filing in enumerate(filings):
            if limit and idx>=limit:
                break
            items.append(filing)
        return items

    def holding_key(self,holding):
        cusip=holding.get("cusip")
        ticker=holding.get("ticker")
        issuer=holding.get("issuer")
        if cusip:
            return f"cusip:{cusip}"
        if ticker:
            return f"ticker:{ticker}"
        return f"issuer:{issuer}"

    def normalize_holding(self,row):
        return {
            "issuer":self.safe(row.get("Issuer")),
            "ticker":self.safe(row.get("Ticker")),
            "cusip":self.safe(row.get("Cusip")),
            "class":self.safe(row.get("Class")),
            "value":self.number(row.get("Value")),
            "shares":self.number(row.get("SharesPrnAmount")),
            "type":self.safe(row.get("Type")),
            "put_call":self.safe(row.get("PutCall")),
            "investment_discretion":self.safe(row.get("InvestmentDiscretion")),
            "sole_voting":self.number(row.get("SoleVoting")),
            "shared_voting":self.number(row.get("SharedVoting")),
            "non_voting":self.number(row.get("NonVoting"))
        }

    def parse_filing(self,filing):
        data_obj=obj(filing)
        if not data_obj or not hasattr(data_obj,"infotable"):
            return None
        df=data_obj.infotable
        if df is None or df.empty:
            return None
        holdings=[self.normalize_holding(row) for _,row in df.iterrows()]
        return {
            "filing":{
                "manager":self.safe(getattr(filing,"company",None)),
                "cik":self.safe(getattr(filing,"cik",None)),
                "form":self.safe(getattr(filing,"form",None)),
                "filing_date":self.safe(getattr(filing,"filing_date",None)),
                "report_period":self.safe(getattr(data_obj,"report_period",None)),
                "accession_number":self.safe(getattr(filing,"accession_number",None)),
                "total_value":self.number(getattr(data_obj,"total_value",0)),
                "total_holdings":self.number(getattr(data_obj,"total_holdings",0))
            },
            "holdings":holdings
        }

    def get_manager_filings(self,query,limit=None):
        company=Company(query)
        filings=company.get_filings(form=["13F-HR","13F-HR/A"])
        filings=self.safe_filings(filings,limit)
        parsed=[]
        for filing in filings:
            try:
                item=self.parse_filing(filing)
                if item:
                    parsed.append(item)
            except Exception as e:
                print(f"[13F PARSE ERROR] {query}: {e}")
        return {
            "query":query,
            "filings_count":len(parsed),
            "filings":parsed
        }

manager_13f_parser=Manager13FParser()