document.addEventListener("DOMContentLoaded", function () {
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
let tickerDiv = document.getElementById("ticker");
const filter = document.getElementById("chartFilter");

    if (filter) {
        filter.addEventListener("change", loadChart);
    }

function showSkeleton() {
    tickerDiv.innerHTML = Array(10).fill(0).map(() => `
        <div class="ticker-item skeleton">
            <span>LOADING</span>
            <span>--</span>
        </div>
    `).join("");
}

showSkeleton();

async function loadTicker() {
    try {
        const res = await fetch("/api/stocks");
        const json = await res.json();
        const data = json.data;
        if (!data || data.length === 0) return;
        tickerDiv.innerHTML = "";
        data.forEach(item => {
            const symbol = item.symbol;
            const price = item.price;
            const change = item.change;
            const color = change >= 0 ? "green" : "red";
            const div = document.createElement("div");
            div.className = "ticker-item";

            div.innerHTML = `
                <span>${symbol}</span>
                <span style="color:${color}">
                    ${price}
                </span>
            `;

            tickerDiv.appendChild(div);
        });

    } catch (err) {
        console.log("ticker error", err);
    }
}

setTimeout(loadTicker, 500);
setInterval(loadTicker, 5000);
loadTicker();

    // // MODAL
    // function openChart(symbol) {
    //     document.getElementById("modal").classList.remove("hidden");
    //     document.getElementById("modal-title").innerText = symbol;
    //
    //     loadChart(symbol);
    // }
    //
    // function closeModal() {
    //     document.getElementById("modal").classList.add("hidden");
    // }
    //
    // // SIMPLE DEMO CHART
    // function loadChart(symbol) {
    //     const ctx = document.getElementById("chart").getContext("2d");
    //
    //     new Chart(ctx, {
    //         type: "line",
    //         data: {
    //             labels: ["1", "2", "3", "4", "5"],
    //             datasets: [{
    //                 label: symbol,
    //                 data: [10, 12, 9, 14, 13],
    //                 borderColor: "blue"
    //             }]
    //         }
    //     });
    // }


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

    const panel = document.getElementById("smart-money-panel");

    document.getElementById("smart-money-btn").addEventListener("click", async function (e)
    {
        e.preventDefault();

        const ticker = window.currentSymbol;

        if (!ticker) {
            notify("Search a stock first", "warning");
            return;
        }

        await loadSmartMoney(ticker);
});
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
    const data = window.smartMoneyData;

    document.getElementById("smSmartMoneyScore").textContent = data.smart_money_score ?? "--";
    const score=Number(data.smart_money_score || 0);
    document.getElementById("smSmartMoneyScore").textContent=score;
    document.getElementById("smScoreStatus").textContent=getSmartMoneyLabel(score);

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
            chip.className = `signal-chip ${signal.signal.toLowerCase()}`;
            chip.textContent = `${signal.signal} (${signal.score})`;
            signalList.appendChild(chip);
        });
    } else {
        signalList.innerHTML = `<div class="signal-chip neutral">No strong signal detected</div>`;
    }
}
    function getSmartMoneyLabel(score){
        if(score>=80) return "Strong Accumulation";
        if(score>=65) return "Bullish";
        if(score>=45) return "Neutral";
        if(score>=25) return "Bearish";
        return "Heavy Distribution";
    }




    function openSmartMoneyPanel(){
    const panel=document.getElementById("smart-money-panel");
    const resultsGrid=document.querySelector(".results-grid");

    if(resultsGrid){
        resultsGrid.classList.add("hidden");
    }

    panel.classList.remove("hidden");

    setTimeout(()=>{
        panel.scrollIntoView({
            behavior:"smooth",
            block:"start"
        });
    },100);
}

    function closeSmartMoney(){
    const panel=document.getElementById("smart-money-panel");
    const resultsGrid=document.querySelector(".results-grid");

    panel.classList.add("hidden");

    if(resultsGrid){
        resultsGrid.classList.remove("hidden");
    }
}
    function renderSmartMoneyCharts() {
        renderGauge();
        renderDonut();
        renderRadar();
        renderOwnership();
        renderTimeline();
    }
    function renderGauge() {

        const score = smartMoneyData.smart_money_score;

        new Chart(document.getElementById("smartMoneyGauge"), {
            type: "doughnut",
            data: {
                datasets: [{
                    data: [score, 100 - score],
                    backgroundColor: [
                        score > 65 ? "#22c55e" :
                        score > 40 ? "#facc15" : "#ef4444",
                        "#1f2937"
                    ],
                    borderWidth: 0
                }]
            },
            options: {
                cutout: "75%",
                plugins: {
                    tooltip: { enabled: false }
                }
            },
            plugins: [{
                id: "centerText",
                beforeDraw(chart) {
                    const { width } = chart;
                    const ctx = chart.ctx;

                    ctx.restore();
                    ctx.font = "bold 28px Arial";
                    ctx.fillStyle = "white";
                    ctx.textAlign = "center";

                    ctx.fillText(score, width / 2, 90);
                    ctx.font = "12px Arial";
                    ctx.fillText("Smart Money", width / 2, 110);
                    ctx.save();
                }
            }]
        });
    }

    function renderDonut() {
        const buys = smartMoneyData.total_buys;
        const sells = smartMoneyData.total_sells;
        const taxes = smartMoneyData.total_taxes;
        const grants = smartMoneyData.total_grants;

        new Chart(document.getElementById("activityDonut"), {
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
                    ]
                }]
            },
            options: {
                plugins: {
                    legend: { position: "bottom" }
                }
            }
        });
    }

    window.signalRadarChart=window.signalRadarChart || null;
    function renderRadar(){
    const canvas=document.getElementById("signalRadar");

    if(!canvas){
        return;
    }

    if(window.signalRadarChart){
        window.signalRadarChart.destroy();
        window.signalRadarChart=null;
    }

    const signals=window.smartMoneyData.signals || [];
    const labels=signals.map(s=>s.signal.replaceAll("_"," "));
    const values=signals.map(s=>s.score);

    window.signalRadarChart=new Chart(canvas,{
        type:"bar",
        data:{
            labels:labels,
            datasets:[{
                label:"Signal Strength",
                data:values,
                backgroundColor:signals.map(s=>{
                    const name=s.signal.toLowerCase();
                    if(name.includes("bearish") || name.includes("distribution")) return "#ef4444";
                    if(name.includes("bullish") || name.includes("accumulation")) return "#22c55e";
                    return "#60a5fa";
                }),
                borderRadius:10,
                barThickness:28
            }]
        },
        options:{
            indexAxis:"y",
            responsive:true,
            maintainAspectRatio:false,
            resizeDelay:100,
            plugins:{
                legend:{display:false},
                tooltip:{enabled:true}
            },
            scales:{
                x:{
                    beginAtZero:true,
                    max:100,
                    grid:{color:"rgba(15,23,42,.08)"},
                    ticks:{color:"#64748b"}
                },
                y:{
                    grid:{display:false},
                    ticks:{
                        color:"#111827",
                        font:{weight:"700"}
                    }
                }
            }
        }
    });
}


    function renderOwnership() {

        const container = document.getElementById("ownershipBars");
        container.innerHTML = "";

        const grouped = {};

        smartMoneyData.recent_transactions.forEach(t => {
            const name = t.insider || "Unknown";
            grouped[name] = (grouped[name] || 0) + (t.shares || 0);
        });

        const max = Math.max(...Object.values(grouped));

        Object.entries(grouped).forEach(([name, value]) => {

            const bar = document.createElement("div");
            bar.className = "ownership-row";

            bar.innerHTML = `
                <div class="label">${name}</div>
                <div class="bar">
                    <div class="fill" style="width:${(value/max)*100}%"></div>
                </div>
                <div class="value">${value.toLocaleString()}</div>
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

