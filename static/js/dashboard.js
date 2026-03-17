/**
 * Trading Signal Dashboard — Auto-Refresh & Interactive Features
 * Adapted for Flask backend
 */
(function () {
    'use strict';

    // ======================== CONFIG ========================
    const REFRESH_INTERVAL = 5 * 60 * 1000; // 5 minutes in ms
    let countdownTimer;
    let remainingSeconds = 300; // 5 minutes

    // ======================== INIT ========================
    document.addEventListener('DOMContentLoaded', () => {
        updateStats();
        startCountdown();
        scheduleAutoRefresh();
    });

    // ======================== AUTO-REFRESH ========================

    function scheduleAutoRefresh() {
        setInterval(() => {
            refreshSignals();
        }, REFRESH_INTERVAL);
    }

    function refreshSignals() {
        let endpoint = window.apiEndpoint;
        if (!endpoint) return;

        // Append tf parameter if it exists (for volume delta)
        if (window.currentTf && window.currentTf !== 'default') {
            const separator = endpoint.includes('?') ? '&' : '?';
            endpoint += `${separator}tf=${window.currentTf}`;
        }

        const indicator = document.getElementById('refresh-indicator');
        if (indicator) indicator.classList.add('refreshing');

        fetch(endpoint, {
            headers: {
                'Accept': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
            .then(response => {
                if (!response.ok) throw new Error('Network response was not ok');
                return response.json();
            })
            .then(data => {
                updateDashboard(data);
                updateLastUpdateTime(data.updatedAt);
                showToast('✅ Signals refreshed successfully', 'success');
                remainingSeconds = 300;
            })
            .catch(error => {
                console.error('Refresh failed:', error);
                showToast('⚠️ Refresh failed. Retrying...', 'info');
            })
            .finally(() => {
                if (indicator) indicator.classList.remove('refreshing');
            });
    }

    // ======================== COUNTDOWN TIMER ========================

    function startCountdown() {
        updateCountdownDisplay();
        countdownTimer = setInterval(() => {
            remainingSeconds--;
            if (remainingSeconds <= 0) {
                remainingSeconds = 300;
            }
            updateCountdownDisplay();
        }, 1000);
    }

    function updateCountdownDisplay() {
        const el = document.getElementById('refresh-countdown');
        if (!el) return;

        const min = Math.floor(remainingSeconds / 60);
        const sec = remainingSeconds % 60;
        el.textContent = `Next refresh: ${min}:${sec.toString().padStart(2, '0')}`;
    }

    // ======================== UPDATE DASHBOARD ========================

    function updateDashboard(data) {
        if (window.dashboardType === 'bbma') {
            updateBBMADashboard(data);
        } else if (window.dashboardType === 'smc') {
            updateSMCDashboard(data);
        } else if (window.dashboardType === 'summary') {
            updateSummaryDashboard(data);
        } else if (window.dashboardType === 'volume-delta') {
            updateVolumeDeltaDashboard(data);
        } else if (window.dashboardType === 'candle-ranking') {
            updateCandleRankingDashboard(data);
        }
        updateStats();
    }

    function updateBBMADashboard(data) {
        const comboBody = document.getElementById('combo-body');
        if (comboBody && data.signals) {
            let html = '';
            data.signals.forEach(item => {
                const combos = Object.entries(item.combos);
                combos.forEach(([groupName, combo], idx) => {
                    const hasSignal = combo.action !== 'WAIT' ? 'has-signal' : '';
                    html += `<tr class="signal-row ${hasSignal}" data-symbol="${item.symbol}" data-group="${groupName}">`;

                    if (idx === 0) {
                        html += `<td class="td-symbol" rowspan="${combos.length}">
                            <span class="symbol-name">${item.symbol}</span></td>`;
                    }

                    html += `<td class="td-group">
                        <span class="group-badge">${groupName}</span>
                        <small class="group-tf">${combo.timeframes.join(' → ')}</small></td>`;
                    html += `<td class="td-signal">${renderSignalBadge(combo.rem)}</td>`;
                    html += `<td class="td-signal">${renderSignalBadge(combo.ree)}</td>`;
                    html += `<td class="td-signal">${renderSignalBadge(combo.rme)}</td>`;
                    html += `<td class="td-signal">${renderSignalBadge(combo.zzl)}</td>`;
                    html += `<td class="td-signal td-diamond">${renderDiamondBadge(combo.diamond)}</td>`;

                    if (combo.setup) {
                        const setupClass = combo.signal === 1 ? 'setup-buy' : 'setup-sell';
                        const setupText = combo.setup + (combo.signal === 1 ? ' Buy' : ' Sell');
                        html += `<td class="td-setup"><span class="setup-badge ${setupClass}">${setupText}</span></td>`;
                    } else {
                        html += `<td class="td-setup"><span class="setup-none">---</span></td>`;
                    }

                    html += `<td class="td-action">
                        <span class="action-badge action-${combo.action.toLowerCase()}">${combo.action}</span></td>`;
                    html += '</tr>';
                });
            });
            comboBody.innerHTML = html;
        }

        const singlesBody = document.getElementById('singles-body');
        if (singlesBody && data.signals) {
            let html = '';
            const tfs = data.timeframes;
            const indicators = ['extreme', 'reentry', 'mhv', 'csm', 'csak'];

            data.signals.forEach(item => {
                html += `<tr class="signal-row" data-symbol="${item.symbol}">`;
                html += `<td class="td-symbol"><span class="symbol-name">${item.symbol}</span></td>`;

                indicators.forEach(ind => {
                    tfs.forEach(tf => {
                        const val = item.singleTF[tf][ind];
                        html += `<td class="td-signal td-mini">${renderSignalDot(val)}</td>`;
                    });
                });

                html += '</tr>';
            });
            singlesBody.innerHTML = html;
        }
    }

    function updateSMCDashboard(data) {
        const overviewBody = document.getElementById('smc-overview-body');
        if (overviewBody && data.signals) {
            let html = '';
            data.signals.forEach(item => {
                const hasSignal = item.entry.action !== 'WAIT' ? 'has-signal' : '';
                const biasClass = item.bias.direction === 'BULLISH' ? 'bias-bullish' :
                    item.bias.direction === 'BEARISH' ? 'bias-bearish' : 'bias-neutral';
                const structClass = 'structure-' + item.structure.toLowerCase().replace(/ /g, '-');

                html += `<tr class="signal-row ${hasSignal}" data-symbol="${item.symbol}">`;
                html += `<td class="td-symbol"><span class="symbol-name">${item.symbol}</span></td>`;
                html += `<td class="td-structure"><span class="structure-badge ${structClass}">${item.structure}</span></td>`;
                html += `<td class="td-bias"><span class="bias-badge ${biasClass}">${item.bias.direction}</span></td>`;
                html += `<td class="td-strength">
                    <div class="strength-bar-container">
                        <div class="strength-bar ${biasClass}" style="width: ${Math.min(item.bias.strength, 100)}%"></div>
                        <span class="strength-value">${item.bias.strength}%</span>
                    </div></td>`;
                html += `<td class="td-entry">
                    <div class="entry-scores">
                        <span class="score-buy" title="Buy Score">📈 ${item.entry.buyScore}</span>
                        <span class="score-sell" title="Sell Score">📉 ${item.entry.sellScore}</span>
                    </div></td>`;
                html += `<td class="td-action">
                    <span class="action-badge action-${item.entry.action.toLowerCase()}">${item.entry.action}</span></td>`;
                html += '</tr>';
            });
            overviewBody.innerHTML = html;
        }

        const detailBody = document.getElementById('smc-detail-body');
        if (detailBody && data.signals) {
            let html = '';
            const tfs = data.timeframes;
            const indicators = Object.keys(data.indicators);

            data.signals.forEach(item => {
                html += `<tr class="signal-row" data-symbol="${item.symbol}">`;
                html += `<td class="td-symbol"><span class="symbol-name">${item.symbol}</span></td>`;

                indicators.forEach(ind => {
                    tfs.forEach(tf => {
                        const val = item.signals[tf][ind];
                        if (ind === 'premium_discount') {
                            html += `<td class="td-signal td-mini">${renderPDBadge(val)}</td>`;
                        } else {
                            html += `<td class="td-signal td-mini">${renderSignalDot(val)}</td>`;
                        }
                    });
                });

                html += '</tr>';
            });
            detailBody.innerHTML = html;
        }
    }

    // ======================== RENDER HELPERS ========================

    function renderSignalBadge(signal) {
        if (signal === 1) return '<span class="signal-badge signal-buy">B</span>';
        if (signal === -1) return '<span class="signal-badge signal-sell">S</span>';
        return '<span class="signal-badge signal-none">—</span>';
    }

    function renderDiamondBadge(signal) {
        if (signal === 1) return '<span class="signal-badge signal-diamond">◆B</span>';
        if (signal === -1) return '<span class="signal-badge signal-diamond-sell">◆S</span>';
        return '<span class="signal-badge signal-none">—</span>';
    }

    function renderSignalDot(signal) {
        if (signal === 1) return '<span class="signal-dot dot-buy" title="Buy">●</span>';
        if (signal === -1) return '<span class="signal-dot dot-sell" title="Sell">●</span>';
        return '<span class="signal-dot dot-none" title="None">·</span>';
    }

    function renderPDBadge(signal) {
        if (signal === 2) return '<span class="pd-badge pd-premium" title="Premium Zone">P</span>';
        if (signal === -2) return '<span class="pd-badge pd-discount" title="Discount Zone">D</span>';
        return '<span class="signal-dot dot-none" title="Equilibrium">·</span>';
    }

    // ======================== STATS ========================

    function updateStats() {
        if (window.dashboardType === 'bbma') {
            updateBBMAStats();
        } else if (window.dashboardType === 'smc') {
            updateSMCStats();
        }
    }

    function updateSummaryDashboard(data) {
        const strongEl = document.getElementById('strongest-currency');
        const weakEl = document.getElementById('weakest-currency');
        const oppEl = document.getElementById('opportunities-count');
        if (strongEl && data.strongest) strongEl.textContent = data.strongest.currency;
        if (weakEl && data.weakest) weakEl.textContent = data.weakest.currency;
        if (oppEl && data.opportunities) oppEl.textContent = data.opportunities.length;

        const tbody = document.getElementById('strength-body');
        if (tbody && data.currencies) {
            let html = '';
            data.currencies.forEach((cur, idx) => {
                const dirClass = cur.trend === 'bullish' ? 'direction-bullish' :
                    cur.trend === 'bearish' ? 'direction-bearish' : 'direction-neutral';
                const barClass = cur.trend === 'bullish' ? 'strength-bar-bullish' :
                    cur.trend === 'bearish' ? 'strength-bar-bearish' : 'strength-bar-neutral';
                const netClass = cur.net > 0 ? 'net-positive' : (cur.net < 0 ? 'net-negative' : 'net-zero');
                const arrow = cur.trend === 'bullish' ? '▲' : (cur.trend === 'bearish' ? '▼' : '◆');
                const netPrefix = cur.net > 0 ? '+' : '';

                let pairsHtml = '';
                if (cur.topPairs && cur.topPairs.length) {
                    cur.topPairs.forEach(p => {
                        pairsHtml += `<span class="pair-chip pair-${p.impact}" title="${p.source}: ${p.symbol} ${p.direction}">`;
                        pairsHtml += `<span class="pair-source">${p.source}</span> ${p.symbol} <span class="pair-dir">${p.direction}</span></span>`;
                    });
                } else {
                    pairsHtml = '<span class="setup-none">—</span>';
                }

                html += `<tr class="signal-row ${cur.trend !== 'neutral' ? 'has-signal' : ''}" data-currency="${cur.currency}">`;
                html += `<td class="td-rank">${idx + 1}</td>`;
                html += `<td class="td-symbol"><span class="currency-name">${cur.currency}</span></td>`;
                html += `<td><span class="direction-badge ${dirClass}"><span class="dir-arrow">${arrow}</span> ${cur.direction}</span></td>`;
                html += `<td><div class="strength-meter"><div class="strength-meter-bar ${barClass}" style="width:${Math.min(cur.strength, 100)}%"></div><span class="strength-meter-value">${cur.strength}%</span></div></td>`;
                html += `<td class="td-score score-bullish-cell">${cur.bullish}</td>`;
                html += `<td class="td-score score-bearish-cell">${cur.bearish}</td>`;
                html += `<td class="td-score ${netClass}"><strong>${netPrefix}${cur.net}</strong></td>`;
                html += `<td class="td-pairs">${pairsHtml}</td>`;
                html += '</tr>';
            });
            tbody.innerHTML = html;
        }

        const oppGrid = document.querySelector('.opportunities-grid');
        if (oppGrid && data.opportunities) {
            let html = '';
            data.opportunities.forEach(opp => {
                const isLong = opp.action === 'BUY';
                html += `<div class="opportunity-card ${isLong ? 'opp-buy' : 'opp-sell'}">`;
                html += `<div class="opp-header"><span class="opp-pair">${opp.pair}</span>`;
                html += `<span class="action-badge ${isLong ? 'action-buy' : 'action-sell'}">${opp.action}</span></div>`;
                html += `<div class="opp-body"><div class="opp-vs">`;
                html += `<span class="opp-strong"><span class="opp-arrow">▲</span> ${opp.strong}</span>`;
                html += `<span class="opp-separator">vs</span>`;
                html += `<span class="opp-weak"><span class="opp-arrow">▼</span> ${opp.weak}</span></div>`;
                html += `<div class="opp-reason">${opp.reasoning}</div></div>`;
                html += `<div class="opp-footer"><div class="opp-score-bar">`;
                html += `<div class="opp-score-fill" style="width:${Math.min(opp.score * 5, 100)}%"></div></div>`;
                html += `<span class="opp-score-text">Score: ${opp.score}</span></div></div>`;
            });
            oppGrid.innerHTML = html;
        }
    }

    // ======================== VOLUME DELTA ========================

    function updateVolumeDeltaDashboard(data) {
        const flags = { 'USD': '🇺🇸', 'EUR': '🇪🇺', 'GBP': '🇬🇧', 'JPY': '🇯🇵', 'AUD': '🇦🇺', 'CAD': '🇨🇦', 'NZD': '🇳🇿', 'CHF': '🇨🇭', 'XAU': '🪙' };

        const mb = document.getElementById('most-buying');
        const ms = document.getElementById('most-selling');
        const pc = document.getElementById('pair-count');
        if (mb && data.mostBuying) mb.textContent = data.mostBuying.currency;
        if (ms && data.mostSelling) ms.textContent = data.mostSelling.currency;
        if (pc && data.pairs) pc.textContent = data.pairs.length;

        const tbody = document.getElementById('currency-delta-body');
        if (tbody && data.currencies) {
            let html = '';
            data.currencies.forEach((cur, idx) => {
                const pClass = getPressureClass(cur.pressure);
                const netClass = cur.netDelta > 0 ? 'net-positive' : (cur.netDelta < 0 ? 'net-negative' : 'net-zero');
                const avgClass = cur.avgDelta > 0 ? 'net-positive' : (cur.avgDelta < 0 ? 'net-negative' : 'net-zero');
                const arrow = cur.trend === 'bullish' ? '▲' : (cur.trend === 'bearish' ? '▼' : '◆');
                const flag = flags[cur.currency] || '🏳️';

                html += `<tr class="signal-row ${cur.trend !== 'neutral' ? 'has-signal' : ''}">`;
                html += `<td class="td-rank">${idx + 1}</td>`;
                html += `<td class="td-symbol"><span class="currency-flag">${flag}</span><span class="currency-name">${cur.currency}</span></td>`;
                html += `<td><span class="pressure-badge ${pClass}"><span class="dir-arrow">${arrow}</span> ${cur.pressure}</span></td>`;
                html += `<td><div class="volume-ratio-bar">`;
                html += `<div class="ratio-buy" style="width:${cur.buyPercent}%"><span class="ratio-label">${cur.buyPercent}%</span></div>`;
                html += `<div class="ratio-sell" style="width:${cur.sellPercent}%"><span class="ratio-label">${cur.sellPercent}%</span></div>`;
                html += `</div></td>`;
                html += `<td class="td-score score-bullish-cell">${cur.buyVolume.toLocaleString()}</td>`;
                html += `<td class="td-score score-bearish-cell">${cur.sellVolume.toLocaleString()}</td>`;
                html += `<td class="td-score ${netClass}"><strong>${cur.netDelta > 0 ? '+' : ''}${cur.netDelta.toLocaleString()}</strong></td>`;
                html += `<td class="td-score ${avgClass}"><strong>${cur.avgDelta > 0 ? '+' : ''}${cur.avgDelta}%</strong></td>`;

                html += `<td class="td-pairs">`;
                if (cur.topPairs && cur.topPairs.length) {
                    cur.topPairs.slice(0, 4).forEach(tp => {
                        const tpC = tp.delta > 0 ? 'pair-bullish' : (tp.delta < 0 ? 'pair-bearish' : 'pair-neutral');
                        html += `<span class="pair-chip ${tpC}">${tp.symbol} <span class="pair-dir">${tp.delta > 0 ? '+' : ''}${tp.delta}%</span></span>`;
                    });
                } else {
                    html += `<span class="setup-none">—</span>`;
                }
                html += `</td></tr>`;
            });
            tbody.innerHTML = html;
        }

        const pairBody = document.getElementById('pair-delta-body');
        if (pairBody && data.pairs) {
            const tfs = data.timeframes || ['D1', 'H4', 'H1', 'M30', 'M15', 'M5', 'M1'];
            let html = '';
            data.pairs.forEach(pd => {
                const hasSig = Math.abs(pd.overallDelta) > 10;
                const oClass = pd.overallDelta > 0 ? 'net-positive' : (pd.overallDelta < 0 ? 'net-negative' : 'net-zero');
                const pClass = getPressureClass(pd.pressure);

                html += `<tr class="signal-row ${hasSig ? 'has-signal' : ''}">`;
                html += `<td class="td-symbol"><span class="symbol-name">${pd.symbol}</span></td>`;

                tfs.forEach(tf => {
                    const dp = pd.timeframes[tf].deltaPercent;
                    const dpC = dp > 10 ? 'vd-strong-buy' : (dp > 0 ? 'vd-buy' : (dp < -10 ? 'vd-strong-sell' : (dp < 0 ? 'vd-sell' : 'vd-neutral')));
                    html += `<td class="td-mini ${dpC}">${dp > 0 ? '+' : ''}${dp}%</td>`;
                });

                tfs.forEach(tf => {
                    const cd = pd.timeframes[tf].cumDelta;
                    const cdC = cd > 0 ? 'vd-buy' : (cd < 0 ? 'vd-sell' : 'vd-neutral');
                    html += `<td class="td-mini ${cdC}">${cd > 0 ? '+' : ''}${cd.toLocaleString()}</td>`;
                });

                html += `<td class="td-score ${oClass}"><strong>${pd.overallDelta > 0 ? '+' : ''}${pd.overallDelta}%</strong></td>`;
                html += `<td><span class="pressure-badge-sm ${pClass}">${pd.pressure}</span></td>`;
                html += `</tr>`;
            });
            pairBody.innerHTML = html;
        }

        if (data.updatedAt) updateLastUpdateTime(data.updatedAt);
    }

    function getPressureClass(pressure) {
        if (pressure.includes('HEAVY BUYING')) return 'pressure-heavy-buy';
        if (pressure.includes('STRONG BUYING')) return 'pressure-strong-buy';
        if (pressure.includes('MODERATE BUYING')) return 'pressure-mod-buy';
        if (pressure.includes('SLIGHT BUYING')) return 'pressure-slight-buy';
        if (pressure.includes('HEAVY SELLING')) return 'pressure-heavy-sell';
        if (pressure.includes('STRONG SELLING')) return 'pressure-strong-sell';
        if (pressure.includes('MODERATE SELLING')) return 'pressure-mod-sell';
        if (pressure.includes('SLIGHT SELLING')) return 'pressure-slight-sell';
        return 'pressure-neutral';
    }

    // ======================== CANDLE RANKING ========================

    function updateCandleRankingDashboard(data) {
        const flags = { 'USD': '🇺🇸', 'EUR': '🇪🇺', 'GBP': '🇬🇧', 'JPY': '🇯🇵', 'AUD': '🇦🇺', 'CAD': '🇨🇦', 'NZD': '🇳🇿', 'CHF': '🇨🇭', 'XAU': '🪙' };

        if (!data.timeframes || !data.rankings) return;

        data.timeframes.forEach(tf => {
            const tbody = document.getElementById(`cr-body-${tf}`);
            if (tbody) {
                let html = '';
                const currencies = data.rankings[tf] || [];
                currencies.forEach((cur, idx) => {
                    const pClass = getPressureClass(cur.pressure);
                    const netClass = cur.netDelta > 0 ? 'net-positive' : (cur.netDelta < 0 ? 'net-negative' : 'net-zero');
                    const arrow = cur.trend === 'bullish' ? '▲' : (cur.trend === 'bearish' ? '▼' : '◆');
                    const flag = flags[cur.currency] || '🏳️';

                    html += `<tr class="signal-row ${cur.trend !== 'neutral' ? 'has-signal' : ''}">`;
                    html += `<td class="td-rank">${idx + 1}</td>`;
                    html += `<td class="td-symbol"><span class="currency-flag">${flag}</span><span class="currency-name">${cur.currency}</span></td>`;
                    html += `<td><span class="pressure-badge ${pClass}"><span class="dir-arrow">${arrow}</span> ${cur.pressure}</span></td>`;
                    html += `<td class="td-score score-bullish-cell">${cur.buyVolume.toLocaleString()}</td>`;
                    html += `<td class="td-score score-bearish-cell">${cur.sellVolume.toLocaleString()}</td>`;
                    html += `<td class="td-score ${netClass}"><strong>${cur.netDelta > 0 ? '+' : ''}${cur.netDelta.toLocaleString()}</strong></td>`;

                    const pctClass = cur.deltaPercent > 0 ? 'net-positive' : (cur.deltaPercent < 0 ? 'net-negative' : 'net-zero');
                    html += `<td class="td-score ${pctClass}"><strong>${cur.deltaPercent > 0 ? '+' : ''}${cur.deltaPercent}%</strong></td>`;
                    
                    html += `<td class="td-pairs">`;
                    if (cur.pairDetails && cur.pairDetails.length) {
                        cur.pairDetails.forEach(tp => {
                            const tpC = tp.delta > 0 ? 'pair-bullish' : (tp.delta < 0 ? 'pair-bearish' : 'pair-neutral');
                            html += `<span class="pair-chip ${tpC}">${tp.symbol} <span class="pair-dir">${tp.delta > 0 ? '+' : ''}${tp.delta}%</span></span>`;
                        });
                    } else {
                        html += `<span class="setup-none">—</span>`;
                    }
                    html += `</td></tr>`;
                });
                tbody.innerHTML = html;
            }

            const prevEl = document.getElementById(`cr-prev-${tf}`);
            if (prevEl && data.prev_rankings && data.prev_rankings[tf]) {
                // Now prev_rankings[tf] is an array of 5 strings
                for (let i = 0; i < 5; i++) {
                    const spanEl = document.getElementById(`cr-prev-val-${tf}-${i}`);
                    if (spanEl && data.prev_rankings[tf].length > i) {
                        spanEl.textContent = data.prev_rankings[tf][i];
                    } else if (spanEl) {
                        spanEl.textContent = '';
                    }
                }
            }
        });

        if (data.updatedAt) updateLastUpdateTime(data.updatedAt);
    }

    function updateBBMAStats() {
        const rows = document.querySelectorAll('#combo-body .signal-row');
        let buys = 0, sells = 0, setups = 0;

        rows.forEach(row => {
            const actionBadge = row.querySelector('.action-badge');
            if (actionBadge) {
                if (actionBadge.classList.contains('action-buy')) buys++;
                else if (actionBadge.classList.contains('action-sell')) sells++;
            }
            const setupBadge = row.querySelector('.setup-badge');
            if (setupBadge) setups++;
        });

        animateCounter('buy-count', buys);
        animateCounter('sell-count', sells);
        animateCounter('setup-count', setups);
    }

    function updateSMCStats() {
        const rows = document.querySelectorAll('#smc-overview-body .signal-row');
        let bullish = 0, bearish = 0, entries = 0;

        rows.forEach(row => {
            const biasBadge = row.querySelector('.bias-badge');
            if (biasBadge) {
                if (biasBadge.classList.contains('bias-bullish')) bullish++;
                else if (biasBadge.classList.contains('bias-bearish')) bearish++;
            }
            const actionBadge = row.querySelector('.action-badge');
            if (actionBadge && !actionBadge.classList.contains('action-wait')) entries++;
        });

        animateCounter('bullish-count', bullish);
        animateCounter('bearish-count', bearish);
        animateCounter('entry-count', entries);
    }

    function animateCounter(id, target) {
        const el = document.getElementById(id);
        if (!el) return;

        const current = parseInt(el.textContent) || 0;
        if (current === target) return;

        const duration = 500;
        const step = (target - current) / (duration / 16);
        let value = current;

        const animate = () => {
            value += step;
            if ((step > 0 && value >= target) || (step < 0 && value <= target)) {
                el.textContent = target;
                return;
            }
            el.textContent = Math.round(value);
            requestAnimationFrame(animate);
        };

        requestAnimationFrame(animate);
    }

    // ======================== TOAST ========================

    function showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        container.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    // ======================== LAST UPDATE TIME ========================

    function updateLastUpdateTime(timeStr) {
        const el = document.getElementById('last-update');
        if (el && timeStr) {
            el.textContent = 'Updated: ' + timeStr;
        }
    }

    // ======================== PAIR ANALYSIS ========================

    window.onPairSelect = function (symbol, source) {
        const panelId = source === 'summary' ? 'summary-analysis-panel' : 'vd-analysis-panel';
        const resultId = source === 'summary' ? 'summary-analysis-result' : 'vd-analysis-result';
        const loadingId = source === 'summary' ? 'summary-analysis-loading' : 'vd-analysis-loading';

        const panel = document.getElementById(panelId);
        const result = document.getElementById(resultId);
        const loading = document.getElementById(loadingId);

        if (!symbol) {
            if (panel) panel.style.display = 'none';
            return;
        }

        if (panel) panel.style.display = 'block';
        if (loading) loading.style.display = 'flex';
        if (result) result.innerHTML = '';

        fetch(`/api/pair-analysis/${symbol}?source=${source}`)
            .then(res => res.json())
            .then(data => {
                if (loading) loading.style.display = 'none';
                renderAnalysisPanel(data, resultId);
            })
            .catch(err => {
                console.error('Error fetching pair analysis:', err);
                if (loading) loading.style.display = 'none';
                if (result) result.innerHTML = `<div style="color:red;text-align:center;">Error loading analysis for ${symbol}</div>`;
            });
    };

    function renderAnalysisPanel(data, containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const isBuy = data.verdictKey.includes('buy');
        const isSell = data.verdictKey.includes('sell');
        const verdictClass = isBuy ? 'verdict-buying' : (isSell ? 'verdict-selling' : 'verdict-neutral');
        const mainScore = isBuy ? data.buyPercent : (isSell ? data.sellPercent : Math.max(data.buyPercent, data.sellPercent));
        const colorClass = isBuy ? 'score-buy' : (isSell ? 'score-sell' : '');

        let breakdownHtml = '';

        // Map backend keys to CSS classes
        const classMap = {
            'strong_buying': 'fill-strong-buy',
            'moderate_buying': 'fill-mod-buy',
            'slight_buying': 'fill-slight-buy',
            'neutral': 'fill-neutral',
            'slight_selling': 'fill-slight-sell',
            'moderate_selling': 'fill-mod-sell',
            'strong_selling': 'fill-strong-sell'
        };

        data.breakdown.forEach(item => {
            const fillClass = classMap[item.key] || 'fill-neutral';
            // Only dim 0% bars
            const opacity = item.score === 0 ? 'opacity: 0.2;' : '';

            breakdownHtml += `
            <div class="breakdown-row" style="${opacity}">
                <div class="breakdown-label">${item.label}</div>
                <div class="breakdown-bar-wrap">
                    <div class="breakdown-fill ${fillClass}" style="width: ${item.score}%"></div>
                </div>
                <div class="breakdown-pct">${item.score}%</div>
            </div>`;
        });

        container.innerHTML = `
            <div class="analysis-grid">
                <div class="verdict-box">
                    <div class="verdict-title">Overall Verdict</div>
                    <div class="verdict-badge ${verdictClass}">${data.verdict}</div>
                    <div class="verdict-score ${colorClass}">${mainScore}%</div>
                    <div style="font-size: 10px; color: var(--text-muted); margin-top: 8px;">Confidence Score</div>
                </div>
                <div class="breakdown-box">
                    ${breakdownHtml}
                </div>
            </div>
        `;
    }

    // ======================== CURRENCY DELTA TIMEFRAME ========================

    window.onCurrencyTfSelect = function (tf) {
        window.currentTf = tf;

        // Update URL query parameter without full reload if possible,
        // but for a clean state we can just redirect or reload with the new param
        const url = new URL(window.location.href);
        if (tf === 'default') {
            url.searchParams.delete('tf');
        } else {
            url.searchParams.set('tf', tf);
        }

        window.location.href = url.toString();
    };

})();
