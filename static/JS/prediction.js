(function () {
    "use strict";

    /* =========================================================
       1. GLOBAL STATE
       ========================================================= */

    let forecastChart = null;
    let activeForecastData = null;
    let latestForecastApiData = null;
    let forecastAiLottie = null;


    /* =========================================================
       2. PRESET FALLBACK STOCK DATA
       Used only for local/demo fallback forecast generation.
       Real dashboard data comes from /api/predict/<symbol>.
       ========================================================= */

    const presetStocks = {
        AAPL: {
            current: 195.32,
            drift: 0.018,
            volatility: 0.017,
            confidence: 76,
            risk: "Medium"
        },
        TSLA: {
            current: 184.71,
            drift: -0.012,
            volatility: 0.036,
            confidence: 61,
            risk: "High"
        },
        NVDA: {
            current: 129.84,
            drift: 0.024,
            volatility: 0.029,
            confidence: 72,
            risk: "Medium"
        },
        MSFT: {
            current: 426.18,
            drift: 0.011,
            volatility: 0.014,
            confidence: 79,
            risk: "Low"
        },
        BBAI: {
            current: 4.38,
            drift: 0.032,
            volatility: 0.058,
            confidence: 54,
            risk: "High"
        },
        IBM: {
            current: 186.42,
            drift: 0.008,
            volatility: 0.012,
            confidence: 74,
            risk: "Low"
        }
    };


    /* =========================================================
       3. BASIC UTILITY HELPERS
       ========================================================= */

    function getEl(id) {
        return document.getElementById(id);
    }

    function setText(id, value) {
        const element = getEl(id);

        if (element) {
            element.textContent = value;
        }
    }

    function formatCurrency(value) {
        return "$" + Number(value || 0).toFixed(2);
    }

    function formatPercent(value) {
        const numberValue = Number(value || 0);
        const sign = numberValue > 0 ? "+" : "";

        return sign + numberValue.toFixed(2) + "%";
    }

    function clamp(value, min, max) {
        return Math.max(min, Math.min(max, value));
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

    function smoothScrollToElement(elementId, delay = 250) {
        setTimeout(function () {
            const element = document.getElementById(elementId);

            if (!element) return;

            element.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });
        }, delay);
    }

    function resetPredictionLedger() {
    const statusBox = getEl("predictionStatus");

    if (!statusBox) return;

    statusBox.className = "prediction-ledger";
    statusBox.innerHTML = "";
}

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


    /* =========================================================
       4. FORECAST DATA HELPERS
       These create fallback/demo data and convert backend data
       into the dashboard format used by the UI.
       ========================================================= */

    function hashSymbol(symbol) {
        return symbol.split("").reduce(function (sum, char) {
            return sum + char.charCodeAt(0);
        }, 0);
    }

    function getStockProfile(symbol) {
        const cleanSymbol = symbol.toUpperCase().trim();

        if (presetStocks[cleanSymbol]) {
            return presetStocks[cleanSymbol];
        }

        const seed = hashSymbol(cleanSymbol);
        const volatility = 0.014 + ((seed % 18) / 1000);

        return {
            current: 35 + (seed % 340),
            drift: ((seed % 15) - 6) / 1000,
            volatility: volatility,
            confidence: clamp(58 + (seed % 22), 50, 82),
            risk: volatility > 0.027 ? "High" : volatility > 0.018 ? "Medium" : "Low"
        };
    }

    function getDirection(changePercent) {
        if (changePercent > 0.65) return "Bullish";
        if (changePercent < -0.65) return "Bearish";

        return "Neutral";
    }

    function getDirectionClass(direction) {
        if (direction === "Bullish") return "direction-bullish";
        if (direction === "Bearish") return "direction-bearish";

        return "direction-neutral";
    }

    function createDateLabels(length) {
        const labels = [];
        const today = new Date();

        for (let i = length - 1; i >= 0; i--) {
            const date = new Date(today);
            date.setDate(today.getDate() - i);

            labels.push(
                date.toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric"
                })
            );
        }

        labels.push("Next Day");

        return labels;
    }

    function buildForecastData(symbol) {
        const cleanSymbol = symbol.toUpperCase().trim() || "AAPL";
        const profile = getStockProfile(cleanSymbol);

        const historyLength = 48;
        const labels = createDateLabels(historyLength);
        const actual = [];
        const predicted = [];
        const upperBand = [];
        const lowerBand = [];

        const seed = hashSymbol(cleanSymbol);
        let price = profile.current * (0.88 + ((seed % 8) / 100));

        for (let i = 0; i < historyLength; i++) {
            const wave = Math.sin((i + seed) / 4) * profile.volatility * 1.8;
            const miniTrend = profile.drift / 8;
            const noise = Math.cos((i + seed) / 3) * profile.volatility * 0.55;

            price = price * (1 + miniTrend + wave * 0.18 + noise * 0.12);

            if (i === historyLength - 1) {
                price = profile.current;
            }

            actual.push(Number(price.toFixed(2)));

            if (i < historyLength - 18) {
                predicted.push(null);
                upperBand.push(null);
                lowerBand.push(null);
            } else {
                const predictionOffset = Math.sin((i + seed) / 5) * profile.volatility * price;
                const pastPrediction = price + predictionOffset;

                predicted.push(Number(pastPrediction.toFixed(2)));
                upperBand.push(Number((pastPrediction * (1 + profile.volatility * 1.9)).toFixed(2)));
                lowerBand.push(Number((pastPrediction * (1 - profile.volatility * 1.9)).toFixed(2)));
            }
        }

        const currentPrice = actual[actual.length - 1];
        const predictedPrice = currentPrice * (1 + profile.drift);
        const expectedMove = ((predictedPrice - currentPrice) / currentPrice) * 100;
        const direction = getDirection(expectedMove);

        actual.push(null);
        predicted.push(Number(predictedPrice.toFixed(2)));
        upperBand.push(Number((predictedPrice * (1 + profile.volatility * 2.2)).toFixed(2)));
        lowerBand.push(Number((predictedPrice * (1 - profile.volatility * 2.2)).toFixed(2)));

        const momentumScore = clamp(Math.round(62 + expectedMove * 6 + (seed % 9)), 35, 94);
        const trendScore = clamp(Math.round(profile.confidence + expectedMove * 2), 35, 95);
        const volatilitySafetyScore = clamp(Math.round(100 - profile.volatility * 1450), 28, 92);

        const mae = currentPrice * profile.volatility * 0.72;
        const rmse = mae * 1.34;
        const directionAccuracy = clamp(Math.round(profile.confidence - profile.volatility * 140 + 8), 48, 84);
        const rangeHitRate = clamp(Math.round(profile.confidence + 6 - profile.volatility * 90), 50, 88);

        return {
            symbol: cleanSymbol,
            labels: labels,
            actual: actual,
            predicted: predicted,
            upperBand: upperBand,
            lowerBand: lowerBand,
            currentPrice: currentPrice,
            predictedPrice: Number(predictedPrice.toFixed(2)),
            expectedMove: Number(expectedMove.toFixed(2)),
            direction: direction,
            confidence: profile.confidence,
            risk: profile.risk,
            momentumScore: momentumScore,
            trendScore: trendScore,
            volatilitySafetyScore: volatilitySafetyScore,
            mae: mae,
            rmse: rmse,
            directionAccuracy: directionAccuracy,
            rangeHitRate: rangeHitRate,
            models: buildModelComparison(currentPrice, predictedPrice, expectedMove, profile),
            bullishReasons: buildBullishReasons(direction, expectedMove, momentumScore, trendScore),
            bearishReasons: buildBearishReasons(profile.risk, profile.volatility, volatilitySafetyScore)
        };
    }

    function buildForecastDataFromApi(apiData) {
        const symbol = apiData.symbol.toUpperCase();

        const profile = {
            current: apiData.current_price,
            drift: apiData.expected_move / 100,
            volatility: apiData.volatility,
            confidence: apiData.confidence,
            risk: apiData.risk
        };

        const data = buildForecastData(symbol);

        data.symbol = symbol;
        data.labels = apiData.labels || data.labels;
        data.actual = apiData.actual || data.actual;
        data.predicted = apiData.predicted || data.predicted;
        data.upperBand = apiData.upper_band || data.upperBand;
        data.lowerBand = apiData.lower_band || data.lowerBand;

        data.currentPrice = apiData.current_price;
        data.predictedPrice = apiData.predicted_price;
        data.expectedMove = apiData.expected_move;
        data.direction = apiData.direction;
        data.confidence = apiData.confidence;
        data.risk = apiData.risk;
        data.signalBreakdown = apiData.signal_breakdown || null;
        data.model = apiData.model;
        data.mape = apiData.mape;
data.rSquared = apiData.r_squared;

        data.momentumScore = clamp(Math.round(55 + apiData.expected_move * 5), 30, 95);
        data.trendScore = clamp(Math.round(apiData.confidence + apiData.expected_move * 2), 35, 95);
        data.volatilitySafetyScore = clamp(Math.round(100 - apiData.volatility * 1450), 25, 95);

        data.mae = apiData.mae || apiData.current_price * apiData.volatility * 0.75;
        data.rmse = apiData.rmse || data.mae * 1.35;
        data.directionAccuracy = apiData.direction_accuracy || clamp(Math.round(apiData.confidence + 4), 45, 88);
        data.rangeHitRate = clamp(Math.round(apiData.confidence + 8), 50, 90);

        data.models = buildModelComparison(
            apiData.current_price,
            apiData.predicted_price,
            apiData.expected_move,
            profile
        );

        data.bullishReasons = buildBullishReasons(
            apiData.direction,
            apiData.expected_move,
            data.momentumScore,
            data.trendScore
        );

        data.bearishReasons = buildBearishReasons(
            apiData.risk,
            apiData.volatility,
            data.volatilitySafetyScore
        );

        return data;
    }

    function buildModelComparison(currentPrice, predictedPrice, expectedMove, profile) {
        const direction = getDirection(expectedMove);

        return [
            {
                name: "LSTM",
                prediction: predictedPrice,
                direction: direction,
                confidence: clamp(profile.confidence - 4, 45, 88),
                error: profile.volatility * currentPrice * 0.85
            },
            {
                name: "GRU",
                prediction: predictedPrice * 0.997,
                direction: getDirection(expectedMove - 0.28),
                confidence: clamp(profile.confidence - 7, 42, 86),
                error: profile.volatility * currentPrice * 0.96
            },
            {
                name: "CNN-LSTM",
                prediction: predictedPrice * 1.003,
                direction: getDirection(expectedMove + 0.22),
                confidence: clamp(profile.confidence - 2, 48, 90),
                error: profile.volatility * currentPrice * 0.79
            },
            {
                name: "Transformer",
                prediction: predictedPrice * 0.991,
                direction: getDirection(expectedMove - 0.42),
                confidence: clamp(profile.confidence - 10, 38, 84),
                error: profile.volatility * currentPrice * 1.12
            },
            {
                name: "Ensemble",
                prediction: predictedPrice * 1.001,
                direction: direction,
                confidence: clamp(profile.confidence + 3, 50, 92),
                error: profile.volatility * currentPrice * 0.68
            }
        ];
    }

    function buildBullishReasons(direction, expectedMove, momentumScore, trendScore) {
        const reasons = [];

        if (direction === "Bullish") {
            reasons.push("Neural forecast shows positive next-session drift.");
        } else {
            reasons.push("Model detects limited upside but no extreme breakdown signal.");
        }

        if (momentumScore >= 65) {
            reasons.push("Momentum score is stronger than the recent baseline.");
        } else {
            reasons.push("Momentum is mixed but still stable enough for monitoring.");
        }

        if (trendScore >= 70) {
            reasons.push("Trend alignment is supportive across the recent price window.");
        } else {
            reasons.push("Trend alignment is not strong, but price structure is still measurable.");
        }

        if (expectedMove > 0) {
            reasons.push("Predicted close is above the latest adjusted close.");
        }

        return reasons.slice(0, 4);
    }

    function buildBearishReasons(risk, volatility, volatilitySafetyScore) {
        const reasons = [];

        if (risk === "High") {
            reasons.push("Volatility risk is elevated, so the forecast range is wider.");
        } else if (risk === "Medium") {
            reasons.push("Moderate volatility may reduce prediction stability.");
        } else {
            reasons.push("Low volatility helps the model, but does not remove downside risk.");
        }

        if (volatilitySafetyScore < 55) {
            reasons.push("Volatility safety score is below the preferred threshold.");
        } else {
            reasons.push("Volatility safety is acceptable but should still be monitored.");
        }

        reasons.push("Single-feature close-price models can miss news, earnings, and macro shocks.");
        reasons.push("Real backend version should include validation error before trusting predictions.");

        return reasons;
    }

    function setSystemText(id, value, fallback = "--") {
    const element = getEl(id);

    if (!element) return;

    element.textContent =
        value !== undefined && value !== null && value !== ""
            ? value
            : fallback;
}

