from utils.edgar_wrapper import edgar_client
from sec.parser import filing_parser
from services.insider_service import insider_service


def test_insider_pipeline(ticker="APLD"):

    print("\n🔎 STEP 1: Resolve company...\n")

    company = edgar_client.find(ticker)

    if not company:
        print("❌ Company not found")
        return

    print(f"✅ Company: {company.name}")

    # -------------------------------------------------
    # STEP 2: FETCH FILINGS
    # -------------------------------------------------
    print("\n📄 STEP 2: Fetch filings...\n")

    entity = company.raw
    filings = entity.get_filings(form=["4"])

    if not filings:
        print("❌ No filings found")
        return

    filings = list(filings)  # ensure list

    print(f"✅ Found {len(filings)} filings")

    # -------------------------------------------------
    # STEP 3: PARSE FILINGS
    # -------------------------------------------------
    print("\n🧠 STEP 3: Parse filings...\n")

    parsed_filings = []

    for i, filing in enumerate(filings[3:5]):  # adjustable limit

        try:
            parsed = filing_parser.parse(filing)

            if parsed:
                parsed_filings.append(parsed)

        except Exception as e:
            print(f"❌ Parse error at filing {i}: {e}")

    print(f"✅ Parsed filings: {len(parsed_filings)}")

    if not parsed_filings:
        print("❌ No parsed filings")
        return

    # -------------------------------------------------
    # STEP 4: ANALYZE
    # -------------------------------------------------
    print("\n📊 STEP 4: Running analysis...\n")

    summary = insider_service.analyze(
        filings=parsed_filings,
        company=company.name
    )

    # -------------------------------------------------
    # STEP 5: BASIC METRICS
    # -------------------------------------------------
    print("\n==============================")
    print("INSIDER SUMMARY")
    print(summary)
    print("==============================\n")

    print(f"Company: {summary.company}")

    print(f"Buys: {summary.total_buys}")
    print(f"Sells: {summary.total_sells}")
    print(f"Taxes: {summary.total_taxes}")
    print(f"Grants: {summary.total_grants}")

    print(f"\nNet Activity: {summary.net_activity}")

    print(f"\nInsider Score: {summary.insider_score}")
    print(f"Smart Money Score: {summary.smart_money_score}")

    print(f"\nBullish: {summary.bullish}")
    print(f"Bearish: {summary.bearish}")

    print(f"\nCluster Buying: {summary.cluster_buying}")

    # -------------------------------------------------
    # STEP 6: SIGNALS DEBUG
    # -------------------------------------------------
    print("\n==============================")
    print("SIGNALS (RAW)")
    print("==============================\n")

    print(f"{summary.signals})")

    # -------------------------------------------------
    # STEP 7: GROUPED SIGNALS
    # -------------------------------------------------
    print("\n==============================")
    print("SIGNAL GROUPS")
    print("==============================\n")

    print("Bullish:")
    for s in summary.signal_groups.get("bullish", []):
        print(f"  - {s['signal']} ({s['score']})")

    print("\nBearish:")
    for s in summary.signal_groups.get("bearish", []):
        print(f"  - {s['signal']} ({s['score']})")

    print("\nNeutral:")
    for s in summary.signal_groups.get("neutral", []):
        print(f"  - {s['signal']} ({s['score']})")

    # -------------------------------------------------
    # STEP 8: MOMENTUM
    # -------------------------------------------------
    print("\n==============================")
    print("MOMENTUM")
    print("==============================\n")

    print(f"Insider Momentum: {summary.insider_momentum}")

    # -------------------------------------------------
    # STEP 9: SAMPLE TRANSACTIONS
    # -------------------------------------------------
    print("\n==============================")
    print("RECENT TRANSACTIONS")
    print("==============================\n")

    for tx in summary.recent_transactions[-5:]:
        print(tx)


if __name__ == "__main__":
    test_insider_pipeline("APLD")