/* DITO Dashboard — Chart.js helpers */

const DITO_COLORS = {
    primary: '#3333ff',
    secondary: '#ffe102',
    success: '#22c55e',
    text: '#94a3b8',
    grid: '#1e293b',
    accounts: ['#3333ff', '#ffe102', '#22c55e', '#c084fc', '#f97316'],
};

const CHART_DEFAULTS = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: {
            labels: { color: DITO_COLORS.text, font: { size: 11 } }
        }
    },
    scales: {
        x: {
            ticks: { color: DITO_COLORS.text, font: { size: 10 } },
            grid: { color: DITO_COLORS.grid }
        },
        y: {
            ticks: { color: DITO_COLORS.text, font: { size: 10 } },
            grid: { color: DITO_COLORS.grid }
        }
    }
};

/**
 * Render a dual-axis line chart: Spend + Conversions over time.
 */
function initSpendConversionsChart(canvasId, labels, spendData, conversionsData) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Spend (MXN)',
                    data: spendData,
                    borderColor: DITO_COLORS.primary,
                    backgroundColor: DITO_COLORS.primary + '20',
                    fill: true,
                    tension: 0.3,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    yAxisID: 'y',
                },
                {
                    label: 'Conversions',
                    data: conversionsData,
                    borderColor: DITO_COLORS.secondary,
                    borderDash: [5, 3],
                    fill: false,
                    tension: 0.3,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    yAxisID: 'y1',
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: {
                    labels: { color: DITO_COLORS.text, font: { size: 11 }, usePointStyle: true }
                },
                tooltip: {
                    backgroundColor: '#111827',
                    titleColor: '#fff',
                    bodyColor: '#e2e8f0',
                    borderColor: '#1e293b',
                    borderWidth: 1,
                }
            },
            scales: {
                x: {
                    ticks: { color: DITO_COLORS.text, font: { size: 10 }, maxRotation: 45 },
                    grid: { color: DITO_COLORS.grid }
                },
                y: {
                    type: 'linear',
                    position: 'left',
                    ticks: {
                        color: DITO_COLORS.text, font: { size: 10 },
                        callback: v => '$' + v.toLocaleString()
                    },
                    grid: { color: DITO_COLORS.grid }
                },
                y1: {
                    type: 'linear',
                    position: 'right',
                    ticks: { color: DITO_COLORS.text, font: { size: 10 } },
                    grid: { drawOnChartArea: false }
                }
            }
        }
    });
}

/**
 * Render a doughnut chart: Spend by Account.
 */
function initSpendByAccountChart(canvasId, labels, data) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: DITO_COLORS.accounts.slice(0, labels.length),
                borderColor: '#0a1628',
                borderWidth: 3,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '65%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: DITO_COLORS.text,
                        font: { size: 11 },
                        usePointStyle: true,
                        padding: 16,
                    }
                },
                tooltip: {
                    backgroundColor: '#111827',
                    titleColor: '#fff',
                    bodyColor: '#e2e8f0',
                    callbacks: {
                        label: ctx => `${ctx.label}: $${ctx.parsed.toLocaleString()} MXN`
                    }
                }
            }
        }
    });
}

/**
 * Render a multi-series hover-only line chart — used by the e-commerce panel.
 *
 * Design: all metrics share the X-axis (time). Each metric gets its own
 * HIDDEN Y-axis so the curves don't collapse into each other when their
 * magnitudes differ (e.g. spend in thousands vs conversions in units).
 * Values surface only in the tooltip on hover.
 *
 *   isoLabels: array of "YYYY-MM-DD" strings
 *   series:    array of { label, data, color, valueFormat?, unitLabel? }
 *              data may contain null for intentional gaps (e.g. CPA on 0-conv days)
 */
function initCombinedHoverChart(canvasId, isoLabels, series) {
    // Convert "YYYY-MM-DD" to "5 may" for the x-axis display (Spanish short).
    const monthsEs = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'];
    const displayLabels = isoLabels.map(s => {
        const [y, m, d] = s.split('-');
        return `${parseInt(d, 10)} ${monthsEs[parseInt(m, 10) - 1]}`;
    });

    const ctx = document.getElementById(canvasId).getContext('2d');

    const datasets = series.map((s, i) => ({
        label: s.label,
        data: s.data,
        borderColor: s.color,
        backgroundColor: s.color + '15',
        fill: false,
        tension: 0.35,
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 4,
        pointHoverBackgroundColor: s.color,
        pointHoverBorderColor: '#fff',
        pointHoverBorderWidth: 2,
        spanGaps: false,
        yAxisID: `y${i}`,
    }));

    // One hidden y-axis per series. Each line scales independently so they
    // remain readable side-by-side without showing any numeric labels.
    const scales = {
        x: {
            ticks: {
                color: DITO_COLORS.text,
                font: { size: 10 },
                maxRotation: 0,
                autoSkip: true,
                autoSkipPadding: 18,
            },
            grid: { display: false },
            border: { display: false },
        },
    };
    series.forEach((_, i) => {
        scales[`y${i}`] = { display: false, grid: { display: false } };
    });

    return new Chart(ctx, {
        type: 'line',
        data: { labels: displayLabels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: {
                    position: 'top',
                    align: 'end',
                    labels: {
                        color: DITO_COLORS.text,
                        font: { size: 11 },
                        usePointStyle: true,
                        pointStyle: 'rectRounded',
                        boxWidth: 10,
                        boxHeight: 10,
                        padding: 14,
                    },
                },
                tooltip: {
                    backgroundColor: '#111827',
                    titleColor: '#fff',
                    bodyColor: '#e2e8f0',
                    borderColor: '#1e293b',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: true,
                    boxPadding: 4,
                    callbacks: {
                        title: items => {
                            // Show full ISO date in the tooltip header.
                            const idx = items[0]?.dataIndex ?? 0;
                            return isoLabels[idx] || items[0]?.label;
                        },
                        label: ctx => {
                            const s = series[ctx.datasetIndex] || {};
                            const fmt = s.valueFormat || (n => Number(n).toLocaleString());
                            const unit = s.unitLabel ? ' ' + s.unitLabel : '';
                            const v = ctx.parsed.y;
                            if (v === null || v === undefined) {
                                return `${s.label}: sin datos`;
                            }
                            return `${s.label}: ${fmt(v)}${unit}`;
                        },
                    },
                },
            },
            scales,
        },
    });
}

/**
 * Render a horizontal bar chart: Top campaigns by spend.
 */
function initCampaignBarChart(canvasId, labels, data) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Spend (MXN)',
                data: data,
                backgroundColor: DITO_COLORS.primary + 'cc',
                borderColor: DITO_COLORS.primary,
                borderWidth: 1,
                borderRadius: 4,
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#111827',
                    bodyColor: '#e2e8f0',
                    callbacks: { label: ctx => `$${ctx.parsed.x.toLocaleString()} MXN` }
                }
            },
            scales: {
                x: {
                    ticks: {
                        color: DITO_COLORS.text, font: { size: 10 },
                        callback: v => '$' + v.toLocaleString()
                    },
                    grid: { color: DITO_COLORS.grid }
                },
                y: {
                    ticks: { color: DITO_COLORS.text, font: { size: 11 } },
                    grid: { display: false }
                }
            }
        }
    });
}
