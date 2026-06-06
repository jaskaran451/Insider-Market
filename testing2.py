import json
import argparse
from pathlib import Path
from services.manager_portfolio_service import manager_portfolio_service
from edgar import set_identity
set_identity("SmartMoneyDashboard (your_email@gmail.com)")
def run(query,limit):
    result=manager_portfolio_service.analyze(query,limit)
    out=Path("test_outputs")
    out.mkdir(exist_ok=True)
    path=out/f"{query.upper()}_manager_portfolio_service.json"
    path.write_text(json.dumps(result,indent=2,default=str),encoding="utf-8")
    print("\nSUCCESS:",result.get("success"))
    print("MANAGER:",result.get("manager"))
    if result.get("success"):
        print("LATEST:",result["overview"]["latest_report_period"])
        print("PORTFOLIO VALUE:",result["overview"]["portfolio_value"])
        print("TOTAL HOLDINGS:",result["overview"]["total_holdings"])
        print("NEW:",result["overview"]["new_positions"])
        print("CLOSED:",result["overview"]["closed_positions"])
        print("INCREASED:",result["overview"]["increased_positions"])
        print("DECREASED:",result["overview"]["decreased_positions"])
        print("STYLE:",result["manager_dna"]["style"])
        print("\nTOP HOLDINGS:")
        for h in result["top_holdings"][:5]:
            print(h.get("ticker"),h.get("issuer"),h.get("portfolio_weight"))
    print("\nSaved:",path.resolve())

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--query",default="NVDA")
    parser.add_argument("--limit",type=int,default=8)
    args=parser.parse_args()
    run(args.query,args.limit)