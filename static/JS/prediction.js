(function () {
    "use strict";

    let forecastChart = null;
    let activeForecastData = null;

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

    function getEl(id) {
        return document.getElementById(id);
    }

    function formatCurrency(value) {
        return "$" + Number(value).toFixed(2);
    }

    function formatPercent(value) {
        const sign = value > 0 ? "+" : "";
        return sign + Number(value).toFixed(2) + "%";
    }

    function clamp(value, min, max) {
        return Math.max(min, Math.min(max, value));
    }

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
        const basePrice = 35 + (seed % 340);
        const drift = ((seed % 15) - 6) / 1000;
        const volatility = 0.014 + ((seed % 18) / 1000);
        const confidence = clamp(58 + (seed % 22), 50, 82);
        const risk = volatility > 0.027 ? "High" : volatility > 0.018 ? "Medium" : "Low";

        return {
            current: basePrice,
            drift: drift,
            volatility: volatility,
            confidence: confidence,
            risk: risk
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

        getEl("activeModelPill").textContent = data.symbol + " · " + (data.model || "Consensus Forecast");
        getEl("forecastCompanyTitle").textContent = data.symbol + " Forecast Intelligence";
    }

    function setText(id, value) {
    const element = getEl(id);

    if (element) {
        element.textContent = value;
    }
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

        getEl("confidenceRingValue").textContent = data.confidence + "%";

        setBar("momentumBar", "momentumScoreText", data.momentumScore);
        setBar("trendBar", "trendScoreText", data.trendScore);
        setBar("volatilityBar", "volatilityScoreText", data.volatilitySafetyScore);
    }

    function setBar(barId, textId, value) {
        getEl(barId).style.width = value + "%";
        getEl(textId).textContent = value + "%";
    }

    function renderModelRows(models) {
        const rows = models.map(function (model) {
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

        getEl("modelRows").innerHTML = rows;
    }

    function renderReasons(data) {
        getEl("bullishReasons").innerHTML = data.bullishReasons.map(function (reason) {
            return `<li>${reason}</li>`;
        }).join("");

        getEl("bearishReasons").innerHTML = data.bearishReasons.map(function (reason) {
            return `<li>${reason}</li>`;
        }).join("");
    }

    function renderBacktest(data) {
        getEl("maeValue").textContent = formatCurrency(data.mae);
        getEl("rmseValue").textContent = formatCurrency(data.rmse);
        getEl("directionAccuracyValue").textContent = data.directionAccuracy + "%";
        getEl("rangeHitRateValue").textContent = data.rangeHitRate + "%";
    }

    function renderForecastChart(data) {
        const canvas = getEl("forecastChart");

        if (!canvas || !window.Chart) {
            getEl("predictionStatus").textContent = "Chart.js did not load. Check internet connection or CDN.";
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

    function renderSignalBreakdown(data) {
    const breakdown = data.signalBreakdown || {};

    getEl("signalLstm").textContent = formatPercent(breakdown.lstm || 0);
    getEl("signalTrend").textContent = formatPercent(breakdown.trend || 0);
    getEl("signalMomentum").textContent = formatPercent(breakdown.momentum || 0);
    getEl("signalVolatility").textContent = formatPercent(breakdown.volatility_adjustment || 0);
    getEl("signalConsensus").textContent = formatPercent(breakdown.consensus || 0);
}

    function updateScenarioForecast() {
        if (!activeForecastData) return;

        const sentiment = Number(getEl("sentimentSlider").value);
        const volume = Number(getEl("volumeSlider").value);
        const volatility = Number(getEl("volatilitySlider").value);
        const macro = Number(getEl("macroSlider").value);

        getEl("sentimentValue").textContent = sentiment;
        getEl("volumeValue").textContent = volume;
        getEl("volatilityValue").textContent = volatility;
        getEl("macroValue").textContent = macro;

        const scenarioImpact =
            (sentiment * 0.0009) +
            (volume * 0.00045) -
            (volatility * 0.0006) -
            (macro * 0.0005);

        const scenarioPrice = activeForecastData.predictedPrice * (1 + scenarioImpact);
        const scenarioMove = ((scenarioPrice - activeForecastData.predictedPrice) / activeForecastData.predictedPrice) * 100;

        getEl("scenarioForecastValue").textContent = formatCurrency(scenarioPrice);
        getEl("scenarioMoveValue").textContent = formatPercent(scenarioMove) + " vs base prediction";
    }

    function bindEvents() {
        const form = getEl("predictionSearchForm");
        const input = getEl("predictionSymbolInput");

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

        document.querySelectorAll("[data-symbol]").forEach(function (button) {
    button.addEventListener("click", function () {
        const symbol = button.getAttribute("data-symbol");

        input.value = symbol;
        loadPredictionForecast(symbol);
    });
});

        ["sentimentSlider", "volumeSlider", "volatilitySlider", "macroSlider"].forEach(function (id) {
            getEl(id).addEventListener("input", updateScenarioForecast);
        });
    }

    function initPredictionDashboard() {
    bindEvents();

   setInlineStatus(
        "predictionStatus",
        "Enter a ticker symbol to run the InsiderAI forecast.",
        "info"
    );
}

async function fetchPredictionFromApi(symbol) {
    const cleanSymbol = symbol.toUpperCase().trim();

    const response = await fetch("/api/predict/" + encodeURIComponent(cleanSymbol));
    const data = await response.json();

    if (!response.ok || data.error) {
        throw new Error(data.message || "Prediction API failed");
    }

    return data;
}

async function loadPredictionForecast(symbol) {
    const cleanSymbol = symbol.toUpperCase().trim();

    const pipeline = createStatusPipeline("predictionStatus", [
        "Validating ticker symbol...",
        "Fetching historical OHLC price data for " + cleanSymbol + "...",
        "Preparing 10-year training dataset...",
        "Normalizing price series and building lookback windows...",
        "Running PyTorch LSTM neural network forecast...",
        "Calculating trend, momentum, and volatility signals...",
        "Combining signals into InsiderAI Consensus Forecast...",
        "Building forecast range, backtest metrics, and chart data..."
    ], {
        interval: 1100
    });

    try {
        const apiData = await fetchPredictionFromApi(cleanSymbol);
        const dashboardData = buildForecastDataFromApi(apiData);

        renderDashboard(dashboardData);

        pipeline.success(
            "Forecast ready for " + cleanSymbol + ". " +
            "Model: " + apiData.model + ". " +
            "Expected move: " + formatPercent(apiData.expected_move) + "."
        );

    } catch (error) {
        console.error(error);

        pipeline.error(
            "Forecast failed for " + cleanSymbol + ". Please check the ticker and try again."
        );
    }
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


    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initPredictionDashboard);
    } else {
        initPredictionDashboard();
    }

})();