document.addEventListener("DOMContentLoaded", async function () {
    let tickerDiv = document.getElementById("ticker");

    if (!tickerDiv) {
        console.warn("Ticker div not found");
        return;
    }

    async function showSkeleton() {
        try {
            const res = await fetch("/api/ticker-list");
            const tickers = await res.json();

            tickerDiv.innerHTML = tickers.map(symbol => `
                <div class="ticker-item">
                    <span>${symbol}</span>
                    <span class="ticker-loading">--</span>
                </div>
            `).join("");

        } catch (err) {
            console.error("Ticker list error", err);

            tickerDiv.innerHTML = `
                <div class="ticker-item">
                    <span>MARKET</span>
                    <span>--</span>
                </div>
            `;
        }
    }

    await showSkeleton();

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

        if (json.refreshing) {
            setTimeout(loadTicker, 4000);
        }

    } catch (err) {
        console.log("ticker error", err);
    }
}

    setInterval(loadTicker, 300000);
    loadTicker();
});