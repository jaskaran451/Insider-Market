import plotly.graph_objs as go
import plotly.offline as pyo
from collections import defaultdict
from datetime import datetime, timedelta


def create_insider_chart(transactions, months):

    buy_data = defaultdict(float)
    sell_data = defaultdict(float)

    cutoff_date = datetime.now() - timedelta(days=months * 30)

    # ----------------------------
    # FILTER + AGGREGATE
    # ----------------------------
    for t in transactions:

        date_str = t.get("date")
        shares = t.get("shares")

        if not date_str or not shares:
            continue

        try:
            tx_date = datetime.strptime(date_str, "%Y-%m-%d")
            shares = float(shares)
        except:
            continue

        if tx_date < cutoff_date:
            continue

        if t.get("type") == "Buy":
            buy_data[date_str] += shares
        else:
            sell_data[date_str] += shares

    # ----------------------------
    # SORT DATES
    # ----------------------------
    dates = sorted(set(buy_data.keys()) | set(sell_data.keys()))

    buy_values = [buy_data[d] for d in dates]
    sell_values = [sell_data[d] for d in dates]

    # ----------------------------
    # BUILD FIGURE
    # ----------------------------
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=dates,
        y=buy_values,
        mode="lines+markers",
        name="Buy",
        line=dict(color="#16a34a", width=3),
        marker=dict(size=7),
        customdata=dates,
        hovertemplate="<b>Buy</b><br>Date: %{customdata}<br>Shares: %{y:,}<extra></extra>"
    ))

    fig.add_trace(go.Scatter(
        x=dates,
        y=sell_values,
        mode="lines+markers",
        name="Sell",
        line=dict(color="#dc2626", width=3),
        marker=dict(size=7),
        customdata=dates,
        hovertemplate="<b>Sell</b><br>Date: %{customdata}<br>Shares: %{y:,}<extra></extra>"
    ))

    fig.update_layout(
        height=350,
        hovermode="x unified",
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        margin=dict(l=20, r=20, t=30, b=20),

        xaxis=dict(
            showgrid=False,
            tickfont=dict(size=11),
            tickformat="%b"
        ),

        yaxis=dict(
            title="Shares",
            gridcolor="rgba(0,0,0,0.06)"
        ),

        legend=dict(
            orientation="h",
            x=1,
            xanchor="right",
            y=1.02,
            yanchor="bottom"
        )
    )

    return fig.to_plotly_json()