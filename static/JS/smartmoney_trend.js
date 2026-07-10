let trendAllocationChart=null;
let trendTopHoldingsChart=null;
let trendBubbleData=[];

document.addEventListener("DOMContentLoaded",function(){
    const form=document.getElementById("trendSearchForm");
    const input=document.getElementById("trendSearchInput");
    const reportFilter=document.getElementById("trendBubbleFilter");

    if(form && input){
        form.addEventListener("submit",async function(e){
            e.preventDefault();
            const query=input.value.trim();

            if(!query){
                notify("Enter a company or manager name","warning");
                return;
            }
            await loadSmartMoneyTrend(query);
        });
    }

    document.querySelectorAll(".smt-ribbon button").forEach(btn=>{
        btn.addEventListener("click",async function(){
            const query=this.dataset.query;
            input.value=this.textContent.trim();
            await loadSmartMoneyTrend(query);
        });
    });

    if(reportFilter){
        reportFilter.addEventListener("change",function(){
            renderTrendBubbleChart(this.value);
        });
    }
});

async function loadSmartMoneyTrend(query){
    const button = document.getElementById("trendSearchButton");
    const pipeline = createStatusPipeline("trendStatus", [
        "Validating search query...",
        "Fetching latest 13F filing data for " + query + "...",
        "Parsing institutional holdings and report periods...",
        "Calculating portfolio value, concentration, and position weights...",
        "Detecting new, increased, decreased, and closed positions...",
        "Building allocation, top holdings, and bubble trend charts...",
        "Finalizing Smart Money Trend analysis..."
    ], {
        interval: 1100
    });

    try{
        const response=await fetch(`/api/smart-money-trend?query=${encodeURIComponent(query)}`);
        const result=await response.json();

        if(!result.success){
            pipeline.error(result.message || "No 13F filings found for " + query + ".");
            return;
        }

        renderTrendDashboard(result);

        document.getElementById("trendResults").classList.remove("hidden");
        document.getElementById("trendResults").scrollIntoView({
            behavior:"smooth",
            block:"start"
        });
        smoothScrollToElement("trendResults", 300);
        pipeline.success(
            "Smart Money Trend analysis ready for " + (result.manager || query) + ". " +
            "Loaded " + ((result.top_holdings || []).length) + " top holdings and " +
            ((result.bubble_chart_data || []).length) + " position trend records."
        );

    }catch(error){
        console.error(error);

        pipeline.error(
            "Smart Money Trend analysis failed for " + query + ". Please check the symbol/name and try again."
        );
    } finally {
        setButtonLoading(button, false);
    }
}

function renderTrendDashboard(data){
    const overview=data.overview;
    const dna=data.manager_dna;
    if(data.large_fund){
    notify(
        "Large institutional portfolio detected. Showing top positions to keep dashboard fast.",
        "info",8000
    );
}

    document.getElementById("trendManager").textContent=data.manager || "--";
    document.getElementById("trendPeriod").textContent=`Latest 13F report: ${overview.latest_report_period || "--"}`;
    document.getElementById("trendStyle").textContent=dna.style || "--";
    document.getElementById("trendPortfolioValue").textContent=formatMoney(overview.portfolio_value);
    document.getElementById("trendTotalHoldings").textContent=overview.total_holdings ?? 0;
    document.getElementById("trendNewPositions").textContent=overview.new_positions ?? 0;
    document.getElementById("trendTop5").textContent=`${dna.top_5_concentration ?? 0}%`;

    renderAllocationChart(data.allocation || []);
    renderTopHoldingsChart(data.top_holdings || []);
    renderHoldingsTable(data.top_holdings || []);
    trendBubbleData=data.bubble_chart_data || [];
    const note=document.getElementById("bubbleChartNote");

    if(note){
        note.textContent=data.large_fund
            ? `Large fund mode: showing top ${data.bubble_limit_per_report} positions per report.`
            : "Bubble size represents number of shares. Y-axis shows portfolio weight.";
    }
    renderTrendBubbleChart("all");
}

