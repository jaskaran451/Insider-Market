
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
            "buy_value": sum(
                self._to_float(transaction.get("value"))
                for transaction in buys
            ),
            "sell_value": sum(
                self._to_float(transaction.get("value"))
                for transaction in sells
            ),
            "tax_value": sum(
                self._to_float(transaction.get("value"))
                for transaction in taxes
            ),
            "grant_shares": sum(
                self._to_float(transaction.get("shares"))
                for transaction in grants
            ),
            "tax_shares": sum(
                self._to_float(transaction.get("shares"))
                for transaction in taxes
            ),
            "net_shares": sum(
                self._to_float(transaction.get("net_change"))
                for transaction in transactions
            ),
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
    def _normalize_transaction(
            self,
            activity,
            context,
    ) -> Optional[Dict[str, Any]]:
        """Normalize one parsed SEC transaction."""

        try:
            shares = self._to_float(
                getattr(activity, "shares", None)
            )
            value = self._to_float(
                getattr(activity, "value", None)
            )
            price = self._to_float(
                getattr(activity, "price_per_share", None)
            )

            return {
                "type": self._classify_transaction(activity),
                "shares": shares,
                "value": value,
                "price": price,
                "transaction_type": getattr(
                    activity,
                    "transaction_type",
                    None,
                ),
                "code": getattr(activity, "code", None),
                "insider": context.get("insider"),
                "role": context.get("role"),
                "date": context.get("date"),
                "net_change": self._to_float(
                    context.get("net_change")
                ),
                "net_value": self._to_float(
                    context.get("net_value")
                ),
                "remaining_shares": self._to_float(
                    context.get("remaining_shares")
                ),
            }
        except Exception as error:
            print("[INSIDER NORMALIZATION ERROR]", error)
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
        if code in ["F","M"]:
            return "Tax"
        if code in ["A"]:
            return "Grant"

        # -------------------------------------------------
        # OPTION EXERCISES / TRANSFERS (NEUTRAL)
        # -------------------------------------------------
        if "exercise" in ttype or "tax" in ttype:
            return "NEUTRAL"

        return "OTHER"

    def _extract_filing_context(self, filing, activity):
        """Extract ownership and reporting context from a filing."""

        empty_context = {
            "insider": None,
            "role": None,
            "date": None,
            "net_change": 0.0,
            "net_value": 0.0,
            "remaining_shares": 0.0,
        }

        if not filing or not hasattr(filing, "data"):
            return empty_context

        data = filing.data or {}
        ownership = data.get("ownership_summary")

        if not ownership:
            return {
                **empty_context,
                "insider": data.get("insider_name"),
            }

        code = getattr(activity, "code", None)
        shares = self._to_float(
            getattr(activity, "shares", None)
        )
        value = self._to_float(
            getattr(activity, "value", None)
        )

        net_change = self._to_float(
            getattr(ownership, "net_change", None)
        )
        net_value = self._to_float(
            getattr(ownership, "net_value", None)
        )

        if code in {"F", "M"}:
            net_change = -abs(shares)
            net_value = -abs(value)
        elif code == "A":
            net_change = abs(shares)
            net_value = abs(value)

        return {
            "insider": data.get("insider_name"),
            "role": getattr(ownership, "position", None),
            "date": getattr(
                ownership,
                "reporting_date",
                None,
            ),
            "net_change": net_change,
            "net_value": net_value,
            "remaining_shares": self._to_float(
                getattr(
                    ownership,
                    "remaining_shares",
                    None,
                )
            ),
        }


    # =====================================================
    # CLUSTER BUYING DETECTION
    # =====================================================
    def _detect_cluster_buying(self, buys):
        """Return True when at least two purchases occur within seven days."""

        if len(buys) < 2:
            return False

        dates = []

        for transaction in buys:
            transaction_date = self._to_datetime(
                transaction.get("date")
            )

            if transaction_date:
                dates.append(transaction_date)

        if len(dates) < 2:
            return False

        dates.sort()

        for current_date, next_date in zip(
                dates,
                dates[1:],
        ):
            if (next_date - current_date).days <= 7:
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

    def _generate_signals(
            self,
            transactions,
            cluster_buying,
            score,
    ):
        """Generate directional signals from normalized transactions."""

        signals = []

        buys = [
            transaction
            for transaction in transactions
            if transaction["type"] == "BUY"
        ]
        sells = [
            transaction
            for transaction in transactions
            if transaction["type"] == "SELL"
        ]

        buy_value = sum(
            self._to_float(transaction.get("value"))
            for transaction in buys
        )
        sell_value = sum(
            self._to_float(transaction.get("value"))
            for transaction in sells
        )

        net_value = buy_value - sell_value

        if cluster_buying:
            signals.append({
                "signal": "CLUSTERED_ACTIVITY",
                "score": 30,
            })

        if net_value > 50_000 and buy_value > sell_value:
            signals.append({
                "signal": "ACCUMULATION",
                "score": 25,
            })

        if net_value < -50_000 and sell_value > buy_value:
            signals.append({
                "signal": "DISTRIBUTION",
                "score": 25,
            })

        if score >= 75:
            signals.append({
                "signal": "BULLISH_INSIDER_SENTIMENT",
                "score": 20,
            })

        if score <= 25:
            signals.append({
                "signal": "BEARISH_INSIDER_SENTIMENT",
                "score": 20,
            })

        if not signals:
            signals.append({
                "signal": "NEUTRAL_ACTIVITY",
                "score": 10,
            })

        return signals

    def _calculate_smart_money_score(
            self,
            insider_score,
            signals,
            transactions,
            cluster_buying,
    ):
        """Calculate the final normalized Smart Money score."""

        score = float(insider_score)

        signal_boost = sum(
            self._to_float(signal.get("score"))
            for signal in signals
        )
        score += signal_boost * 0.2

        buys = [
            transaction
            for transaction in transactions
            if transaction["type"] == "BUY"
        ]
        sells = [
            transaction
            for transaction in transactions
            if transaction["type"] == "SELL"
        ]

        buy_value = sum(
            self._to_float(transaction.get("value"))
            for transaction in buys
        )
        sell_value = sum(
            self._to_float(transaction.get("value"))
            for transaction in sells
        )

        total_value = buy_value + sell_value

        if total_value > 0:
            flow_ratio = (
                                 buy_value - sell_value
                         ) / total_value
            score += flow_ratio * 20

        if cluster_buying:
            score += 10

        return max(5, min(95, round(score, 2)))

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

    @staticmethod
    def _to_float(value, default=0.0):
        """Convert SEC numeric values to floats safely."""

        if value is None:
            return default

        if isinstance(value, (int, float)):
            return float(value)

        try:
            cleaned_value = str(value).replace(",", "").strip()

            if not cleaned_value:
                return default

            return float(cleaned_value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _to_datetime(value):
        """Convert SEC date values to datetime objects safely."""

        if not value:
            return None

        if isinstance(value, datetime):
            return value

        if hasattr(value, "year") and hasattr(value, "month"):
            try:
                return datetime(value.year, value.month, value.day)
            except (TypeError, ValueError, AttributeError):
                return None

        date_text = str(value).strip()

        supported_formats = (
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%m/%d/%Y",
        )

        for date_format in supported_formats:
            try:
                return datetime.strptime(date_text, date_format)
            except ValueError:
                continue

        try:
            return datetime.fromisoformat(
                date_text.replace("Z", "+00:00")
            ).replace(tzinfo=None)
        except ValueError:
            return None


# =========================================================
# SINGLETON
# =========================================================

insider_service = InsiderService()