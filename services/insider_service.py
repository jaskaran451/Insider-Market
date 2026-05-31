
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from sqlalchemy.sql.functions import next_value


# =========================================================
# OUTPUT MODELS
# =========================================================


@dataclass
class InsiderSignal:
    signal: str
    score: float
    description: str
    smart_money_score: float
    signal_groups: dict
    insider_momentum: float



@dataclass
class InsiderSummary:
    company: str

    total_buys: int
    total_sells: int
    total_taxes: int
    total_grants: int
    net_activity: int
    insider_momentum: float
    insider_score: float
    smart_money_score: float
    bullish: bool
    bearish: bool
    cluster_buying: bool
    signals: List[InsiderSignal]
    recent_transactions: List[Dict[str, Any]]
    signal_groups: dict
    summary_stats: Dict = field(default_factory=dict)


# =========================================================
# INSIDER SERVICE
# =========================================================

class InsiderService:
    """
    Aggregates insider filings and generates intelligence signals.
    """
    ROLE_WEIGHTS = {
        "CEO": 1.0,
        "Chief Executive Officer": 1.0,
        "CFO": 0.85,
        "Chief Financial Officer": 0.85,
        "COO": 0.8,
        "Director": 0.6,
        "President": 0.75
    }

    # -----------------------------------------------------
    # MAIN ENTRY POINT
    # -----------------------------------------------------
    def analyze(self, filings: List[Any], company: str) -> InsiderSummary:
        """
        filings = parsed insider filings
        """

        transactions = []

        # -------------------------------------------------
        # EXTRACT TRANSACTIONS
        # -------------------------------------------------
        for filing in filings:

            data = filing.data

            if not data:
                continue

            activities = data.get("activities")

            if not activities:
                continue

            # Normalize to list
            if not isinstance(activities, list):
                activities = [activities]

            for activity in activities:
                context = self._extract_filing_context(filing,activity)
                parsed = self._normalize_transaction(activity, context)

                if parsed:
                    transactions.append(parsed)

        # -------------------------------------------------
        # CALCULATE METRICS
        # -------------------------------------------------
        buys = [t for t in transactions if t["type"] == "BUY"]
        sells = [t for t in transactions if t["type"] == "SELL"]
        taxes = [t for t in transactions if t["type"] == "Tax"]
        grants = [t for t in transactions if t["type"] == "Grant"]

        total_buys = len(buys)
        total_sells = len(sells)
        total_taxes = len(taxes)
        total_grants = len(grants)

        net_activity = total_buys - total_sells

        # -------------------------------------------------
        # SIGNAL DETECTION
        # -------------------------------------------------
        cluster_buying = self._detect_cluster_buying(buys)

        insider_score = self._calculate_score(
            transactions=transactions,
            cluster_buying=cluster_buying
        )

        raw_signals = self._generate_signals(
            transactions=transactions,
            cluster_buying=cluster_buying,
            score=insider_score
        )

        smart_money_score = self._calculate_smart_money_score(
            insider_score=insider_score,
            signals=raw_signals,
            transactions=transactions,
            cluster_buying=cluster_buying
        )
        summary_stats = {

            "buy_count": len(buys),
            "sell_count": len(sells),
            "tax_count": len(taxes),
            "grant_count": len(grants),

            "buy_value":
                sum(t["value"] or 0 for t in buys),

            "sell_value":
                sum(t["value"] or 0 for t in sells),

            "tax_value":
                sum(t["value"] or 0 for t in taxes),

            "grant_shares":
                sum(t["shares"] or 0 for t in grants),

            "tax_shares":
                sum(t["shares"] or 0 for t in taxes),

            "net_shares":
                sum(t["net_change"] or 0 for t in transactions)
        }

        return InsiderSummary(
            company=company,

            total_buys=total_buys,
            total_sells=total_sells,

            net_activity=net_activity,

            insider_score=insider_score,
            smart_money_score=smart_money_score,
            bullish=smart_money_score >= 65,
            bearish=smart_money_score <= 35,
            cluster_buying=cluster_buying,

            signals=raw_signals,
            signal_groups=self._group_signals(raw_signals),
            insider_momentum=self._calculate_insider_momentum(transactions),
            recent_transactions=transactions,
            total_taxes=total_taxes,
            total_grants=total_grants,
            summary_stats=summary_stats
        )


    def _signal_description(self, signal: str) -> str:

        descriptions = {
            "CLUSTERED_ACTIVITY": "Multiple insiders traded within a short timeframe.",
            "ACCUMULATION": "Net insider buying pressure detected.",
            "DISTRIBUTION": "Net insider selling pressure detected.",
            "BULLISH_INSIDER_SENTIMENT": "Insider behavior indicates bullish sentiment.",
            "BEARISH_INSIDER_SENTIMENT": "Insider behavior indicates bearish sentiment.",
            "NEUTRAL_ACTIVITY": "No strong directional insider signal detected."
        }

        return descriptions.get(signal, "")

    # =====================================================
    # TRANSACTION NORMALIZATION
    # =====================================================
    def _normalize_transaction(self, activity,context) -> Optional[Dict[str, Any]]:

            try:
                return {
                    "type": self._classify_transaction(activity),

                    "shares": getattr(activity, "shares", None),
                    "value": getattr(activity, "value", None),
                    "price": getattr(activity, "price_per_share", None),

                    "transaction_type": getattr(activity, "transaction_type", None),
                    "code": getattr(activity, "code", None),

                    # -------------------------------------------------
                    # FILLED FROM FILING LAYER (IMPORTANT)
                    # -------------------------------------------------
                    "insider": context.get("insider"),
                    "role": context.get("role"),
                    "date": context.get("date"),
                    "net_change": context.get("net_change"),
                    "net_value": context.get("net_value"),
                    "remaining_shares": context.get("remaining_shares")
                }

            except Exception:
                return None



    # =====================================================
    # BUY/SELL CLASSIFICATION
    # =====================================================
    def _classify_transaction(self, activity) -> str:
        code = getattr(activity, "code", "")
        ttype = getattr(activity, "transaction_type", "").lower()


        if code in ["P"]:  # Purchase
            return "BUY"
        if code in ["S"]:
            return "SELL"
        if code in ["F"]:
            return "Tax"
        if code in ["A"]:
            return "Grant"

        # -------------------------------------------------
        # OPTION EXERCISES / TRANSFERS (NEUTRAL)
        # -------------------------------------------------
        if "exercise" in ttype or "tax" in ttype:
            return "NEUTRAL"

        return "OTHER"



    def _extract_filing_context(self, filing,activity):

        if not filing or not hasattr(filing, "data"):
            return {"insider": None, "role": None, "date": None}

        data = filing.data

        insider_name = data.get("insider_name")


        ownership = data.get("ownership_summary")

        role = None
        date = None
        code = getattr(activity, "code", None)
        if ownership:
            role = getattr(ownership, "position", None)
            date = getattr(ownership, "reporting_date", None)
            if code not in ["A", "F"]:
                net_change=getattr(ownership, "net_change", None)
                net_value=getattr(ownership, "net_value", None)
                remaining_shares=getattr(ownership, "remaining_shares", None)
            elif code == "F":
                shares = getattr(activity, "shares", 0)
                net_change = -shares
                net_value = -getattr(activity, "value", 0)
                remaining_shares = getattr(ownership,"remaining_shares",None)
            elif code == "A":
                shares = getattr(activity, "shares", 0)
                net_change = shares
                net_value = getattr(activity, "value", 0)
                remaining_shares = getattr(ownership,"remaining_shares",None)



        return {
            "insider": insider_name,
            "role": role,
            "date": date,
            "net_change": net_change,
            "net_value": net_value,
            "remaining_shares": remaining_shares,
        }


    # =====================================================
    # CLUSTER BUYING DETECTION
    # =====================================================
    def _detect_cluster_buying(self, buys):

        if len(buys) < 2:
            return False

        dates = []

        for b in buys:
            if b.get("date"):
                dates.append(b["date"])

        if len(dates) < 2:
            return False

        dates = sorted(dates)

        # check if multiple buys within 7 days
        for i in range(len(dates) - 1):
            if (dates[i + 1] - dates[i]).days <= 7:
                return True

        return False




    # =====================================================
    # SCORE ENGINE
    # =====================================================
    def _calculate_score(self, transactions, cluster_buying: bool):

        score = 50

        intent_transactions = [
            t for t in transactions
            if t["type"] in ["BUY", "SELL"]
        ]

        buys = [t for t in intent_transactions if t["type"] == "BUY"]
        sells = [t for t in intent_transactions if t["type"] == "SELL"]

        total = len(intent_transactions)

        if total == 0:
            return 50

        buy_ratio = len(buys) / total
        sell_ratio = len(sells) / total

        # BUY pressure
        score += buy_ratio * 40

        # SELL pressure
        score -= sell_ratio * 40

        # cluster effect
        if cluster_buying:
            score += 10

        # heavy selling penalty
        if len(sells) >= 5:
            score -= 10

        # optional: grant signal (weak positive bias)
        grant_count = len([t for t in transactions if t["type"] == "Grant"])
        if grant_count > 10:
            score += 2

        score = max(0, min(100, score))

        return round(score, 2)

    def _generate_signals(self, transactions, cluster_buying, score):

        signals = []

        buys = [t for t in transactions if t["type"] == "BUY"]
        sells = [t for t in transactions if t["type"] == "SELL"]

        buy_value = sum(t.get("value") or 0 for t in buys)
        sell_value = sum(t.get("value") or 0 for t in sells)

        net = buy_value - sell_value

        if cluster_buying:
            signals.append({
                "signal": "CLUSTERED_ACTIVITY",
                "score": 30
            })

        if net > 50000 and buy_value > sell_value:
            signals.append({
                "signal": "ACCUMULATION",
                "score": 25
            })

        if net < -50000 and sell_value > buy_value:
            signals.append({
                "signal": "DISTRIBUTION",
                "score": 25
            })

        if score >= 75:
            signals.append({
                "signal": "BULLISH_INSIDER_SENTIMENT",
                "score": 20
            })

        if score <= 25:
            signals.append({
                "signal": "BEARISH_INSIDER_SENTIMENT",
                "score": 20
            })

        if not signals:
            signals.append({
                "signal": "NEUTRAL_ACTIVITY",
                "score": 10
            })

        return signals
    def _calculate_smart_money_score(self,insider_score,signals,transactions,cluster_buying):

        score = insider_score

        # -------------------------------------------------
        # SIGNAL STRENGTH BOOST
        # -------------------------------------------------
        signal_boost = sum(s.get("score", 0) for s in signals)
        score += signal_boost * 0.2

        # -------------------------------------------------
        # FLOW IMBALANCE (BUY vs SELL VALUE)
        # -------------------------------------------------
        buys = [t for t in transactions if t["type"] == "BUY"]
        sells = [t for t in transactions if t["type"] == "SELL"]

        buy_value = sum(t.get("value", 0) for t in buys)
        sell_value = sum(t.get("value", 0) for t in sells)

        if buy_value + sell_value > 0:
            flow_ratio = (buy_value - sell_value) / (buy_value + sell_value)
            score += flow_ratio * 20

        # -------------------------------------------------
        # CLUSTER BONUS
        # -------------------------------------------------
        if cluster_buying:
            score += 10

        # -------------------------------------------------
        # FINAL NORMALIZATION
        # -------------------------------------------------
        return max(0, min(100, score))

    def _group_signals(self, signals):

        grouped = {
            "bullish": [],
            "bearish": [],
            "neutral": []
        }

        bullish_signals = {
            "ACCUMULATION",
            "CLUSTERED_ACTIVITY",
            "BULLISH_INSIDER_SENTIMENT",
            "CEO_BUYING"
        }

        bearish_signals = {
            "DISTRIBUTION",
            "BEARISH_INSIDER_SENTIMENT",
            "HEAVY_SELLING"
        }

        for s in signals:

            name = s.get("signal")

            if name in bullish_signals:
                grouped["bullish"].append(s)

            elif name in bearish_signals:
                grouped["bearish"].append(s)

            else:
                grouped["neutral"].append(s)

        return grouped

    def _calculate_insider_momentum(self, transactions):

        buys = sum(1 for t in transactions if t["type"] == "BUY")
        sells = sum(1 for t in transactions if t["type"] == "SELL")

        if buys + sells == 0:
            return 0

        return (buys - sells) / (buys + sells)

    # =====================================================
    # CEO BUY DETECTION
    # =====================================================
    def _detect_ceo_buying(self, buys: List[Dict]) -> bool:

        for buy in buys:

            role = str(buy.get("role", "")).lower()

            if "ceo" in role:
                return True

        return False



# =========================================================
# SINGLETON
# =========================================================

insider_service = InsiderService()