function renderTrendBubbleChart(range="all"){
    const chart=document.getElementById("trendBubbleChart");

    if(!chart || !trendBubbleData || !trendBubbleData.length){
        return;
    }

    let reports=[...new Set(trendBubbleData.map(x=>x.report_period))].sort();

    if(range!=="all"){
        reports=reports.slice(-Number(range));
    }

    const rows=trendBubbleData.filter(x=>reports.includes(x.report_period));

    console.log("Selected range:",range);
    console.log("Reports shown:",reports);
    console.log("Rows shown:",rows.length);

    const statusColors={
        "NEW":"#22c55e",
        "INCREASED":"#3b82f6",
        "UNCHANGED":"#94a3b8",
        "DECREASED":"#f59e0b",
        "CLOSED":"#ef4444",
        "CURRENT":"#6366f1"
    };

    const statuses=[...new Set(rows.map(x=>x.status || "CURRENT"))];

    const traces=statuses.map(status=>{
        const group=rows.filter(x=>(x.status || "CURRENT")===status);

        return {
            type:"scatter",
            mode:"markers",
            name:status,
            x:group.map(x=>x.report_period),
            y:group.map(x=>x.portfolio_weight),
            text:group.map(x=>x.ticker || x.issuer),
            customdata:group.map(x=>[
                x.issuer,
                x.ticker || "--",
                formatNumber(x.shares),
                formatMoney(x.value),
                `${x.portfolio_weight}%`,
                x.filing_date || "--",
                formatNumber(x.share_change),
                formatMoney(x.value_change),
                x.status || "CURRENT"
            ]),
            marker:{
                size:group.map(x=>Number(x.shares || 0)),
                sizemode:"area",
                sizeref:getBubbleSizeRef(rows),
                sizemin:8,
                color:statusColors[status] || "#64748b",
                opacity:.72,
                line:{
                    color:"#fff",
                    width:1.5
                }
            },
            hovertemplate:
                "<b>%{customdata[0]} (%{customdata[1]})</b><br>"+
                "Status: %{customdata[8]}<br>"+
                "Report Period: %{x}<br>"+
                "Filed: %{customdata[5]}<br>"+
                "Portfolio Weight: %{customdata[4]}<br>"+
                "Shares: %{customdata[2]}<br>"+
                "Position Value: %{customdata[3]}<br>"+
                "Share Change: %{customdata[6]}<br>"+
                "Value Change: %{customdata[7]}<extra></extra>"
        };
    });

    const layout={
        height:520,
        margin:{
            l:70,
            r:30,
            t:20,
            b:70
        },
        paper_bgcolor:"#fff",
        plot_bgcolor:"#edf2f8",
        font:{
            family:"Inter, Arial, sans-serif",
            color:"#24324a"
        },
        xaxis:{
            title:"Report Period",
            type:"category",
            categoryorder:"array",
            categoryarray:reports,
            gridcolor:"rgba(255,255,255,.9)",
            tickfont:{
                size:13,
                color:"#334155"
            }
        },
        yaxis:{
            title:"Portfolio Weight %",
            gridcolor:"rgba(255,255,255,.9)",
            zeroline:false,
            tickfont:{
                size:13,
                color:"#334155"
            }
        },
        legend:{
            orientation:"h",
            y:1.12,
            x:0,
            font:{
                size:13,
                color:"#334155"
            }
        },
        hoverlabel:{
            bgcolor:"#fff",
            bordercolor:"#e2e8f0",
            font:{
                color:"#111827",
                size:13
            }
        }
    };

    const config={
        responsive:true,
        displaylogo:false,
        modeBarButtonsToRemove:[
            "lasso2d",
            "select2d"
        ]
    };

    if(!rows.length){
        Plotly.purge(chart);
        Plotly.newPlot(chart,[],{
            height:520,
            paper_bgcolor:"#fff",
            plot_bgcolor:"#edf2f8",
            annotations:[{
                text:"No positions match selected filters",
                xref:"paper",
                yref:"paper",
                x:.5,
                y:.5,
                showarrow:false,
                font:{
                    size:18,
                    color:"#64748b"
                }
            }]
        },config);
        return;
    }

    Plotly.purge(chart);
    Plotly.newPlot(chart,traces,layout,config);
}
function getBubbleSizeRef(rows){
    const maxShares=Math.max(
        ...rows.map(x=>Number(x.shares || 0)),
        1
    );

    const maxBubbleSize=58;

    return 2 * maxShares / (maxBubbleSize ** 2);
}

