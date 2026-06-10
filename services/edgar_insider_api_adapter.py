from edgar import Company
from sec.parser import filing_parser

class EdgarInsiderApiAdapter:
    def get_insider_transactions(self,symbol,limit=40):
        company=Company(symbol)
        filings=company.get_filings(form=["4"])

        transactions=[]

        for idx,filing in enumerate(filings):
            if idx>=limit:
                break

            try:
                parsed=filing_parser.parse(filing)
                if not parsed or not hasattr(parsed,"data"):
                    continue

                data=parsed.data
                activities=data.get("activities",[])
                insider_name=data.get("insider_name")

                if not isinstance(activities,list):
                    activities=[activities]

                ownership=data.get("ownership_summary")
                title=getattr(ownership,"position",None) if ownership else None
                report_date=getattr(ownership,"reporting_date",None) if ownership else None

                for activity in activities:
                    transactions.append(self._to_alpha_vantage_row(
                        activity=activity,
                        insider_name=insider_name,
                        title=title,
                        report_date=report_date,
                        filing=filing
                    ))

            except Exception as e:
                print(f"[EDGAR INSIDER ERROR] {symbol}: {e}")

        return {
            "symbol":symbol.upper(),
            "data":transactions
        }

    def _to_alpha_vantage_row(self,activity,insider_name,title,report_date,filing):
        code=getattr(activity,"code","")
        shares=self._safe(getattr(activity,"shares",None))
        price=self._safe(getattr(activity,"price_per_share",None))
        sec_link = self.build_sec_link(filing)
        try:
            transaction_value = float(shares) * float(price)
        except:
            transaction_value = 0

        return {
            "transaction_date":str(report_date) if report_date else None,
            "executive":insider_name,
            "executive_title":title,
            "security_type":"Common Stock",
            "acquisition_or_disposal":self._av_action(code),
            "shares":str(shares),
            "share_value": round(transaction_value, 2),
            "share_price":str(price),
            "sec_link":sec_link
        }

    def build_sec_link(self,filing):
        cik = str(filing.cik)

        accession = filing.accession_number.replace("-", "")

        return (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{cik}/{accession}/"
        )

    def _av_action(self,code):
        if code=="P":
            return "A"
        if code=="S":
            return "D"
        if code=="F":
            return "D"
        if code=="A":
            return "A"
        return ""

    def _safe(self,value):
        if value is None:
            return "0"
        return value

edgar_insider_api_adapter=EdgarInsiderApiAdapter()