function setSystemHealth(status, label) {
    const badge = getEl("systemHealthBadge");

    if (!badge) return;

    badge.className = `system-health-badge ${status}`;
    badge.textContent = label;
}

function resetModelSystemPanel() {
    setSystemHealth("training", "Training");

    setSystemText("systemComputeDevice", "Detecting...");
    setSystemText("systemComputeName", "Selecting best available device");

    setSystemText("systemActiveModel", "AE-GRU");
    setSystemText("systemTrainingMode", "Live per ticker");
    setSystemText("systemLookback", "120 Days");
    setSystemText("systemEpochs", "10");

    setSystemText("systemTrainSamples", "--");
    setSystemText("systemValidationSamples", "--");
    setSystemText("systemValLoss", "--");
    setSystemText("systemRuntime", "--");
}

function updateModelSystemFromStatus(stage, extra) {
    if (!extra) return;

    if (stage === "system") {
        setSystemText("systemComputeDevice", extra.device_type || extra.device || "CPU");
        setSystemText("systemComputeName", extra.device_name || "CPU");
        setSystemHealth("training", "Training");
    }

    if (stage === "model_ready") {
        setSystemText("systemActiveModel", extra.architecture || "AE-GRU");

        if (extra.encoder && extra.decoder) {
            setSystemText(
                "systemLookback",
                "120 Days"
            );
        }

        setSystemText("systemEpochs", extra.epochs);
    }

    if (stage === "success") {
        if (extra.train_samples !== undefined) {
            setSystemText("systemTrainSamples", extra.train_samples);
        }

        if (extra.validation_samples !== undefined) {
            setSystemText("systemValidationSamples", extra.validation_samples);
        }
    }

    if (stage === "training") {
        if (extra.validation_loss !== undefined) {
            setSystemText("systemValLoss", extra.validation_loss);
        }

        if (extra.epoch && extra.total_epochs) {
            setSystemText("systemEpochs", `${extra.epoch}/${extra.total_epochs}`);
        }

        setSystemHealth("training", "Training");
    }

    if (stage === "validation_complete") {
        if (extra.rmse !== undefined) {
            setSystemText("systemValLoss", extra.rmse);
        }
    }

    if (stage === "prediction_complete") {
        setSystemHealth("completed", "Completed");
    }

    if (stage === "warning") {
        setSystemHealth("warning", "Fallback");
    }
}

