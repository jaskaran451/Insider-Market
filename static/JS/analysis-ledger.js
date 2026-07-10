function appendPredictionLedger(message, stage = "running", extra = null) {
    const statusBox = getEl("predictionStatus");

    if (!statusBox) return;

    const row = document.createElement("div");
    row.className = `prediction-ledger-row ${stage}`;

    const time = new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
    });

    row.innerHTML = `
        <span class="ledger-dot"></span>
        <div class="ledger-content">
            <div class="ledger-message">${escapeHTML(message)}</div>
            <div class="ledger-time">${time}</div>
        </div>
    `;

    statusBox.appendChild(row);
    statusBox.scrollTop = statusBox.scrollHeight;
}
