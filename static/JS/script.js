document.addEventListener("DOMContentLoaded", function () {

    "use strict";

    /* =========================================================
       1. GLOBAL STATE
       ========================================================= */

    let dashboardAiLottie = null;

    window.smartMoneyGaugeChart = window.smartMoneyGaugeChart || null;
    window.activityDonutChart = window.activityDonutChart || null;
    window.signalRadarChart = window.signalRadarChart || null;


    /* =========================================================
       2. BASIC HELPERS
       ========================================================= */

    function getEl(id) {
        return document.getElementById(id);
    }

    function safeSetText(id, value) {
        const el = getEl(id);

        if (!el) return;

        el.textContent = value || "--";
    }

    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    function escapeHTML(value) {
        return String(value)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }


    /* =========================================================
       3. INITIAL PAGE SETUP
       ========================================================= */

    document.querySelectorAll(".content-section").forEach(section => {
        section.classList.remove("active");
    });

    showSection("insider-section", false);

    const form = document.querySelector("form");
    const btn = getEl("submitBtn");
    const icon = getEl("btnIcon");
    const spinner = getEl("spinner");

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

    const filter = getEl("chartFilter");

    if (filter) {
        filter.addEventListener("change", loadChart);
    }


    /* =========================================================
       4. RESULT TAB BUTTONS
       ========================================================= */

    function setActivePanel(activeBtnId) {
        document.querySelectorAll(".panel").forEach(function (btn) {
            btn.classList.remove("active");
        });

        const activeBtn = getEl(activeBtnId);

        if (activeBtn) {
            activeBtn.classList.add("active");
        }
    }

    const insiderBtn = getEl("insiderBtn");
    const largeBuysBtn = getEl("largeBuysBtn");
    const newsBtn = getEl("newsBtn");
    const earningBtn = getEl("earningBtn");

    if (insiderBtn) {
        insiderBtn.addEventListener("click", function () {
            showSection("insider-section");
            setActivePanel("insiderBtn");
        });
    }

    if (largeBuysBtn) {
        largeBuysBtn.addEventListener("click", function () {
            showSection("largebuys-section");
            setActivePanel("largeBuysBtn");
        });
    }

    if (newsBtn) {
        newsBtn.addEventListener("click", function () {
            showSection("news-section");
            setActivePanel("newsBtn");
        });
    }

    if (earningBtn) {
        earningBtn.addEventListener("click", function () {
            showSection("earning-section");
            setActivePanel("earningBtn");
        });
    }


    /* =========================================================
       5. SMART MONEY PANEL
       ========================================================= */

    const smartMoneyBtn = getEl("smart-money-btn");
    const closeSmartMoneyBtn = getEl("closeSmartMoneyBtn");

    if (smartMoneyBtn) {
        smartMoneyBtn.addEventListener("click", async function (event) {
            event.preventDefault();

            const ticker = window.currentSymbol;

            if (!ticker) {
                notify("Search a stock first", "warning");
                return;
            }

            await loadSmartMoney(ticker);
        });
    }

    if (closeSmartMoneyBtn) {
        closeSmartMoneyBtn.addEventListener("click", closeSmartMoney);
    }

    window.loadSmartMoney = async function loadSmartMoney(ticker) {
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

        safeSetText("smScoreStatus", getSmartMoneyLabel(score));
        safeSetText("smBuys", data.total_buys ?? 0);
        safeSetText("smSells", data.total_sells ?? 0);
        safeSetText("smTaxes", data.total_taxes ?? 0);
        safeSetText("smGrants", data.total_grants ?? 0);
        safeSetText("smMomentum", data.insider_momentum ?? 0);

        const signalList = getEl("smSignalList");

        if (!signalList) return;

        signalList.innerHTML = "";

        if (data.signals && data.signals.length > 0) {
            data.signals.forEach(function (signal) {
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
        const panel = getEl("smart-money-panel");

        if (!panel) return;

        document.querySelectorAll(".content-section").forEach(function (section) {
            section.classList.remove("active");
        });

        panel.classList.remove("hidden");

        setTimeout(function () {
            panel.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });
        }, 100);
    }

    function closeSmartMoney() {
        const panel = getEl("smart-money-panel");

        if (panel) {
            panel.classList.add("hidden");
        }

        showSection("insider-section");

        const resultsSection = getEl("resultsSection");

        if (resultsSection) {
            setTimeout(function () {
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
        /* =========================================================
       6. SMART MONEY CHARTS
       ========================================================= */

    function renderGauge() {
        const canvas = getEl("smartMoneyGauge");

        if (!canvas || !window.Chart) return;

        if (window.smartMoneyGaugeChart) {
            window.smartMoneyGaugeChart.destroy();
            window.smartMoneyGaugeChart = null;
        }

        const score = Number(window.smartMoneyData?.smart_money_score || 0);
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
                    tooltip: { enabled: false },
                    legend: { display: false }
                }
            },
            plugins: [{
                id: "smartMoneyCenterText",
                beforeDraw(chart) {
                    const { width, height } = chart;
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

    function renderDonut() {
        const canvas = getEl("activityDonut");

        if (!canvas || !window.Chart) return;

        if (window.activityDonutChart) {
            window.activityDonutChart.destroy();
            window.activityDonutChart = null;
        }

        const data = window.smartMoneyData || {};

        window.activityDonutChart = new Chart(canvas, {
            type: "doughnut",
            data: {
                labels: ["Buys", "Sells", "Taxes", "Grants"],
                datasets: [{
                    data: [
                        Number(data.total_buys || 0),
                        Number(data.total_sells || 0),
                        Number(data.total_taxes || 0),
                        Number(data.total_grants || 0)
                    ],
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

    function renderRadar() {
        const canvas = getEl("signalRadar");

        if (!canvas || !window.Chart) return;

        if (window.signalRadarChart) {
            window.signalRadarChart.destroy();
            window.signalRadarChart = null;
        }

        const signals = window.smartMoneyData?.signals || [];
        const labels = signals.map(function (signal) {
            return String(signal.signal || "Signal").replaceAll("_", " ");
        });
        const values = signals.map(function (signal) {
            return Number(signal.score || 0);
        });

        window.signalRadarChart = new Chart(canvas, {
            type: "bar",
            data: {
                labels: labels,
                datasets: [{
                    label: "Signal Strength",
                    data: values,
                    backgroundColor: signals.map(function (signal) {
                        const name = String(signal.signal || "").toLowerCase();

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
                    legend: { display: false },
                    tooltip: { enabled: true }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        max: 100,
                        grid: { color: "rgba(15,23,42,.08)" },
                        ticks: { color: "#64748b" }
                    },
                    y: {
                        grid: { display: false },
                        ticks: {
                            color: "#111827",
                            font: { weight: "700" }
                        }
                    }
                }
            }
        });
    }

    function renderLeaderboard() {
        const container = getEl("leaderboardContainer");

        if (!container) return;

        const transactions = window.smartMoneyData?.recent_transactions || [];

        if (!transactions.length) {
            container.innerHTML = `<div class="empty-state">No insider activity available.</div>`;
            return;
        }

        container.innerHTML = transactions.slice(0, 10).map(function (transaction) {
            return `
                <div class="leaderboard-row">
                    <div>
                        <strong>${escapeHTML(transaction.insider || "Unknown Insider")}</strong>
                        <span>${escapeHTML(transaction.title || transaction.type || "Transaction")}</span>
                    </div>
                    <div>
                        <strong>${Number(transaction.shares || 0).toLocaleString()}</strong>
                        <span>Shares</span>
                    </div>
                </div>
            `;
        }).join("");
    }

    function renderOwnership() {
        const container = getEl("ownershipBars");

        if (!container) return;

        const transactions = window.smartMoneyData?.recent_transactions || [];

        if (!transactions.length) {
            container.innerHTML = `<div class="empty-state">No ownership data available.</div>`;
            return;
        }

        const grouped = {};

        transactions.forEach(function (transaction) {
            const name = transaction.insider || "Unknown";
            grouped[name] = (grouped[name] || 0) + Number(transaction.shares || 0);
        });

        const values = Object.values(grouped);
        const max = Math.max(...values);

        if (!max || max <= 0) {
            container.innerHTML = `<div class="empty-state">No ownership data available.</div>`;
            return;
        }

        container.innerHTML = Object.entries(grouped).map(function ([name, value]) {
            return `
                <div class="ownership-row">
                    <div class="label">${escapeHTML(name)}</div>
                    <div class="bar">
                        <div class="fill" style="width:${(value / max) * 100}%"></div>
                    </div>
                    <div class="value">${Number(value).toLocaleString()}</div>
                </div>
            `;
        }).join("");
    }

    function renderTimeline() {
        const container = getEl("timelineContainer");

        if (!container) return;

        const transactions = window.smartMoneyData?.recent_transactions || [];

        if (!transactions.length) {
            container.innerHTML = `<div class="empty-state">No timeline data available.</div>`;
            return;
        }

        const sorted = transactions
            .slice()
            .sort(function (a, b) {
                return new Date(b.date) - new Date(a.date);
            });

        container.innerHTML = sorted.map(function (transaction) {
            const color =
                transaction.type === "BUY" ? "green" :
                transaction.type === "SELL" ? "red" :
                transaction.type === "Tax" ? "orange" : "blue";

            return `
                <div class="timeline-item">
                    <div class="dot ${color}"></div>
                    <div class="content">
                        <div>${escapeHTML(transaction.date || "--")}</div>
                        <div><b>${escapeHTML(transaction.insider || "Unknown")}</b> → ${escapeHTML(transaction.type || "Transaction")}</div>
                        <div>${Number(transaction.shares || 0).toLocaleString()} shares</div>
                    </div>
                </div>
            `;
        }).join("");
    }
        /* =========================================================
       7. COMPANY INFO DRAWER
       ========================================================= */

    const companyInfoDrawer = getEl("companyInfoDrawer");
    const companyInfoToggle = getEl("companyInfoToggle");
    const companyInfoClose = getEl("companyInfoClose");

    if (companyInfoToggle && companyInfoDrawer) {
        companyInfoToggle.addEventListener("click", function () {
            companyInfoDrawer.classList.toggle("open");
        });
    }

    if (companyInfoClose && companyInfoDrawer) {
        companyInfoClose.addEventListener("click", function () {
            companyInfoDrawer.classList.remove("open");
        });
    }

    async function loadCompanyInfo(symbol) {
        try {
            console.log("Loading company info for:", symbol);

            const response = await fetch(`/company-info/${symbol}`);
            const result = await response.json();

            if (!result.success) {
                console.error(result.message || "Company info failed");
                return;
            }

            const data = result.data || {};

            safeSetText("companyInfoName", data.snapshot?.name);
            safeSetText("companyInfoSector", data.snapshot?.sector);

            const websiteEl = getEl("companyInfoWebsite");

            if (websiteEl) {
                if (data.snapshot?.website) {
                    websiteEl.textContent = data.snapshot.website.replace(/^https?:\/\//, "");
                    websiteEl.href = data.snapshot.website;
                } else {
                    websiteEl.textContent = "--";
                    websiteEl.href = "#";
                }
            }

            safeSetText("companyMarketPrice", data.market?.price);
            safeSetText("companyPreviousClose", data.market?.previous_close);
            safeSetText("companyOpen", data.market?.open);
            safeSetText("companyVolume", data.market?.volume);
            safeSetText("companyDayRange", data.market?.day_range);
            safeSetText("company52WeekRange", data.market?.week_52_range);
            safeSetText("companyMarketCap", data.market?.market_cap);

            safeSetText("companyForwardPE", data.valuation?.forward_pe);
            safeSetText("companyPriceBook", data.valuation?.price_to_book);
            safeSetText("companyPriceSales", data.valuation?.price_to_sales);
            safeSetText("companyEnterpriseValue", data.valuation?.enterprise_value);
            safeSetText("companyBeta", data.valuation?.beta);

            safeSetText("companyRevenue", data.financial_health?.revenue);
            safeSetText("companyGrossMargin", data.financial_health?.gross_margin);
            safeSetText("companyOperatingMargin", data.financial_health?.operating_margin);
            safeSetText("companyProfitMargin", data.financial_health?.profit_margin);
            safeSetText("companyFreeCashFlow", data.financial_health?.free_cashflow);
            safeSetText("companyTotalCash", data.financial_health?.total_cash);
            safeSetText("companyTotalDebt", data.financial_health?.total_debt);

            safeSetText("companyTargetLow", data.analyst?.target_low);
            safeSetText("companyTargetMean", data.analyst?.target_mean);
            safeSetText("companyTargetHigh", data.analyst?.target_high);
            safeSetText("companyAnalystOpinions", data.analyst?.analyst_opinions);

        } catch (error) {
            console.error("Company info loading failed:", error);
        }
    }

    if (window.currentSymbol) {
        loadCompanyInfo(window.currentSymbol);
    }


    /* =========================================================
       8. AI COMPANY ANALYSIS STREAMING
       ========================================================= */

    const analyzeCompanyWithAiBtn = getEl("analyzeCompanyWithAiBtn");

    if (analyzeCompanyWithAiBtn) {
        analyzeCompanyWithAiBtn.addEventListener("click", analyzeCompanyDashboardWithAI);
    }

    function expandDashboardAICard() {
        const card = getEl("dashboardAiCard");

        if (!card) return;

        card.classList.remove("ai-card-compact");
        card.classList.add("ai-card-expanded");

        setTimeout(function () {
            card.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });
        }, 180);
    }

    function showDashboardAILottieThinking() {
        const body = getEl("dashboardAiBody");

        if (!body) return;

        body.innerHTML = `
            <div class="ai-lottie-panel">
                <div class="ai-lottie-bg" id="dashboardAiLottie"></div>
                <div class="ai-lottie-overlay"></div>

                <div class="ai-lottie-content">
                    <p class="ai-lottie-title">Analyzing company intelligence...</p>

                    <p class="ai-lottie-subtitle">
                        Ollama is reading insider activity, institutional holdings, news themes,
                        and earnings transcript commentary to identify business signals and risks.
                    </p>
                </div>
            </div>
        `;

        const container = getEl("dashboardAiLottie");

        if (!container || !window.lottie) {
            return;
        }

        if (dashboardAiLottie) {
            dashboardAiLottie.destroy();
            dashboardAiLottie = null;
        }

        try {
            dashboardAiLottie = lottie.loadAnimation({
                container: container,
                renderer: "svg",
                loop: true,
                autoplay: true,
                path: "/static/animations/ai-thinking.json"
            });

            dashboardAiLottie.addEventListener("data_failed", function () {
                console.error("Dashboard Lottie failed to load. Check /static/animations/ai-thinking.json");
            });

        } catch (error) {
            console.error("Dashboard Lottie init failed:", error);
        }
    }

    function showDashboardAIStreamBox() {
        const body = getEl("dashboardAiBody");

        if (!body) return null;

        if (dashboardAiLottie) {
            dashboardAiLottie.destroy();
            dashboardAiLottie = null;
        }

        body.innerHTML = `
            <div class="dashboard-ai-success streaming" id="dashboardAiStreamText"></div>
        `;

        return getEl("dashboardAiStreamText");
    }

    async function analyzeCompanyDashboardWithAI() {
        const body = getEl("dashboardAiBody");
        const button = getEl("analyzeCompanyWithAiBtn");
        const symbol = window.currentSymbol;

        if (!symbol) {
            expandDashboardAICard();

            if (body) {
                body.innerHTML = `
                    <div class="dashboard-ai-unavailable">
                        Search a company first before using AI company analysis.
                    </div>
                `;
            }

            return;
        }

        expandDashboardAICard();
        showDashboardAILottieThinking();

        if (typeof setButtonLoading === "function") {
            setButtonLoading(button, true);
        } else if (button) {
            button.disabled = true;
        }

        try {
            const response = await fetch(`/api/company-dashboard/${encodeURIComponent(symbol)}/ai-analysis-stream`, {
                method: "POST"
            });

            if (!response.ok || !response.body) {
                throw new Error("AI stream failed.");
            }

            const output = showDashboardAIStreamBox();
            const aiBody = getEl("dashboardAiBody");

            if (aiBody) {
                aiBody.dataset.userScrolled = "false";

                aiBody.addEventListener("scroll", function () {
                    const distanceFromBottom =
                        aiBody.scrollHeight - aiBody.scrollTop - aiBody.clientHeight;

                    aiBody.dataset.userScrolled = distanceFromBottom > 80 ? "true" : "false";
                });
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");

            let fullText = "";

            while (true) {
                const result = await reader.read();

                if (result.done) {
                    break;
                }

                const chunk = decoder.decode(result.value, {
                    stream: true
                });

                fullText += chunk;

                await sleep(35);

                if (output) {
                    output.textContent = fullText;

                    if (aiBody && aiBody.dataset.userScrolled !== "true") {
                        aiBody.scrollTop = aiBody.scrollHeight;
                    }
                }
            }

            if (output) {
                output.classList.remove("streaming");
            }

            if (!fullText.trim() && output) {
                output.textContent = "AI analysis returned an empty response.";
            }

        } catch (error) {
            console.error("Dashboard AI frontend error:", error);

            if (dashboardAiLottie) {
                dashboardAiLottie.destroy();
                dashboardAiLottie = null;
            }

            if (body) {
                body.innerHTML = `
                    <div class="dashboard-ai-unavailable">
                        AI company analysis failed: ${escapeHTML(error.message || "Unknown error")}
                    </div>
                `;
            }

        } finally {
            if (typeof setButtonLoading === "function") {
                setButtonLoading(button, false);
            } else if (button) {
                button.disabled = false;
            }
        }
    }


    /* =========================================================
       9. AUTO SCROLL AFTER SEARCH
       ========================================================= */

    if (window.currentSymbol && window.currentSymbol.trim() !== "") {
        setTimeout(function () {
            smoothScrollToResults();
        }, 350);
    }

});

/* =========================================================
   GLOBAL FUNCTIONS
   These stay outside DOMContentLoaded because HTML buttons
   may call them directly with onclick.
   ========================================================= */

function showSection(sectionId, shouldScroll = true) {
    document.querySelectorAll(".content-section").forEach(function (section) {
        section.classList.remove("active");
    });

    const targetSection = document.getElementById(sectionId);

    if (!targetSection) {
        console.error("Section not found:", sectionId);
        return;
    }

    targetSection.classList.add("active");

    if (shouldScroll) {
        setTimeout(function () {
            smoothScrollToResults();
        }, 80);
    }
}

let chartVisible = false;

async function toggleChart() {
    const wrapper = document.getElementById("chartWrapper");

    if (!wrapper) return;

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

    if (!dropdown) return;

    const months = dropdown.value;
    const symbol = window.currentSymbol;

    if (!symbol) {
        console.error("Symbol is missing");
        return;
    }

    try {
        const response = await fetch(`/chart/${symbol}/${months}`);
        const data = await response.json();

        const chartContainer = document.getElementById("chartContainer");

        if (data.chart) {
            Plotly.react(
                "chartContainer",
                data.chart.data,
                data.chart.layout
            );
        } else if (chartContainer) {
            chartContainer.innerHTML = "<p>No chart data available</p>";
        }

    } catch (error) {
        console.error("Chart loading failed:", error);
    }
}

function smoothScrollToResults() {
    const resultsSection = document.getElementById("resultsSection");

    if (!resultsSection) return;

    resultsSection.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
}
(function(){
    "use strict";

    const dashboardState={
        insiders:"idle",
        institutions:"idle",
        news:"idle",
        earnings:"idle"
    };

    function escapeDashboardHTML(value){
        return String(value??"")
            .replaceAll("&","&amp;")
            .replaceAll("<","&lt;")
            .replaceAll(">","&gt;")
            .replaceAll('"',"&quot;")
            .replaceAll("'","&#039;");
    }

    function formatDashboardNumber(value){
        const number=Number(value);
        return Number.isFinite(number)?number.toLocaleString():escapeDashboardHTML(value||"--");
    }

    function setTabStatus(id,status){
        const indicator=document.getElementById(id);
        if(!indicator)return;
        indicator.className=`panel-status ${status}`;
        indicator.setAttribute("aria-label",status);
    }

    function loadingCard(title,message,stage){
        return `
            <div class="dashboard-loading-card">
                <div class="dashboard-loader"></div>
                <div>
                    <strong>${escapeDashboardHTML(title)}</strong>
                    <p>${escapeDashboardHTML(message)}</p>
                    <span class="dashboard-loading-stage">${escapeDashboardHTML(stage)}</span>
                </div>
            </div>
        `;
    }

    function errorCard(section,message){
        return `
            <div class="dashboard-error-card">
                <div class="dashboard-error-icon">!</div>
                <div>
                    <strong>This section could not be loaded</strong>
                    <p>${escapeDashboardHTML(message)}</p>
                    <button type="button" class="dashboard-retry-btn" data-retry-section="${section}">Retry</button>
                </div>
            </div>
        `;
    }

    async function fetchJSON(url){
        const response=await fetch(url,{headers:{"Accept":"application/json"}});
        const payload=await response.json().catch(()=>({}));
        if(!response.ok||payload.success===false){
            throw new Error(payload.message||`Request failed with status ${response.status}`);
        }
        return payload;
    }

    function insiderHTML(transactions,symbol,companyName){
        if(!transactions.length){
            return `<div class="empty-state"><h3>No insider transactions found</h3><p>No recent Form 4 transactions were returned for ${escapeDashboardHTML(symbol)}.</p></div>`;
        }
        const cards=transactions.map(t=>`
            <div class="result-card">
                <div class="card-top">
                    <div><h3>${escapeDashboardHTML(t.executive||"Unknown Insider")}</h3><span class="title">${escapeDashboardHTML(t.title||"Insider")}</span></div>
                    <span class="${t.type==="Buy"?"buy":t.type==="Sell"?"sell":"neutral"}">${escapeDashboardHTML(t.type||"Other")}</span>
                </div>
                <div class="card-details">
                    <div class="detail-item"><span>Date</span><strong>${escapeDashboardHTML(t.date||"--")}</strong></div>
                    <div class="detail-item"><span>Shares</span><strong>${formatDashboardNumber(t.shares)}</strong></div>
                    <div class="detail-item"><span>Price</span><strong>${t.price?"$"+escapeDashboardHTML(t.price):"--"}</strong></div>
                    <div class="detail-item"><span>Security</span><strong>${escapeDashboardHTML(t.security||"--")}</strong></div>
                    <div class="detail-item"><span>Value</span><strong>${t.shares_value?"$"+formatDashboardNumber(t.shares_value):"--"}</strong></div>
                    <div class="detail-item"><span>SEC Filing</span><strong>${t.sec_link?`<a class="sec-link" href="${escapeDashboardHTML(t.sec_link)}" target="_blank" rel="noopener noreferrer">View Filing</a>`:"--"}</strong></div>
                </div>
            </div>
        `).join("");
        return `
            <div class="results-header">
                <div class="company-header">
                    <h2 class="company-name">${escapeDashboardHTML(companyName)} (${escapeDashboardHTML(symbol)})</h2>
                    <div class="header-actions">
                        <span class="chart-btn" onclick="toggleChart()">📊<span class="chart-tooltip">Open chart</span></span>
                        <a href="#" id="smart-money-btn"><img src="../static/grok.svg" class="smart-money-icon" alt="Smart Money"></a>
                    </div>
                </div>
                <p>Insider transaction activity</p>
            </div>
            <div class="chart-wrapper hidden" id="chartWrapper">
                <div class="chart-toolbar"><select id="chartFilter" class="chart-filter"><option value="3">Last 3 Months</option><option value="6">Last 6 Months</option><option value="12">Last 1 Year</option></select></div>
                <div id="chartContainer" data-symbol="${escapeDashboardHTML(symbol)}"></div>
            </div>
            <div class="results-grid">${cards}</div>
        `;
    }

    function institutionHTML(rows,summary,symbol){
        const items=[
            ["Total Holders",summary.total_holders],["Total Shares",summary.total_shares],["Ownership %",summary.ownership_pct],
            ["Increased Holders",summary.increased_holders],["Increased Shares",summary.increased_shares],["Decreased Holders",summary.decreased_holders],
            ["Decreased Shares",summary.decreased_shares],["Unchanged Holders",summary.unchanged_holders]
        ];
        const summaryHTML=items.map(([label,value])=>`<div class="summary-card"><span>${label}</span><strong>${formatDashboardNumber(value)}</strong></div>`).join("");
        const cards=rows.length?rows.map(h=>`
            <div class="result-card">
                <div class="card-top"><div><h3>${escapeDashboardHTML(h.holder||"Unknown Holder")}</h3><span class="title">Institutional Holder</span></div><span class="${escapeDashboardHTML(h.css||"neutral")}">${escapeDashboardHTML(h.type||"Hold")}</span></div>
                <div class="card-details">
                    <div class="detail-item"><span>Shares Held</span><strong>${formatDashboardNumber(h.shares)}</strong></div>
                    <div class="detail-item"><span>Change</span><strong>${formatDashboardNumber(h.change)}</strong></div>
                    <div class="detail-item"><span>Change %</span><strong>${escapeDashboardHTML(h.change_pct||"--")}</strong></div>
                    <div class="detail-item"><span>Last Report</span><strong>${escapeDashboardHTML(h.date||"--")}</strong></div>
                </div>
            </div>
        `).join(""):`<div class="empty-state"><h3>No institutional holdings found</h3><p>No institutional data was returned for ${escapeDashboardHTML(symbol)}.</p></div>`;
        return `<div class="results-header"><h2>Institutional Holdings</h2><p>Big money positioning in ${escapeDashboardHTML(symbol)}</p></div><div class="summary-grid">${summaryHTML}</div><div class="results-grid">${cards}</div>`;
    }

    function newsHTML(news,summary,symbol){
        const summaryItems=[
            ["Total Articles",summary.total_articles,""] ,["Bullish",summary.bullish,"bullish"],["Bearish",summary.bearish,"bearish"],
            ["Neutral",summary.neutral,"neutral"],["Avg Sentiment",summary.avg_score,""] ,["Top Topic",summary.top_topic,""]
        ];
        const summaryHTML=summaryItems.map(([label,value,css])=>`<div class="summary-card ${css}"><h3>${label}</h3><p>${escapeDashboardHTML(value??0)}</p></div>`).join("");
        const cards=news.length?news.map(n=>`
            <div class="news-card">
                ${n.image?`<img class="news-image" src="${escapeDashboardHTML(n.image)}" alt="">`:""}
                <div class="news-body">
                    <div class="news-top">
                            <h3>
                                ${n.url
                                    ? `<a href="${escapeDashboardHTML(n.url)}" target="_blank" rel="noopener noreferrer">${escapeDashboardHTML(n.title||"Untitled")}</a>`
                                    : escapeDashboardHTML(n.title||"Untitled")
                                }
                            </h3>
                        
                            <div class="news-sentiment-result">
                                <span class="${n.sentiment_label==="Bullish"?"buy":n.sentiment_label==="Bearish"?"sell":"neutral"}">
                                    ${escapeDashboardHTML(n.sentiment_label||"Neutral")}
                                </span>
                        
                                <span class="news-sentiment-score">
                                    ${Number(n.sentiment_score||0)>=0?"+":""}${Number(n.sentiment_score||0).toFixed(2)}
                                </span>
                            </div>
                        </div>
                    <p class="news-summary">${escapeDashboardHTML((n.summary||"").slice(0,240))}${(n.summary||"").length>240?"...":""}</p>
                    ${n.sentiment_reason?`<div class="news-sentiment-reason"><strong>AI reasoning:</strong> ${escapeDashboardHTML(n.sentiment_reason)}</div>`:""}
                    <div class="news-meta"><span>Source: ${escapeDashboardHTML(n.source||"Google News")}</span><span>${escapeDashboardHTML(n.time||"")}</span></div>
                    <div class="tag-row">${(n.topics||[]).map(topic=>`<span class="tag">${escapeDashboardHTML(topic)}</span>`).join("")}</div>
                    <div class="ticker-row">${(n.tickers||[]).map(t=>`<span class="ticker-chip">${escapeDashboardHTML(t.symbol)} (${escapeDashboardHTML(t.label)})</span>`).join("")}</div>
                </div>
            </div>
        `).join(""):`<div class="empty-state"><h3>No company news found</h3><p>Google News did not return recent articles for ${escapeDashboardHTML(symbol)}.</p></div>`;
        return `<div class="summary-grid">${summaryHTML}</div><div class="results-header"><h2>News & Sentiment</h2><p>Latest market intelligence for ${escapeDashboardHTML(symbol)}</p></div>${cards}`;
    }

    function earningsHTML(earnings,symbol,companyName){
        const items=earnings.items||[];
        if(!items.length){
            return `<div class="empty-state"><h3>No earnings transcripts found</h3><p>${escapeDashboardHTML(earnings.message||"Earnings data is not available.")}</p></div>`;
        }
        const cards=items.map(call=>`
            <div class="earnings-card">
                <div class="earnings-card-header"><div><p class="earnings-label">Earnings Call</p><h3>${escapeDashboardHTML(call.title)}</h3>${call.date?`<p class="earnings-date">${escapeDashboardHTML(call.date)}</p>`:""}</div><span class="earnings-period">Q${escapeDashboardHTML(call.quarter)} ${escapeDashboardHTML(call.year)}</span></div>
                <div class="earnings-preview">${escapeDashboardHTML(call.preview||"")}</div>
                <details class="earnings-details"><summary>Read full transcript</summary><div class="earnings-transcript">${escapeDashboardHTML(call.transcript||"")}</div></details>
            </div>
        `).join("");
        return `<div class="results-header"><h2>${escapeDashboardHTML(companyName)} (${escapeDashboardHTML(symbol)})</h2><p>Latest earnings call transcripts</p></div><div class="earnings-grid">${cards}</div>`;
    }

    function bindDynamicInsiderControls(){
        const chartFilter=document.getElementById("chartFilter");
        if(chartFilter)chartFilter.addEventListener("change",loadChart);
        const smartMoneyBtn=document.getElementById("smart-money-btn");
        if(smartMoneyBtn){
            smartMoneyBtn.addEventListener("click",async event=>{
                event.preventDefault();
                if(typeof window.loadSmartMoney==="function")await window.loadSmartMoney(window.currentSymbol);
                else notify("Smart Money panel is available after insider data finishes loading.","info");
            });
        }
    }

    async function loadInsiders(){
        const target=document.getElementById("insiderContent");
        dashboardState.insiders="loading";
        setTabStatus("insiderTabStatus","loading");
        target.innerHTML=loadingCard("Loading insider activity","Reading recent SEC Form 4 filings...","Step 1 of 4");
        try{
            const data=await fetchJSON(`/api/dashboard/${encodeURIComponent(window.currentSymbol)}/insiders`);
            target.innerHTML=insiderHTML(data.transactions||[],window.currentSymbol,window.currentCompanyName||window.currentSymbol);
            dashboardState.insiders="success";
            setTabStatus("insiderTabStatus","success");
            bindDynamicInsiderControls();
        }catch(error){
            dashboardState.insiders="error";
            setTabStatus("insiderTabStatus","error");
            target.innerHTML=errorCard("insiders",error.message);
        }
    }

    async function loadInstitutions(){
        const target=document.getElementById("institutionContent");
        dashboardState.institutions="loading";
        setTabStatus("institutionTabStatus","loading");
        target.innerHTML=loadingCard("Loading institutional holdings","Fetching holder positions and ownership changes...","Step 2 of 4");
        try{
            const data=await fetchJSON(`/api/dashboard/${encodeURIComponent(window.currentSymbol)}/institutions`);
            target.innerHTML=institutionHTML(data.institutional||[],data.summary||{},window.currentSymbol);
            dashboardState.institutions="success";
            setTabStatus("institutionTabStatus","success");
        }catch(error){
            dashboardState.institutions="error";
            setTabStatus("institutionTabStatus","error");
            target.innerHTML=errorCard("institutions",error.message);
        }
    }

    async function loadNews(){
        const target=document.getElementById("newsContent");
        dashboardState.news="loading";
        setTabStatus("newsTabStatus","loading");
        target.innerHTML=loadingCard("Collecting company news","Searching Google News for recent company coverage...","Step 3 of 4 · Fetching articles");
        try{
            setTimeout(()=>{
                if(dashboardState.news==="loading")target.innerHTML=loadingCard("Analyzing news sentiment","InsiderAI is evaluating company-specific impact for each article...","Step 3 of 4 · AI sentiment analysis");
            },1800);
            const url=`/api/dashboard/${encodeURIComponent(window.currentSymbol)}/news?company_name=${encodeURIComponent(window.currentCompanyName||window.currentSymbol)}`;
            const data=await fetchJSON(url);
            target.innerHTML=newsHTML(data.news||[],data.summary||{},window.currentSymbol);
            dashboardState.news="success";
            setTabStatus("newsTabStatus","success");
        }catch(error){
            dashboardState.news="error";
            setTabStatus("newsTabStatus","error");
            target.innerHTML=errorCard("news",error.message);
        }
    }

    async function loadEarnings(){
        const target=document.getElementById("earningsContent");
        dashboardState.earnings="loading";
        setTabStatus("earningsTabStatus","loading");
        target.innerHTML=loadingCard("Loading earnings transcripts","Fetching recent quarterly call transcripts...","Step 4 of 4");
        try{
            const data=await fetchJSON(`/api/dashboard/${encodeURIComponent(window.currentSymbol)}/earnings`);
            target.innerHTML=earningsHTML(data.earnings||{},window.currentSymbol,window.currentCompanyName||window.currentSymbol);
            dashboardState.earnings="success";
            setTabStatus("earningsTabStatus","success");
        }catch(error){
            dashboardState.earnings="error";
            setTabStatus("earningsTabStatus","error");
            target.innerHTML=errorCard("earnings",error.message);
        }
    }

    async function loadDashboardProgressively(){
        if(!window.currentSymbol)return;
        const aiButton=document.getElementById("analyzeCompanyWithAiBtn");
        if(aiButton)aiButton.disabled=true;
        await loadInsiders();
        await loadInstitutions();
        await loadNews();
        await loadEarnings();
        if(aiButton)aiButton.disabled=false;
        if(typeof notify==="function")notify("Dashboard analysis complete","success");
    }

    document.addEventListener("click",async event=>{
        const button=event.target.closest("[data-retry-section]");
        if(!button)return;
        const section=button.dataset.retrySection;
        const loaders={insiders:loadInsiders,institutions:loadInstitutions,news:loadNews,earnings:loadEarnings};
        if(loaders[section])await loaders[section]();
    });

    window.addEventListener("DOMContentLoaded",loadDashboardProgressively);
})();