document.addEventListener("DOMContentLoaded", async function () {
    // ensure clean dashboard start
    document.querySelectorAll(".content-section").forEach(section => {
        section.classList.remove("active");
    });

    const form = document.querySelector("form");
    const btn = document.getElementById("submitBtn");
    const icon = document.getElementById("btnIcon");
    const spinner = document.getElementById("spinner");

    if (form && btn && icon && spinner) {
        form.addEventListener("submit", function () {
            icon.classList.add("hidden");
            spinner.classList.remove("hidden");

            btn.disabled = true;
            btn.style.opacity = "0.7";
            btn.style.cursor = "not-allowed";

            notify("Loading data...", "info");
        });
    }


    // optional default view
    showSection("insider-section");

    const filter = document.getElementById("chartFilter");

    if (filter) {
        filter.addEventListener("change", loadChart);
    }


    document.getElementById("insiderBtn")
        .addEventListener("click", () => {
            showSection("insider-section");
        });

    document.getElementById("largeBuysBtn")
        .addEventListener("click", () => {
            showSection("largebuys-section");
        });

    document.getElementById("newsBtn")
        .addEventListener("click", () => {
            showSection("news-section");
        });
    document.getElementById("earningBtn")
        .addEventListener("click", () => {
            showSection("earning-section");
        });

    const panel = document.getElementById("smart-money-panel");

    document.getElementById("smart-money-btn").addEventListener("click", async function (e) {
        e.preventDefault();

        const ticker = window.currentSymbol;

        if (!ticker) {
            notify("Search a stock first", "warning");
            return;
        }

        await loadSmartMoney(ticker);
    });

    const earningsBtn = document.getElementById("earningBtn");

    if (earningsBtn) {
        earningsBtn.addEventListener("click", function () {
            showSection("earning-section");
        });
    }

    const closeSmartMoneyBtn = document.getElementById("closeSmartMoneyBtn");

    if (closeSmartMoneyBtn) {
        closeSmartMoneyBtn.addEventListener("click", closeSmartMoney);
    }

    async function loadSmartMoney(ticker) {
        try {
            notify("Loading Smart Money Intelligence...", "info");

            const response = await fetch(`/insider?ticker=${ticker}`);
            const result = await response.json();

            if (!result.success) {
                notify(result.message || "Failed to load Smart Money data", "error");
                return;
            }

            window.smartMoneyData = result.data;

            populateSmartMoneyPanel();
            openSmartMoneyPanel();
            renderSmartMoneyCharts();

        } catch (error) {
            console.error("error in loadSmartMoney()", error);
            notify("Failed to load Smart Money data", "error");
        }
    }

    function populateSmartMoneyPanel() {
        const data = window.smartMoneyData || {};

        const score = Number(data.smart_money_score || 0);

        document.getElementById("smScoreStatus").textContent = getSmartMoneyLabel(score);

        document.getElementById("smBuys").textContent = data.total_buys ?? 0;
        document.getElementById("smSells").textContent = data.total_sells ?? 0;
        document.getElementById("smTaxes").textContent = data.total_taxes ?? 0;
        document.getElementById("smGrants").textContent = data.total_grants ?? 0;
        document.getElementById("smMomentum").textContent = data.insider_momentum ?? 0;

        const signalList = document.getElementById("smSignalList");
        signalList.innerHTML = "";

        if (data.signals && data.signals.length > 0) {
            data.signals.forEach(signal => {
                const chip = document.createElement("div");

                const signalClass = String(signal.signal || "neutral")
                    .toLowerCase()
                    .replaceAll("_", "-")
                    .replaceAll(" ", "-");

                chip.className = `signal-chip ${signalClass}`;
                chip.textContent = `${String(signal.signal || "Signal").replaceAll("_", " ")} (${signal.score ?? 0})`;

                signalList.appendChild(chip);
            });
        } else {
            signalList.innerHTML = `<div class="signal-chip neutral">No strong signal detected</div>`;
        }
    }

    function getSmartMoneyLabel(score) {
        if (score >= 80) return "Strong Accumulation";
        if (score >= 65) return "Bullish";
        if (score >= 45) return "Neutral";
        if (score >= 25) return "Bearish";
        return "Heavy Distribution";
    }


    function openSmartMoneyPanel() {
        const panel = document.getElementById("smart-money-panel");

        document.querySelectorAll(".content-section").forEach(section => {
            section.classList.remove("active");
        });

        panel.classList.remove("hidden");

        setTimeout(() => {
            panel.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });
        }, 100);
    }

    function closeSmartMoney() {
        const panel = document.getElementById("smart-money-panel");

        panel.classList.add("hidden");

        showSection("insider-section");

        const resultsSection = document.getElementById("resultsSection");

        if (resultsSection) {
            setTimeout(() => {
                resultsSection.scrollIntoView({
                    behavior: "smooth",
                    block: "start"
                });
            }, 100);
        }
    }

    function renderSmartMoneyCharts() {
        renderGauge();
        renderDonut();
        renderRadar();
        renderOwnership();
        renderTimeline();
        renderLeaderboard();
    }

    window.smartMoneyGaugeChart = window.smartMoneyGaugeChart || null;
    window.activityDonutChart = window.activityDonutChart || null;

    function renderGauge() {
        const canvas = document.getElementById("smartMoneyGauge");

        if (!canvas) return;

        if (window.smartMoneyGaugeChart) {
            window.smartMoneyGaugeChart.destroy();
            window.smartMoneyGaugeChart = null;
        }

        const score = Number(window.smartMoneyData.smart_money_score || 0);
        const remaining = Math.max(0, 100 - score);

        window.smartMoneyGaugeChart = new Chart(canvas, {
            type: "doughnut",
            data: {
                datasets: [{
                    data: [score, remaining],
                    backgroundColor: [
                        score > 65 ? "#22c55e" : score > 40 ? "#facc15" : "#ef4444",
                        "#e5e7eb"
                    ],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "72%",
                plugins: {
                    tooltip: {enabled: false},
                    legend: {display: false}
                }
            },
            plugins: [{
                id: "smartMoneyCenterText",
                beforeDraw(chart) {
                    const {width, height} = chart;
                    const ctx = chart.ctx;

                    ctx.save();
                    ctx.textAlign = "center";
                    ctx.textBaseline = "middle";

                    ctx.font = "900 42px Arial";
                    ctx.fillStyle = "#102033";
                    ctx.fillText(`${score}`, width / 2, height / 2 - 12);

                    ctx.font = "700 15px Arial";
                    ctx.fillStyle = "#64748b";
                    ctx.fillText("Smart Money", width / 2, height / 2 + 26);

                    ctx.restore();
                }
            }]
        });
    }

    function renderLeaderboard() {
        const container = document.getElementById("leaderboardContainer");

        if (!container) return;

        container.innerHTML = "";

        const transactions = window.smartMoneyData.recent_transactions || [];

        if (!transactions.length) {
            container.innerHTML = `<div class="empty-state">No insider activity available.</div>`;
            return;
        }

        transactions.slice(0, 10).forEach(t => {
            const row = document.createElement("div");
            row.className = "leaderboard-row";

            row.innerHTML = `
            <div>
                <strong>${t.insider || "Unknown Insider"}</strong>
                <span>${t.title || t.type || "Transaction"}</span>
            </div>
            <div>
                <strong>${Number(t.shares || 0).toLocaleString()}</strong>
                <span>Shares</span>
            </div>
        `;

            container.appendChild(row);
        });
    }

    function renderDonut() {
        const canvas = document.getElementById("activityDonut");

        if (!canvas) return;

        if (window.activityDonutChart) {
            window.activityDonutChart.destroy();
            window.activityDonutChart = null;
        }

        const data = window.smartMoneyData || {};

        const buys = Number(data.total_buys || 0);
        const sells = Number(data.total_sells || 0);
        const taxes = Number(data.total_taxes || 0);
        const grants = Number(data.total_grants || 0);

        window.activityDonutChart = new Chart(canvas, {
            type: "doughnut",
            data: {
                labels: ["Buys", "Sells", "Taxes", "Grants"],
                datasets: [{
                    data: [buys, sells, taxes, grants],
                    backgroundColor: [
                        "#22c55e",
                        "#ef4444",
                        "#f59e0b",
                        "#3b82f6"
                    ],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "68%",
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: {
                            usePointStyle: true,
                            boxWidth: 10,
                            font: {
                                size: 13,
                                weight: "700"
                            }
                        }
                    }
                }
            }
        });
    }

    window.signalRadarChart = window.signalRadarChart || null;

    function renderRadar() {
        const canvas = document.getElementById("signalRadar");

        if (!canvas) {
            return;
        }

        if (window.signalRadarChart) {
            window.signalRadarChart.destroy();
            window.signalRadarChart = null;
        }

        const signals = window.smartMoneyData.signals || [];
        const labels = signals.map(s => s.signal.replaceAll("_", " "));
        const values = signals.map(s => s.score);

        window.signalRadarChart = new Chart(canvas, {
            type: "bar",
            data: {
                labels: labels,
                datasets: [{
                    label: "Signal Strength",
                    data: values,
                    backgroundColor: signals.map(s => {
                        const name = s.signal.toLowerCase();
                        if (name.includes("bearish") || name.includes("distribution")) return "#ef4444";
                        if (name.includes("bullish") || name.includes("accumulation")) return "#22c55e";
                        return "#60a5fa";
                    }),
                    borderRadius: 10,
                    barThickness: 28
                }]
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                resizeDelay: 100,
                plugins: {
                    legend: {display: false},
                    tooltip: {enabled: true}
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        max: 100,
                        grid: {color: "rgba(15,23,42,.08)"},
                        ticks: {color: "#64748b"}
                    },
                    y: {
                        grid: {display: false},
                        ticks: {
                            color: "#111827",
                            font: {weight: "700"}
                        }
                    }
                }
            }
        });
    }


    function renderOwnership() {
        const container = document.getElementById("ownershipBars");

        if (!container) return;

        container.innerHTML = "";

        const transactions = window.smartMoneyData.recent_transactions || [];

        if (!transactions.length) {
            container.innerHTML = `<div class="empty-state">No ownership data available.</div>`;
            return;
        }

        const grouped = {};

        transactions.forEach(t => {
            const name = t.insider || "Unknown";
            grouped[name] = (grouped[name] || 0) + Number(t.shares || 0);
        });

        const values = Object.values(grouped);
        const max = Math.max(...values);

        if (!max || max <= 0) {
            container.innerHTML = `<div class="empty-state">No ownership data available.</div>`;
            return;
        }

        Object.entries(grouped).forEach(([name, value]) => {
            const bar = document.createElement("div");
            bar.className = "ownership-row";

            bar.innerHTML = `
            <div class="label">${name}</div>
            <div class="bar">
                <div class="fill" style="width:${(value / max) * 100}%"></div>
            </div>
            <div class="value">${Number(value).toLocaleString()}</div>
        `;

            container.appendChild(bar);
        });
    }


    function renderTimeline() {

        const container = document.getElementById("timelineContainer");
        container.innerHTML = "";

        const sorted = smartMoneyData.recent_transactions
            .slice()
            .sort((a, b) => new Date(b.date) - new Date(a.date));

        sorted.forEach(t => {

            const div = document.createElement("div");
            div.className = "timeline-item";

            const color =
                t.type === "BUY" ? "green" :
                    t.type === "SELL" ? "red" :
                        t.type === "Tax" ? "orange" : "blue";

            div.innerHTML = `
                <div class="dot ${color}"></div>
                <div class="content">
                    <div>${t.date}</div>
                    <div><b>${t.insider}</b> → ${t.type}</div>
                    <div>${t.shares} shares</div>
                </div>
            `;

            container.appendChild(div);
        });
    }

    const companyInfoDrawer = document.getElementById("companyInfoDrawer");
    const companyInfoToggle = document.getElementById("companyInfoToggle");
    const companyInfoClose = document.getElementById("companyInfoClose");

    if (companyInfoToggle && companyInfoDrawer) {
        companyInfoToggle.addEventListener("click", () => {
            companyInfoDrawer.classList.toggle("open");
        });
    }

    if (companyInfoClose && companyInfoDrawer) {
        companyInfoClose.addEventListener("click", () => {
            companyInfoDrawer.classList.remove("open");
        });
    }

    function setText(id, value) {
        const el = document.getElementById(id);

        if (!el) {
            console.error("Missing company info element:", id);
            return;
        }

        el.textContent = value || "--";
    }

    async function loadCompanyInfo(symbol) {
        try {
            console.log("Loading company info for:", symbol);

            const response = await fetch(`/company-info/${symbol}`);
            const result = await response.json();

            console.log("Company info result:", result);

            if (!result.success) {
                console.error(result.message || "Company info failed");
                return;
            }

            const data = result.data || {};

            // Snapshot
            setText("companyInfoName", data.snapshot?.name);
            setText("companyInfoSector", data.snapshot?.sector);

            const websiteEl = document.getElementById("companyInfoWebsite");

            if (websiteEl) {
                if (data.snapshot?.website) {
                    websiteEl.textContent = data.snapshot.website.replace(/^https?:\/\//, "");
                    websiteEl.href = data.snapshot.website;
                } else {
                    websiteEl.textContent = "--";
                    websiteEl.href = "#";
                }
            }

            // Market data
            setText("companyMarketPrice", data.market?.price);
            setText("companyPreviousClose", data.market?.previous_close);
            setText("companyOpen", data.market?.open);
            setText("companyVolume", data.market?.volume);
            setText("companyDayRange", data.market?.day_range);
            setText("company52WeekRange", data.market?.week_52_range);
            setText("companyMarketCap", data.market?.market_cap);

            // Valuation
            setText("companyForwardPE", data.valuation?.forward_pe);
            setText("companyPriceBook", data.valuation?.price_to_book);
            setText("companyPriceSales", data.valuation?.price_to_sales);
            setText("companyEnterpriseValue", data.valuation?.enterprise_value);
            setText("companyBeta", data.valuation?.beta);

            // Financial health
            setText("companyRevenue", data.financial_health?.revenue);
            setText("companyGrossMargin", data.financial_health?.gross_margin);
            setText("companyOperatingMargin", data.financial_health?.operating_margin);
            setText("companyProfitMargin", data.financial_health?.profit_margin);
            setText("companyFreeCashFlow", data.financial_health?.free_cashflow);
            setText("companyTotalCash", data.financial_health?.total_cash);
            setText("companyTotalDebt", data.financial_health?.total_debt);

            // Analyst view
            setText("companyTargetLow", data.analyst?.target_low);
            setText("companyTargetMean", data.analyst?.target_mean);
            setText("companyTargetHigh", data.analyst?.target_high);
            setText("companyAnalystOpinions", data.analyst?.analyst_opinions);

        } catch (error) {
            console.error("Company info loading failed:", error);
        }
    }

    if (window.currentSymbol) {
        loadCompanyInfo(window.currentSymbol);
    }

});