function renderAllocationChart(allocation){
    const ctx=document.getElementById("trendAllocationChart");

    if(trendAllocationChart){
        trendAllocationChart.destroy();
    }

    trendAllocationChart=new Chart(ctx,{
        type:"doughnut",
        data:{
            labels:allocation.map(x=>x.label || "Unknown"),
            datasets:[{
                data:allocation.map(x=>x.value || 0),
                backgroundColor:["#111827","#2563eb","#16a34a","#f59e0b","#ef4444","#7c3aed","#0891b2","#64748b","#cbd5e1"],
                borderWidth:0
            }]
        },
        options:{
            cutout:"68%",
            plugins:{
                legend:{
                    position:"bottom",
                    labels:{boxWidth:10,usePointStyle:true}
                },
                tooltip:{
                    callbacks:{
                        label:function(ctx){
                            const item=allocation[ctx.dataIndex];
                            return `${item.label}: ${formatMoney(item.value)} (${item.weight}%)`;
                        }
                    }
                }
            }
        }
    });
}

function renderTopHoldingsChart(holdings){
    const ctx=document.getElementById("trendTopHoldingsChart");
    const top=holdings.slice(0,8).reverse();

    if(trendTopHoldingsChart){
        trendTopHoldingsChart.destroy();
    }

    trendTopHoldingsChart=new Chart(ctx,{
        type:"bar",
        data:{
            labels:top.map(h=>h.ticker || h.issuer),
            datasets:[{
                label:"Portfolio Weight %",
                data:top.map(h=>h.portfolio_weight || 0),
                backgroundColor:"#111827",
                borderRadius:10,
                barThickness:24
            }]
        },
        options:{
            indexAxis:"y",
            responsive:true,
            maintainAspectRatio:false,
            plugins:{
                legend:{display:false},
                tooltip:{
                    callbacks:{
                        label:function(ctx){
                            const h=top[ctx.dataIndex];
                            return `${h.issuer}: ${h.portfolio_weight}%`;
                        }
                    }
                }
            },
            scales:{
                x:{
                    beginAtZero:true,
                    grid:{color:"rgba(15,23,42,.06)"},
                    ticks:{color:"#64748b"}
                },
                y:{
                    grid:{display:false},
                    ticks:{color:"#111827",font:{weight:"700"}}
                }
            }
        }
    });
}

function renderHoldingsTable(holdings){
    const container=document.getElementById("trendHoldingsTable");

    if(!holdings.length){
        container.innerHTML="<p>No holdings found.</p>";
        return;
    }

    container.innerHTML=`
        <table class="smt-table">
            <thead>
                <tr>
                    <th>Ticker</th>
                    <th>Issuer</th>
                    <th>Shares</th>
                    <th>Value</th>
                    <th>Weight</th>
                </tr>
            </thead>
            <tbody>
                ${holdings.map(h=>`
                    <tr>
                        <td>${h.ticker || "--"}</td>
                        <td>${h.issuer || "--"}</td>
                        <td>${formatNumber(h.shares)}</td>
                        <td>${formatMoney(h.value)}</td>
                        <td>${h.portfolio_weight ?? 0}%</td>
                    </tr>
                `).join("")}
            </tbody>
        </table>
    `;
}

function formatMoney(value){
    const num=Number(value || 0);
    if(num>=1_000_000_000) return `$${(num/1_000_000_000).toFixed(2)}B`;
    if(num>=1_000_000) return `$${(num/1_000_000).toFixed(2)}M`;
    if(num>=1_000) return `$${(num/1_000).toFixed(2)}K`;
    return `$${num.toFixed(0)}`;
}

function formatNumber(value){
    return Number(value || 0).toLocaleString();
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