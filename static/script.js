document.addEventListener("DOMContentLoaded", function () {
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

     const form = document.querySelector("form");
    const btn = document.getElementById("submitBtn");
    const icon = document.getElementById("btnIcon");
    const spinner = document.getElementById("spinner");

    form.addEventListener("submit", function () {
        // show spinner
        icon.classList.add("hidden");
        spinner.classList.remove("hidden");

        // disable button to prevent double clicks
        btn.disabled = true;
        btn.style.opacity = "0.7";
        btn.style.cursor = "not-allowed";
    });
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