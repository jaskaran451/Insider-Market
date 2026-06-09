from collections import defaultdict
from sec.manager_13f_parser import manager_13f_parser
from edgar import set_identity
set_identity("SmartMoneyDashboard (your_email@gmail.com)")
class ManagerPortfolioService:
    def analyze(self,query,limit=8):
        data=manager_13f_parser.get_manager_filings(query,limit)
        filings=data.get("filings",[])
        if not filings:
            return {
                "query":query,
                "success":False,
                "message":"No 13F-HR filings found"
            }
        latest=filings[0]
        previous=filings[1] if len(filings)>1 else None
        changes=self.compare_filings(latest,previous) if previous else []
        return {
            "query":query,
            "success":True,
            "manager":latest["filing"]["manager"],
            "cik":latest["filing"]["cik"],
            "latest_filing":latest["filing"],
            "previous_filing":previous["filing"] if previous else None,
            "overview":self.build_overview(latest,previous,changes),
            "top_holdings":self.top_holdings(latest),
            "allocation":self.portfolio_allocation(latest),
            "quarter_changes":self.build_change_summary(changes),
            "portfolio_timeline":self.build_portfolio_timeline(filings),
            "holding_timeline":self.build_holding_timeline(filings),
            "copy_trade_portfolio":self.copy_trade_portfolio(latest),
            "manager_dna":self.manager_dna(filings),
            "raw_filings":filings,
            "bubble_chart_data": self.build_bubble_chart_data(filings)
        }

    def num(self,value):
        try:
            return float(value or 0)
        except Exception:
            return 0

    def holding_key(self,h):
        if h.get("cusip"):
            return f"cusip:{h.get('cusip')}"
        if h.get("ticker"):
            return f"ticker:{h.get('ticker')}"
        return f"issuer:{h.get('issuer')}"

    def compare_filings(self,current,previous):
        current_map={self.holding_key(h):h for h in current["holdings"]}
        previous_map={self.holding_key(h):h for h in previous["holdings"]}
        keys=set(current_map.keys()) | set(previous_map.keys())
        changes=[]
        current_total=self.num(current["filing"].get("total_value"))
        previous_total=self.num(previous["filing"].get("total_value"))
        for key in keys:
            curr=current_map.get(key)
            prev=previous_map.get(key)
            base=curr or prev
            curr_shares=self.num(curr.get("shares")) if curr else 0
            prev_shares=self.num(prev.get("shares")) if prev else 0
            curr_value=self.num(curr.get("value")) if curr else 0
            prev_value=self.num(prev.get("value")) if prev else 0
            if curr and not prev:
                status="NEW"
            elif prev and not curr:
                status="CLOSED"
            elif curr_shares>prev_shares:
                status="INCREASED"
            elif curr_shares<prev_shares:
                status="DECREASED"
            else:
                status="UNCHANGED"
            current_weight=(curr_value/current_total)*100 if current_total else 0
            previous_weight=(prev_value/previous_total)*100 if previous_total else 0
            changes.append({
                "issuer":base.get("issuer"),
                "ticker":base.get("ticker"),
                "cusip":base.get("cusip"),
                "status":status,
                "current_shares":curr_shares,
                "previous_shares":prev_shares,
                "share_change":curr_shares-prev_shares,
                "current_value":curr_value,
                "previous_value":prev_value,
                "value_change":curr_value-prev_value,
                "current_weight":round(current_weight,4),
                "previous_weight":round(previous_weight,4),
                "weight_change":round(current_weight-previous_weight,4)
            })
        return sorted(changes,key=lambda x:abs(x["value_change"]),reverse=True)

    def build_overview(self,latest,previous,changes):
        latest_value=self.num(latest["filing"].get("total_value"))
        previous_value=self.num(previous["filing"].get("total_value")) if previous else 0
        return {
            "manager":latest["filing"].get("manager"),
            "latest_report_period":latest["filing"].get("report_period"),
            "previous_report_period":previous["filing"].get("report_period") if previous else None,
            "latest_filing_date":latest["filing"].get("filing_date"),
            "portfolio_value":latest_value,
            "previous_portfolio_value":previous_value,
            "portfolio_value_change":latest_value-previous_value if previous else 0,
            "total_holdings":len(latest.get("holdings",[])),
            "previous_total_holdings":len(previous.get("holdings",[])) if previous else 0,
            "new_positions":sum(1 for c in changes if c["status"]=="NEW"),
            "closed_positions":sum(1 for c in changes if c["status"]=="CLOSED"),
            "increased_positions":sum(1 for c in changes if c["status"]=="INCREASED"),
            "decreased_positions":sum(1 for c in changes if c["status"]=="DECREASED")
        }

    def top_holdings(self,filing,limit=15):
        total=self.num(filing["filing"].get("total_value"))
        rows=[]
        for h in filing["holdings"]:
            value=self.num(h.get("value"))
            rows.append({
                **h,
                "portfolio_weight":round((value/total)*100,4) if total else 0
            })
        return sorted(rows,key=lambda x:x["value"],reverse=True)[:limit]

    def portfolio_allocation(self,filing,limit=8):
        top=self.top_holdings(filing,limit)
        total=self.num(filing["filing"].get("total_value"))
        used=sum(self.num(h["value"]) for h in top)
        allocation=[{
            "label":h.get("ticker") or h.get("issuer"),
            "issuer":h.get("issuer"),
            "value":h.get("value"),
            "weight":h.get("portfolio_weight")
        } for h in top]
        other=max(0,total-used)
        if other:
            allocation.append({
                "label":"Other",
                "issuer":"Other Holdings",
                "value":other,
                "weight":round((other/total)*100,4) if total else 0
            })
        return allocation

    def build_change_summary(self,changes):
        return {
            "new":[c for c in changes if c["status"]=="NEW"][:10],
            "closed":[c for c in changes if c["status"]=="CLOSED"][:10],
            "increased":[c for c in changes if c["status"]=="INCREASED"][:10],
            "decreased":[c for c in changes if c["status"]=="DECREASED"][:10],
            "unchanged":[c for c in changes if c["status"]=="UNCHANGED"][:10],
            "all":changes
        }

    def build_portfolio_timeline(self,filings):
        timeline=[]
        for f in filings:
            timeline.append({
                "report_period":f["filing"].get("report_period"),
                "filing_date":f["filing"].get("filing_date"),
                "total_value":self.num(f["filing"].get("total_value")),
                "total_holdings":len(f.get("holdings",[]))
            })
        return timeline

    def build_holding_timeline(self,filings):
        history=defaultdict(list)
        for f in filings:
            period=f["filing"].get("report_period")
            total=self.num(f["filing"].get("total_value"))
            for h in f["holdings"]:
                key=self.holding_key(h)
                value=self.num(h.get("value"))
                history[key].append({
                    "report_period":period,
                    "issuer":h.get("issuer"),
                    "ticker":h.get("ticker"),
                    "shares":self.num(h.get("shares")),
                    "value":value,
                    "weight":round((value/total)*100,4) if total else 0
                })
        return dict(history)

    def copy_trade_portfolio(self,filing,limit=10):
        return [{
            "ticker":h.get("ticker"),
            "issuer":h.get("issuer"),
            "weight":h.get("portfolio_weight"),
            "value":h.get("value")
        } for h in self.top_holdings(filing,limit)]

    def manager_dna(self,filings):
        latest=filings[0]
        holdings=self.top_holdings(latest,10)
        weights=[h["portfolio_weight"] for h in holdings]
        top_5=sum(weights[:5])
        top_10=sum(weights[:10])
        style="Concentrated" if top_5>=70 else "Balanced" if top_5>=40 else "Diversified"
        return {
            "style":style,
            "top_5_concentration":round(top_5,2),
            "top_10_concentration":round(top_10,2),
            "average_holdings":round(sum(len(f.get("holdings",[])) for f in filings)/len(filings),2),
            "quarters_available":len(filings)
        }

    def build_bubble_chart_data(self, filings):
        rows = []
        previous = None
        for filing in reversed(filings):
            changes = self.compare_filings(filing, previous) if previous else []
            change_map = {self.holding_key(c): c for c in changes}
            total = self.num(filing["filing"].get("total_value"))
            for h in filing["holdings"]:
                key = self.holding_key(h)
                value = self.num(h.get("value"))
                change = change_map.get(key, {})
                rows.append({
                    "report_period": filing["filing"].get("report_period"),
                    "filing_date": filing["filing"].get("filing_date"),
                    "issuer": h.get("issuer"),
                    "ticker": h.get("ticker"),
                    "shares": self.num(h.get("shares")),
                    "value": value,
                    "portfolio_weight": round((value / total) * 100, 4) if total else 0,
                    "status": change.get("status", "CURRENT"),
                    "share_change": change.get("share_change", 0),
                    "value_change": change.get("value_change", 0)
                })
            previous = filing
        return rows

manager_portfolio_service=ManagerPortfolioService()