function showSection(sectionId) {

   document.querySelectorAll(".content-section").forEach(section => {
        section.classList.remove("active");
    });
    document.getElementById(sectionId).classList.remove("hidden");
    document.getElementById(sectionId).classList.add("active");
}
let chartVisible = false;

async function toggleChart() {

    const wrapper = document.getElementById("chartWrapper");

    chartVisible = !chartVisible;

    if (chartVisible) {

        wrapper.classList.remove("hidden");

        await loadChart();

    } else {

        wrapper.classList.add("hidden");
    }
}
async function loadChart() {

    const dropdown = document.getElementById("chartFilter");
    const months = dropdown.value;

    // IMPORTANT: symbol must come from a stable global variable
    const symbol = window.currentSymbol;

    if (!symbol) {
        console.error("Symbol is missing");
        return;
    }
    const url = `/chart/${symbol}/${months}`;

    try {
        const response = await fetch(url);
        const data = await response.json();

        const chartContainer = document.getElementById("chartContainer");

        if (data.chart) {
            Plotly.react(
            "chartContainer",
            data.chart.data,
            data.chart.layout
            );
        } else {
            chartContainer.innerHTML = "<p>No chart data available</p>";
        }

    } catch (error) {
        console.error("Chart loading failed:", error);
    }
}

