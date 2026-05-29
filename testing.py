from utils.edgar_wrapper import edgar_client
from sec.parser import filing_parser
from services.insider_service import insider_service


def test_insider_pipeline(ticker="BBAI"):

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
        print("❌ No insider filings found")
        return

    print(f"✅ Found {len(filings)} insider filings")

    # -------------------------------------------------
    # STEP 3: PARSE FILINGS
    # -------------------------------------------------
    print("\n🧠 STEP 3: Parse insider filings...\n")

    parsed_filings = []

    # Only test recent filings for now
    for idx, filing in enumerate(filings):

        if idx >= 10:
            break

        try:

            parsed = filing_parser.parse(filing)

            if parsed:
                parsed_filings.append(parsed)

        except Exception as e:
            print(f"❌ Parse error: {e}")

    print(f"✅ Parsed {len(parsed_filings)} filings")

    # -------------------------------------------------
    # STEP 4: ANALYZE INSIDER SIGNALS
    # -------------------------------------------------
    print("\n📊 STEP 4: Generate insider intelligence...\n")

    summary = insider_service.analyze(
        filings=parsed_filings,
        company=company.name
    )

    # -------------------------------------------------
    # OUTPUT RESULTS
    # -------------------------------------------------
    print("\n==============================")
    print("INSIDER SUMMARY")
    print("==============================\n")

    print(f"Company: {summary.company}")

    print(f"\nTotal Buys: {summary.total_buys}")
    print(f"Total Sells: {summary.total_sells}")

    print(f"\nNet Activity: {summary.net_activity}")

    print(f"\nInsider Score: {summary.insider_score}")

    print(f"\nBullish: {summary.bullish}")
    print(f"Bearish: {summary.bearish}")

    print(f"\nCluster Buying: {summary.cluster_buying}")

    print("\n==============================")
    print("SIGNALS")
    print("==============================\n")

    for name, score  in summary.signals:
        print(f"{name} ({score})")

    print("\n==============================")
    print("RECENT TRANSACTIONS")
    print("==============================\n")

    for tx in summary.recent_transactions:

        print(tx)




if __name__ == "__main__":
    test_insider_pipeline("BBAI")