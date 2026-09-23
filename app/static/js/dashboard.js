const $ = (id) => document.getElementById(id);

let transactions = [];
let filteredTransactions = [];
let selectedTransaction = null;


/* =========================================================
   CHART
========================================================= */

const ctx = $("chart").getContext("2d");

const chart = new Chart(ctx, {
    type: "line",

    data: {
        labels: [],

        datasets: [
            {
                label: "Risk Score",

                data: [],

                borderWidth: 2,

                pointRadius: 0,

                tension: 0.25,

                fill: false
            }
        ]
    },

    options: {
        responsive: true,

        maintainAspectRatio: false,

        animation: false,

        plugins: {
            legend: {
                display: false
            }
        },

        scales: {

            x: {
                ticks: {
                    color: "#657286",
                    maxTicksLimit: 8
                },

                grid: {
                    color: "#1c2530"
                }
            },

            y: {
                min: 0,

                max: 100,

                ticks: {
                    color: "#657286"
                },

                grid: {
                    color: "#1c2530"
                }
            }

        }
    }
});


/* =========================================================
   HELPERS
========================================================= */

function money(value) {

    return "₹" +
        Number(value || 0).toLocaleString(
            "en-IN",
            {
                maximumFractionDigits: 0
            }
        );
}


function escapeHTML(value) {

    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


function badge(level) {

    return `
        <span class="risk ${escapeHTML(level)}">
            ${escapeHTML(level)}
        </span>
    `;
}


function formatTime(timestamp) {

    if (!timestamp) {
        return "--";
    }

    const date = new Date(timestamp);

    if (Number.isNaN(date.getTime())) {
        return "--";
    }

    return date.toLocaleTimeString();
}


function formatDateTime(timestamp) {

    if (!timestamp) {
        return "--";
    }

    const date = new Date(timestamp);

    if (Number.isNaN(date.getTime())) {
        return "--";
    }

    return date.toLocaleString();
}


/* =========================================================
   KPI METRICS
========================================================= */

function updateMetrics(stats) {

    $("total").textContent =
        Number(
            stats.total_transactions || 0
        ).toLocaleString("en-IN");


    $("volume").textContent =
        money(stats.total_volume);


    $("avg").textContent =
        Number(
            stats.average_risk_score || 0
        ).toFixed(1);


    $("alerts").textContent =
        `${Number(stats.high_risk_count || 0)} / ${Number(stats.critical_risk_count || 0)}`;
}


/* =========================================================
   TRANSACTION TABLE
========================================================= */

function renderRows(list) {

    const tbody = $("rows");

    tbody.innerHTML = "";


    list.forEach((t) => {

        const tr =
            document.createElement("tr");


        tr.dataset.transactionId =
            t.transaction_id;


        tr.innerHTML = `

            <td>
                ${escapeHTML(
            formatTime(t.timestamp)
        )}
            </td>


            <td>
                <strong>
                    ${escapeHTML(t.customer_id)}
                </strong>
            </td>


            <td>
                ${escapeHTML(t.merchant)}
            </td>


            <td>
                ${money(t.amount)}
            </td>


            <td>
                ${escapeHTML(t.device_id)}
            </td>


            <td>

                ${escapeHTML(t.city)},
                ${escapeHTML(t.country)}

                <br>

                <span class="muted">
                    IP: ${escapeHTML(t.ip_country)}
                </span>

            </td>


            <td>

                ${badge(t.risk_level)}

                <span class="risk-score">
                    ${Number(
            t.risk_score || 0
        ).toFixed(1)}
                </span>

            </td>


            <td
                class="${escapeHTML(t.decision)}"
            >
                ${escapeHTML(t.decision)}
            </td>


            <td>

                ${(t.reasons || [])
                .slice(0, 2)
                .map(
                    (reason) =>
                        escapeHTML(reason)
                )
                .join("; ")}

            </td>

        `;


        tr.addEventListener(
            "click",
            () => openTransactionModal(t)
        );


        tbody.appendChild(tr);

    });
}


/* =========================================================
   DECISION QUEUE
========================================================= */

function addAlert(t) {

    if (
        t.risk_level !== "HIGH" &&
        t.risk_level !== "CRITICAL"
    ) {
        return;
    }


    const container =
        $("alertsList");


    const d =
        document.createElement("div");


    d.className =
        `alert ${t.risk_level === "CRITICAL"
            ? "critical"
            : ""
        }`;


    d.innerHTML = `

        <b>

            ${escapeHTML(t.risk_level)}

            ·

            ${escapeHTML(t.decision)}

            ·

            ${Number(
        t.risk_score || 0
    ).toFixed(1)}

        </b>


        <small>

            ${escapeHTML(t.customer_id)}

            ·

            ${money(t.amount)}

            ·

            ${escapeHTML(t.merchant)}

        </small>


        <small>

            ${(t.reasons || [])
            .slice(0, 3)
            .map(
                (reason) =>
                    escapeHTML(reason)
            )
            .join(" · ")}

        </small>

    `;


    d.addEventListener(
        "click",
        () => openTransactionModal(t)
    );


    container.prepend(d);


    while (
        container.children.length > 20
    ) {

        container.lastChild.remove();

    }
}


/* =========================================================
   CHART UPDATE
========================================================= */

function updateChart(t) {

    chart.data.labels.push(
        formatTime(t.timestamp)
    );


    chart.data.datasets[0].data.push(
        Number(t.risk_score || 0)
    );


    if (
        chart.data.labels.length > 60
    ) {

        chart.data.labels.shift();

        chart.data.datasets[0].data.shift();

    }


    chart.update("none");
}


/* =========================================================
   HANDLE LIVE TRANSACTION
========================================================= */

function handleTransaction(t) {

    transactions.unshift(t);


    if (transactions.length > 500) {

        transactions.pop();

    }


    addAlert(t);

    updateChart(t);


    filteredTransactions =
        applyFilters(transactions);


    renderRows(
        filteredTransactions
    );


    $("feed").textContent =
        `streaming · ${formatTime(
            t.timestamp
        )}`;
}


/* =========================================================
   FILTERS
========================================================= */

function applyFilters(
    source = transactions
) {

    const search =
        (
            $("searchInput")?.value ||
            ""
        )
            .trim()
            .toLowerCase();


    const risk =
        $("riskFilter")?.value ||
        "ALL";


    const decision =
        $("decisionFilter")?.value ||
        "ALL";


    return source.filter((t) => {

        const searchable = [

            t.transaction_id,

            t.customer_id,

            t.merchant,

            t.city,

            t.country,

            t.ip_country,

            t.device_id,

            t.decision,

            ...(t.reasons || [])

        ]
            .join(" ")
            .toLowerCase();


        const matchesSearch =
            !search ||
            searchable.includes(search);


        const matchesRisk =
            risk === "ALL" ||
            t.risk_level === risk;


        const matchesDecision =
            decision === "ALL" ||
            t.decision === decision;


        return (
            matchesSearch &&
            matchesRisk &&
            matchesDecision
        );

    });
}


function refreshTable() {

    filteredTransactions =
        applyFilters(transactions);


    renderRows(
        filteredTransactions
    );
}


/* =========================================================
   TRANSACTION MODAL
========================================================= */

function openTransactionModal(t) {

    selectedTransaction = t;


    const modal =
        $("transactionModal");


    if (!modal) {
        return;
    }


    $("modalTransactionId").textContent =
        t.transaction_id || "--";


    $("modalTimestamp").textContent =
        formatDateTime(t.timestamp);


    $("modalCustomer").textContent =
        t.customer_id || "--";


    $("modalMerchant").textContent =
        t.merchant || "--";


    $("modalAmount").textContent =
        money(t.amount);


    $("modalDevice").textContent =
        t.device_id || "--";


    $("modalLocation").textContent =
        `${t.city || "--"}, ${t.country || "--"
        }`;


    $("modalIPCountry").textContent =
        t.ip_country || "--";


    $("modalRisk").innerHTML = `

        ${badge(t.risk_level)}

        <strong>

            ${Number(
        t.risk_score || 0
    ).toFixed(1)}

        </strong>

    `;


    $("modalDecision").textContent =
        t.decision || "--";


    $("modalDecision").className =
        `decision-value ${t.decision || ""
        }`;


    /* Model probability */

    const probability =
        Number(
            t.model_probability || 0
        );


    $("modalProbability").textContent =
        `${(
            probability * 100
        ).toFixed(1)}%`;


    /* Fraud reasons */

    const reasons =
        $("modalReasons");


    reasons.innerHTML = "";


    if (
        t.reasons &&
        t.reasons.length
    ) {

        t.reasons.forEach(
            (reason) => {

                const li =
                    document.createElement(
                        "li"
                    );


                li.textContent =
                    reason;


                reasons.appendChild(li);

            }
        );

    } else {

        reasons.innerHTML =
            "<li>No elevated-risk reason recorded.</li>";

    }


    /* Behavioral features */

    const features =
        t.features || {};


    const featureRows = [

        [
            "Amount Ratio",
            features.amount_ratio
        ],

        [
            "Amount Z-Score",
            features.amount_zscore
        ],

        [
            "Velocity (10m)",
            features.velocity_10m
        ],

        [
            "New Device",
            features.new_device
        ],

        [
            "New Merchant",
            features.new_merchant
        ],

        [
            "Geo Distance",
            features.geo_distance_km
        ],

        [
            "Geo Velocity",
            features.geo_velocity_kmh
        ],

        [
            "IP Mismatch",
            features.ip_mismatch
        ],

        [
            "Failed Attempts",
            features.failed_attempts
        ],

        [
            "Off Hours",
            features.off_hours
        ],

        [
            "Card Not Present",
            features.card_not_present
        ],

        [
            "Merchant Risk",
            features.merchant_risk
        ]

    ];


    const featureContainer =
        $("modalFeatures");


    featureContainer.innerHTML = "";


    featureRows.forEach(
        ([label, value]) => {

            const row =
                document.createElement(
                    "div"
                );


            row.className =
                "feature-row";


            let displayValue =
                value;


            if (
                typeof value ===
                "boolean"
            ) {

                displayValue =
                    value
                        ? "YES"
                        : "NO";

            }


            if (
                typeof value ===
                "number" &&
                !Number.isInteger(value)
            ) {

                displayValue =
                    value.toFixed(2);

            }


            row.innerHTML = `

                <span>
                    ${escapeHTML(label)}
                </span>

                <strong>
                    ${escapeHTML(
                displayValue
            )}
                </strong>

            `;


            featureContainer.appendChild(
                row
            );

        }
    );


    modal.classList.add("open");

    document.body.classList.add(
        "modal-open"
    );
}


function closeTransactionModal() {

    const modal =
        $("transactionModal");


    if (!modal) {
        return;
    }


    modal.classList.remove("open");


    document.body.classList.remove(
        "modal-open"
    );


    selectedTransaction = null;
}


/* =========================================================
   MODAL EVENTS
========================================================= */

function setupModalEvents() {

    const modal =
        $("transactionModal");


    if (!modal) {
        return;
    }


    const close =
        $("closeModal");


    if (close) {

        close.addEventListener(
            "click",
            closeTransactionModal
        );

    }


    modal.addEventListener(
        "click",
        (event) => {

            if (
                event.target === modal
            ) {

                closeTransactionModal();

            }

        }
    );


    document.addEventListener(
        "keydown",
        (event) => {

            if (
                event.key === "Escape"
            ) {

                closeTransactionModal();

            }

        }
    );
}


/* =========================================================
   FILTER EVENT SETUP
========================================================= */

function setupFilters() {

    const search =
        $("searchInput");


    const risk =
        $("riskFilter");


    const decision =
        $("decisionFilter");


    if (search) {

        search.addEventListener(
            "input",
            refreshTable
        );

    }


    if (risk) {

        risk.addEventListener(
            "change",
            refreshTable
        );

    }


    if (decision) {

        decision.addEventListener(
            "change",
            refreshTable
        );

    }


    const clear =
        $("clearFilters");


    if (clear) {

        clear.addEventListener(
            "click",
            () => {

                if (search) {
                    search.value = "";
                }


                if (risk) {
                    risk.value = "ALL";
                }


                if (decision) {
                    decision.value = "ALL";
                }


                refreshTable();

            }
        );

    }
}


/* =========================================================
   INITIAL LOAD
========================================================= */

async function bootstrap() {

    try {

        const [
            statsResponse,
            transactionsResponse
        ] = await Promise.all([

            fetch("/api/stats"),

            fetch(
                "/api/transactions?limit=80"
            )

        ]);


        if (!statsResponse.ok) {

            throw new Error(
                `Stats API failed: ${statsResponse.status
                }`
            );

        }


        if (
            !transactionsResponse.ok
        ) {

            throw new Error(
                `Transactions API failed: ${transactionsResponse.status
                }`
            );

        }


        const stats =
            await statsResponse.json();


        const transactionData =
            await transactionsResponse.json();


        updateMetrics(stats);


        transactions =
            (
                transactionData.transactions ||
                []
            ).sort(
                (a, b) =>
                    new Date(b.timestamp) -
                    new Date(a.timestamp)
            );


        filteredTransactions =
            applyFilters(
                transactions
            );


        renderRows(
            filteredTransactions
        );


        /* Historical chart */

        const history =
            [...transactions]
                .reverse()
                .slice(-60);


        history.forEach((t) => {

            chart.data.labels.push(
                formatTime(t.timestamp)
            );


            chart.data.datasets[0].data.push(
                Number(
                    t.risk_score || 0
                )
            );

        });


        chart.update("none");


        /* Existing decision queue */

        const elevated =
            transactions
                .filter(
                    (t) =>
                        t.risk_level === "HIGH" ||
                        t.risk_level === "CRITICAL"
                )
                .slice(0, 20)
                .reverse();


        elevated.forEach(addAlert);


        connect();

    } catch (error) {

        console.error(
            "Dashboard bootstrap failed:",
            error
        );


        $("status").textContent =
            "● API ERROR";


        $("status").style.color =
            "#ff4d67";

    }
}


/* =========================================================
   WEBSOCKET
========================================================= */

let retryDelay = 1000;


function connect() {

    const protocol =
        location.protocol === "https:"
            ? "wss"
            : "ws";


    const ws =
        new WebSocket(
            `${protocol}://${location.host}/ws/feed`
        );


    $("status").textContent =
        "● CONNECTING";


    $("status").style.color =
        "#f2bd4b";


    ws.onopen = () => {

        $("status").textContent =
            "● LIVE";


        $("status").style.color =
            "#35d39b";


        retryDelay = 1000;

    };


    ws.onmessage = (event) => {

        try {

            const message =
                JSON.parse(
                    event.data
                );


            if (
                message.type ===
                "transaction" &&
                message.data
            ) {

                handleTransaction(
                    message.data
                );

            }

        } catch (error) {

            console.error(
                "WebSocket message error:",
                error
            );

        }

    };


    ws.onerror = (error) => {

        console.error(
            "WebSocket error:",
            error
        );

    };


    ws.onclose = () => {

        $("status").textContent =
            "● RECONNECTING";


        $("status").style.color =
            "#f2bd4b";


        setTimeout(
            connect,
            retryDelay
        );


        retryDelay =
            Math.min(
                retryDelay * 1.5,
                15000
            );

    };
}


/* =========================================================
   START DASHBOARD
========================================================= */

setupFilters();

setupModalEvents();

bootstrap();