function updateModelSystemFromResult(apiData, runtimeSeconds) {
    if (!apiData) return;

    setSystemHealth("completed", "Completed");

    if (apiData.compute_device) {
        setSystemText(
            "systemComputeDevice",
            apiData.compute_device.type || apiData.compute_device.device
        );

        setSystemText(
            "systemComputeName",
            apiData.compute_device.name || apiData.compute_device.device
        );
    }

    setSystemText("systemActiveModel", apiData.model || "AE-GRU Consensus");
    setSystemText("systemRuntime", runtimeSeconds ? `${runtimeSeconds}s` : "--");

    if (apiData.validation_losses && apiData.validation_losses.length > 0) {
        const lastLoss = apiData.validation_losses[apiData.validation_losses.length - 1];
        setSystemText("systemValLoss", lastLoss);
    }
}


    /* =========================================================
       5. BACKEND API FUNCTIONS
       ========================================================= */

    async function fetchPredictionFromApi(symbol, onStatus) {
    const cleanSymbol = symbol.toUpperCase().trim();

    const response = await fetch("/api/predict/" + encodeURIComponent(cleanSymbol) + "/stream");

    if (!response.ok || !response.body) {
        throw new Error("Prediction stream failed.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");

    let buffer = "";
    let finalData = null;

    while (true) {
        const result = await reader.read();

        if (result.done) {
            break;
        }

        buffer += decoder.decode(result.value, {
            stream: true
        });

        const lines = buffer.split("\n");
        buffer = lines.pop();

        for (const line of lines) {
            if (!line.trim()) continue;

            const event = JSON.parse(line);

            if (event.type === "status") {
                onStatus(event.message, event.stage, event.extra);
            }

            if (event.type === "result") {
                finalData = event.data;
            }

            if (event.type === "error") {
                throw new Error(event.message || "Prediction failed.");
            }
        }
    }

    if (!finalData) {
        throw new Error("Prediction stream ended without forecast data.");
    }

    return finalData;
}

    async function loadPredictionForecast(symbol) {
    const button = getEl("predictionSearchButton");
    const cleanSymbol = symbol.toUpperCase().trim();

    if (typeof setButtonLoading === "function") {
        setButtonLoading(button, true);
    } else if (button) {
        button.disabled = true;
    }

    resetPredictionLedger();
    resetModelSystemPanel();

const startedAt = performance.now();

    appendPredictionLedger("Validating ticker symbol...", "start");
    appendPredictionLedger("Opening live model progress stream...", "running");

    try {
        const apiData = await fetchPredictionFromApi(
            cleanSymbol,
            function (message, stage, extra) {
                appendPredictionLedger(message, stage, extra);
                updateModelSystemFromStatus(stage, extra);
            }
        );

        const dashboardData = buildForecastDataFromApi(apiData);

        latestForecastApiData = apiData;

        const runtimeSeconds = ((performance.now() - startedAt) / 1000).toFixed(1);
updateModelSystemFromResult(apiData, runtimeSeconds);
        renderDashboard(dashboardData);
        resetAIAnalysisSection();
        smoothScrollToElement("forecastMain", 300);

        appendPredictionLedger(
            "Forecast ready for " + cleanSymbol + ". Model: " + apiData.model + ". Expected move: " + formatPercent(apiData.expected_move) + ".",
            "success"
        );

    } catch (error) {
        console.error(error);
        setSystemHealth("error", "Error");

        appendPredictionLedger(
            "Forecast failed for " + cleanSymbol + ". " + (error.message || "Please try again."),
            "error"
        );

    } finally {
        if (typeof setButtonLoading === "function") {
            setButtonLoading(button, false);
        } else if (button) {
            button.disabled = false;
        }
    }
}


    /* =========================================================
       6. MAIN DASHBOARD RENDER FUNCTIONS
       ========================================================= */

    function renderDashboard(data) {
        const forecastMain = getEl("forecastMain");

        if (forecastMain) {
            forecastMain.classList.remove("hidden");
        }

        activeForecastData = data;

        renderMetricCards(data);
        renderConfidence(data);
        renderModelRows(data.models);
        renderReasons(data);
        renderBacktest(data);
        renderForecastChart(data);
        updateScenarioForecast();
        renderSignalBreakdown(data);

        setText("activeModelPill", data.symbol + " · " + (data.model || "Consensus Forecast"));
        setText("forecastCompanyTitle", data.symbol + " Forecast Intelligence");
    }

    function renderMetricCards(data) {
        setText("currentPriceValue", formatCurrency(data.currentPrice));
        setText("predictedPriceValue", formatCurrency(data.predictedPrice));
        setText("expectedMoveValue", formatPercent(data.expectedMove));
        setText("directionValue", data.direction);
        setText("confidenceValue", data.confidence + "%");
        setText("riskValue", data.risk);

        const expectedMoveEl = getEl("expectedMoveValue");
        if (expectedMoveEl) {
            expectedMoveEl.className = data.expectedMove >= 0 ? "direction-bullish" : "direction-bearish";
        }

        const directionEl = getEl("directionValue");
        if (directionEl) {
            directionEl.className = getDirectionClass(data.direction);
        }
    }

    function renderConfidence(data) {
        const angle = (data.confidence / 100) * 360;

        document.documentElement.style.setProperty("--confidence-angle", angle + "deg");

        setText("confidenceRingValue", data.confidence + "%");

        setBar("momentumBar", "momentumScoreText", data.momentumScore);
        setBar("trendBar", "trendScoreText", data.trendScore);
        setBar("volatilityBar", "volatilityScoreText", data.volatilitySafetyScore);
    }

    function setBar(barId, textId, value) {
        const bar = getEl(barId);
        const text = getEl(textId);

        if (bar) {
            bar.style.width = value + "%";
        }

        if (text) {
            text.textContent = value + "%";
        }
    }

    function renderModelRows(models) {
        const modelRows = getEl("modelRows");

        if (!modelRows || !Array.isArray(models)) return;

        modelRows.innerHTML = models.map(function (model) {
            const directionClass = getDirectionClass(model.direction);

            return `
                <tr>
                    <td>${model.name}</td>
                    <td>${formatCurrency(model.prediction)}</td>
                    <td class="${directionClass}">${model.direction}</td>
                    <td>${model.confidence}%</td>
                    <td>${formatCurrency(model.error)}</td>
                </tr>
            `;
        }).join("");
    }

    function renderReasons(data) {
        const bullishReasons = getEl("bullishReasons");
        const bearishReasons = getEl("bearishReasons");

        if (bullishReasons) {
            bullishReasons.innerHTML = data.bullishReasons.map(function (reason) {
                return `<li>${escapeHTML(reason)}</li>`;
            }).join("");
        }

        if (bearishReasons) {
            bearishReasons.innerHTML = data.bearishReasons.map(function (reason) {
                return `<li>${escapeHTML(reason)}</li>`;
            }).join("");
        }
    }

    function renderBacktest(data) {
        setText("maeValue", formatCurrency(data.mae));
        setText("rmseValue", formatCurrency(data.rmse));
        setText("directionAccuracyValue", data.directionAccuracy + "%");
        setText("rangeHitRateValue", data.rangeHitRate + "%");
        setText("mapeValue", (data.mape || 0) + "%");
setText("rSquaredValue", data.rSquared || "0.0000");
    }

    function renderSignalBreakdown(data) {
        const breakdown = data.signalBreakdown || {};

        setText("signalLstm", formatPercent(breakdown.ae_gru || breakdown.lstm || 0));
        setText("signalTrend", formatPercent(breakdown.trend || 0));
        setText("signalMomentum", formatPercent(breakdown.momentum || 0));
        setText("signalVolatility", formatPercent(breakdown.volatility_adjustment || 0));
        setText("signalConsensus", formatPercent(breakdown.consensus || 0));
    }

    function renderForecastChart(data) {
        const canvas = getEl("forecastChart");

        if (!canvas || !window.Chart) {
            setText("predictionStatus", "Chart.js did not load. Check internet connection or CDN.");
            return;
        }

        const ctx = canvas.getContext("2d");

        if (forecastChart) {
            forecastChart.destroy();
            forecastChart = null;
        }

        forecastChart = new Chart(ctx, {
            type: "line",
            data: {
                labels: data.labels,
                datasets: [
                    {
                        label: "Actual Price",
                        data: data.actual,
                        borderColor: "#111827",
                        backgroundColor: "rgba(17, 24, 39, 0.06)",
                        borderWidth: 3,
                        pointRadius: 0,
                        tension: 0.35
                    },
                    {
                        label: "Predicted Price",
                        data: data.predicted,
                        borderColor: "#16a34a",
                        backgroundColor: "rgba(22, 163, 74, 0.10)",
                        borderWidth: 3,
                        pointRadius: 5,
                        tension: 0.35
                    },
                    {
                        label: "Upper Range",
                        data: data.upperBand,
                        borderColor: "rgba(37, 99, 235, 0.75)",
                        borderWidth: 2,
                        pointRadius: 0,
                        borderDash: [6, 6],
                        tension: 0.35
                    },
                    {
                        label: "Lower Range",
                        data: data.lowerBand,
                        borderColor: "rgba(220, 38, 38, 0.75)",
                        borderWidth: 2,
                        pointRadius: 0,
                        borderDash: [6, 6],
                        tension: 0.35
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: "index"
                },
                plugins: {
                    legend: {
                        labels: {
                            color: "#334155",
                            usePointStyle: true,
                            boxWidth: 8,
                            boxHeight: 8
                        }
                    },
                    tooltip: {
                        backgroundColor: "rgba(255, 255, 255, 0.96)",
                        borderColor: "rgba(15, 23, 42, 0.12)",
                        borderWidth: 1,
                        titleColor: "#111827",
                        bodyColor: "#334155",
                        padding: 12
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            color: "#64748b",
                            maxTicksLimit: 8
                        },
                        grid: {
                            color: "rgba(15, 23, 42, 0.06)"
                        }
                    },
                    y: {
                        ticks: {
                            color: "#64748b",
                            callback: function (value) {
                                return "$" + value;
                            }
                        },
                        grid: {
                            color: "rgba(15, 23, 42, 0.08)"
                        }
                    }
                }
            }
        });
    }


    /* =========================================================
       7. SCENARIO SLIDER FUNCTIONS
       ========================================================= */

    function updateScenarioForecast() {
        if (!activeForecastData) return;

        const sentiment = Number(getEl("sentimentSlider")?.value || 0);
        const volume = Number(getEl("volumeSlider")?.value || 0);
        const volatility = Number(getEl("volatilitySlider")?.value || 0);
        const macro = Number(getEl("macroSlider")?.value || 0);

        setText("sentimentValue", sentiment);
        setText("volumeValue", volume);
        setText("volatilityValue", volatility);
        setText("macroValue", macro);

        const scenarioImpact =
            (sentiment * 0.0009) +
            (volume * 0.00045) -
            (volatility * 0.0006) -
            (macro * 0.0005);

        const scenarioPrice = activeForecastData.predictedPrice * (1 + scenarioImpact);
        const scenarioMove = ((scenarioPrice - activeForecastData.predictedPrice) / activeForecastData.predictedPrice) * 100;

        setText("scenarioForecastValue", formatCurrency(scenarioPrice));
        setText("scenarioMoveValue", formatPercent(scenarioMove) + " vs base prediction");
    }


    /* =========================================================
       8. AI / OLLAMA STREAMING FUNCTIONS
       ========================================================= */

    function resetAIAnalysisSection() {
        const card = getEl("forecastAiCard");
        const body = getEl("aiAnalysisBody");
        const button = getEl("analyzeWithAiBtn");

        if (forecastAiLottie) {
            forecastAiLottie.destroy();
            forecastAiLottie = null;
        }

        if (card) {
            card.classList.remove("ai-card-expanded");
            card.classList.add("ai-card-compact");
        }

        if (body) {
            body.innerHTML = `
                <p class="forecast-ai-placeholder">
                    Forecast loaded. Click Analyze with AI to generate the analyst summary.
                </p>
            `;
        }

        if (button) {
            button.disabled = false;
        }
    }

    function expandForecastAICard() {
        const card = getEl("forecastAiCard");

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

    function showForecastAILottieThinking() {
        const body = getEl("aiAnalysisBody");

        if (!body) return;

        body.innerHTML = `
            <div class="forecast-lottie-panel">
                <div class="forecast-lottie-bg" id="forecastAiLottie"></div>
                <div class="forecast-lottie-overlay"></div>

                <div class="forecast-lottie-content">
                    <p class="forecast-lottie-title">Analyzing forecast intelligence...</p>

                    <p class="forecast-lottie-subtitle">
                        Ollama is reading the LSTM forecast, signal breakdown, confidence,
                        risk level, model comparison, and forecast range.
                    </p>

                    <div class="forecast-lottie-steps">
                        <span>LSTM Forecast</span>
                        <span>Signal Breakdown</span>
                        <span>Risk Reading</span>
                        <span>Confidence Range</span>
                    </div>
                </div>
            </div>
        `;

        const container = getEl("forecastAiLottie");

        if (!container || !window.lottie) {
            return;
        }

        if (forecastAiLottie) {
            forecastAiLottie.destroy();
            forecastAiLottie = null;
        }

        try {
            forecastAiLottie = lottie.loadAnimation({
                container: container,
                renderer: "svg",
                loop: true,
                autoplay: true,
                path: "/static/animations/ai-thinking.json"
            });

            forecastAiLottie.addEventListener("data_failed", function () {
                console.error("Forecast Lottie failed to load. Check /static/animations/ai-thinking.json");
            });

        } catch (error) {
            console.error("Forecast Lottie init failed:", error);
        }
    }

    function showForecastAIStreamBox() {
        const body = getEl("aiAnalysisBody");

        if (!body) return null;

        if (forecastAiLottie) {
            forecastAiLottie.destroy();
            forecastAiLottie = null;
        }

        body.innerHTML = `
            <div class="forecast-ai-success streaming" id="forecastAiStreamText"></div>
        `;

        return getEl("forecastAiStreamText");
    }

    async function analyzeForecastWithAI() {
        const body = getEl("aiAnalysisBody");
        const button = getEl("analyzeWithAiBtn");

        if (!latestForecastApiData) {
            expandForecastAICard();

            if (body) {
                body.innerHTML = `
                    <div class="forecast-ai-unavailable">
                        Run a forecast first before using AI analysis.
                    </div>
                `;
            }

            return;
        }

        const symbol = latestForecastApiData.symbol;

        expandForecastAICard();
        showForecastAILottieThinking();

        if (typeof setButtonLoading === "function") {
            setButtonLoading(button, true);
        } else if (button) {
            button.disabled = true;
        }

        try {
            const response = await fetch(`/api/predict/${encodeURIComponent(symbol)}/ai-analysis-stream`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    forecast_data: latestForecastApiData
                })
            });

            if (!response.ok || !response.body) {
                throw new Error("AI forecast stream failed.");
            }

            const output = showForecastAIStreamBox();
            const aiBody = getEl("aiAnalysisBody");

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
            console.error("Forecast AI frontend error:", error);

            if (forecastAiLottie) {
                forecastAiLottie.destroy();
                forecastAiLottie = null;
            }

            if (body) {
                body.innerHTML = `
                    <div class="forecast-ai-unavailable">
                        Forecast AI failed: ${escapeHTML(error.message || "Unknown error")}
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
       9. EVENT BINDING
       ========================================================= */

    function bindEvents() {
        const form = getEl("predictionSearchForm");
        const input = getEl("predictionSymbolInput");

        if (form && input) {
            form.addEventListener("submit", function (event) {
                event.preventDefault();

                const symbol = input.value.trim().toUpperCase();

                if (!symbol) {
                    setInlineStatus(
                        "predictionStatus",
                        "Enter a ticker symbol to run the InsiderAI forecast.",
                        "warning"
                    );
                    return;
                }

                loadPredictionForecast(symbol);
            });
        }

        const analyzeWithAiBtn = getEl("analyzeWithAiBtn");

        if (analyzeWithAiBtn) {
            analyzeWithAiBtn.addEventListener("click", analyzeForecastWithAI);
        }

        document.querySelectorAll("[data-symbol]").forEach(function (button) {
            button.addEventListener("click", function () {
                const symbol = button.getAttribute("data-symbol");

                if (input) {
                    input.value = symbol;
                }

                loadPredictionForecast(symbol);
            });
        });

        ["sentimentSlider", "volumeSlider", "volatilitySlider", "macroSlider"].forEach(function (id) {
            const slider = getEl(id);

            if (slider) {
                slider.addEventListener("input", updateScenarioForecast);
            }
        });
    }


    /* =========================================================
       10. INIT
       ========================================================= */

    function initPredictionDashboard() {
        bindEvents();

        setInlineStatus(
            "predictionStatus",
            "Enter a ticker symbol to run the InsiderAI forecast.",
            "info"
        );
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initPredictionDashboard);
    } else {
        initPredictionDashboard();
    }

})();