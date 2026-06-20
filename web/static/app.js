/**
 * FH6 AutoBot — Web UI Client
 * ============================
 * WebSocket + i18n + 状态更新 + 日志渲染
 */

// ==========================================
// i18n 双语系统
// ==========================================
const GUIDE_EN = `
<h3>🖥️ Prerequisites</h3>
<ol>
    <li><strong>Python 3.10+</strong></li>
    <li><strong>Tesseract OCR</strong> — <a href="https://github.com/UB-Mannheim/tesseract/releases" target="_blank">Download</a> (install to default location, auto-detected)</li>
    <li><strong>ViGEmBus</strong> driver — <a href="https://github.com/ViGEm/ViGEmBus/releases" target="_blank">Download</a> (restart required)</li>
    <li>Game must run in <strong>Windowed</strong> or <strong>Borderless Windowed</strong> mode</li>
    <li>Recommended resolution: <strong>2560×1440</strong></li>
</ol>
<h3>🎮 In-Game Preparation</h3>
<ol>
    <li><strong>Set language to English</strong> (OCR depends on English text)</li>
    <li><strong>Buy main car</strong>: 1998 Subaru Impreza 22B-STI Version</li>
    <li><strong>Install S2 tune</strong>: Any S2-class tune (PI badge = blue)</li>
    <li><strong>Favorite a blueprint</strong>: Any EventLab blueprint works. Default: <code>890169683</code> (~10 pts/race)</li>
    <li><strong>Configure points</strong>: Set <strong>Points / Match</strong> and <strong>Target Points</strong> above to match your blueprint</li>
</ol>
<p class="warn">⚠️ The S2 blue PI badge is how the bot distinguishes "keep" vs "deletable" cars.</p>
<h3>🚀 How to Use</h3>
<ol>
    <li>Select a <strong>Start Stage</strong> from the dropdown above</li>
    <li>Optionally check <strong>Auto Loop</strong> for continuous cycling</li>
    <li>Click <strong>▶ Start Bot</strong> — the bot runs in background</li>
    <li>Monitor progress via the Live Logs and status cards</li>
    <li>Click <strong>⏹ Stop Bot</strong> to stop at any time</li>
</ol>
<h3>📊 Stage Descriptions</h3>
<table>
    <tr><th>Stage</th><th>Description</th></tr>
    <tr><td>🏎️ Farm</td><td>OCR scans skill points → auto-enters EventLab to farm to target</td></tr>
    <tr><td>🛒 Buy</td><td>Navigate to Car Collection → batch-purchase 33 Subaru Imprezas</td></tr>
    <tr><td>⚡ Upgrade</td><td>Enter garage → select each NEW Impreza → spend skill points</td></tr>
    <tr><td>🗑️ Sell</td><td>Enter garage → batch-remove upgraded Imprezas (keep S2 main car)</td></tr>
</table>`;

const GUIDE_ZH = `
<h3>🖥️ 前置要求</h3>
<ol>
    <li><strong>Python 3.10+</strong></li>
    <li><strong>Tesseract OCR</strong> — <a href="https://github.com/UB-Mannheim/tesseract/releases" target="_blank">下载安装</a>（默认路径安装即可，程序自动检测）</li>
    <li><strong>ViGEmBus</strong> 驱动 — <a href="https://github.com/ViGEm/ViGEmBus/releases" target="_blank">下载安装</a>（安装后需重启）</li>
    <li>游戏需运行在 <strong>窗口化</strong> 或 <strong>无边框窗口</strong> 模式</li>
    <li>建议分辨率：<strong>2560×1440</strong></li>
</ol>
<h3>🎮 游戏内准备</h3>
<ol>
    <li><strong>游戏语言设置为英文</strong>（OCR 识别依赖英文文本）</li>
    <li><strong>购买主力车</strong>：1998 Subaru Impreza 22B-STI Version</li>
    <li><strong>安装 S2 级改装</strong>：任意 S2 改装方案（PI 徽章显示蓝色）</li>
    <li><strong>收藏蓝图</strong>：支持任意 EventLab 蓝图。默认分享码 <code>890169683</code>（每局约 10 点）</li>
    <li><strong>配置点数</strong>：在上方设置 <strong>单局点数</strong> 和 <strong>目标点数</strong> 以匹配你的蓝图</li>
</ol>
<p class="warn">⚠️ 主力车的 S2 蓝色 PI 徽章是程序区分「保留车」与「可删除车」的关键依据。</p>
<h3>🚀 使用方法</h3>
<ol>
    <li>从上方下拉框选择 <strong>起始阶段</strong></li>
    <li>如需持续循环，勾选 <strong>自动循环</strong></li>
    <li>点击 <strong>▶ 启动</strong> — Bot 在后台运行</li>
    <li>通过实时日志和状态卡片监控进度</li>
    <li>点击 <strong>⏹ 停止</strong> 随时中止</li>
</ol>
<h3>📊 阶段说明</h3>
<table>
    <tr><th>阶段</th><th>描述</th></tr>
    <tr><td>🏎️ 刷点</td><td>OCR 扫描技能点 → 自动进入 EventLab 刷到目标点数</td></tr>
    <tr><td>🛒 买车</td><td>导航至 Car Collection → 批量购买 33 辆 Subaru Impreza</td></tr>
    <tr><td>⚡ 加点</td><td>进入车库 → 逐辆选择 NEW 标签 Impreza → 消耗技能点</td></tr>
    <tr><td>🗑️ 卖车</td><td>进入车库 → 批量移除已升级 Impreza（保留 S2 主力车）</td></tr>
</table>`;

// Web UI Enhancements State Variables
let logBuffer = [];
let currentFilter = "all";
let searchQuery = "";
let audioEnabled = false;
let notificationsEnabled = false;

const I18N = {
    en: {
        subtitle: "A Never-Ending AFK Farming Machine",
        connected: "⚡ Connected",
        disconnected: "⚡ Disconnected",
        currentStage: "Current Stage",
        loopCount: "Loop Count",
        uptime: "Uptime",
        superWheelspins: "Super Wheelspins (All-Time)",
        stageFarm: "Farm",
        stageBuy: "Buy",
        stageUpgrade: "Upgrade",
        stageSell: "Sell",
        startStage: "Start Stage",
        optFarm: "🏎️ Farm Skill Points",
        optBuy: "🛒 Buy Cars",
        optUpgrade: "⚡ Upgrade Cars",
        optSell: "🗑️ Sell Cars",
        autoLoop: "Auto Loop (4-stage cycle)",
        skipBuy: "Skip Buy Stage",
        pointsPerMatch: "\ud83d\udcca Points / Match",
        targetPoints: "\ud83c\udfaf Target Points",
        btnStart: "▶ Start Bot",
        btnStop: "⏹ Stop Bot",
        btnClear: "🗑 Clear Logs",
        liveLogs: "📜 Live Logs",
        waitingConnection: "Waiting for connection...",
        logsCleared: "Logs cleared",
        entries: "entries",
        logsCopied: "✅ Logs copied to clipboard",
        reconnecting: "⚡ Reconnecting (#{n})...",
        stateIdle: "Idle",
        stateFarm: "Farm Points",
        stateBuy: "Buy Cars",
        stateUpgrade: "Upgrade",
        stateSell: "Sell Cars",
        guideTitle: "📖 Usage Guide",
        guideContent: GUIDE_EN,
        qrTitle: "📱 Scan to access on mobile",
        histTotalRuns: "Total Runs (All-Time)",
        histTotalPoints: "Est. Points Earned",
        histSuccessRate: "Success Rate",
        histAvgTime: "Avg. Match Time",
        notifyToggle: "Desktop Notifications",
        audioToggle: "Audio Alerts",
        chartTitle: "Recent Match Durations",
        calibrateLabel: "📐 Skill Points ROI",
        btnCalibrate: "Calibrate",
        roiModalTitle: "📐 Calibrate Skill Points Region",
        roiModalInst: "Drag to draw a box tightly around the Skill Points number.",
        roiCapturing: "Capturing screenshot… please make sure the game is running and not minimized.",
        roiTimeout: "Capture timed out — please check the backend log or restart the service.",
        btnCancel: "Cancel",
        btnReset: "Reset to Default",
        btnSave: "Save ROI",
    },
    zh: {
        subtitle: "一个永不落幕的全自动挂机工具",
        connected: "⚡ 已连接",
        disconnected: "⚡ 未连接",
        currentStage: "当前阶段",
        loopCount: "循环次数",
        uptime: "运行时长",
        superWheelspins: "累计超级轮盘",
        stageFarm: "刷点",
        stageBuy: "买车",
        stageUpgrade: "加点",
        stageSell: "卖车",
        startStage: "选择阶段",
        optFarm: "🏎️ 刷技能点",
        optBuy: "🛒 买车",
        optUpgrade: "⚡ 加技能点",
        optSell: "🗑️ 卖车",
        autoLoop: "自动循环（四阶段闭环）",
        skipBuy: "跳过买车阶段",
        pointsPerMatch: "\ud83d\udcca 单局点数",
        targetPoints: "\ud83c\udfaf 目标点数",
        btnStart: "▶ 启动",
        btnStop: "⏹ 停止",
        btnClear: "🗑 清空日志",
        liveLogs: "📜 实时日志",
        waitingConnection: "等待连接...",
        logsCleared: "日志已清空",
        entries: "条",
        logsCopied: "✅ 日志已复制到剪贴板",
        reconnecting: "⚡ 正在重连 (#{n})...",
        stateIdle: "空闲",
        stateFarm: "刷技能点",
        stateBuy: "买车",
        stateUpgrade: "加技能点",
        stateSell: "卖车",
        guideTitle: "📖 使用说明",
        guideContent: GUIDE_ZH,
        qrTitle: "📱 扫码手机访问",
        histTotalRuns: "累计跑图 (历史)",
        histTotalPoints: "累计获得点数",
        histSuccessRate: "跑图成功率",
        histAvgTime: "平均单场耗时",
        notifyToggle: "系统桌面通知",
        audioToggle: "音效语音提示",
        chartTitle: "近期单局耗时趋势",
        calibrateLabel: "📐 技能点识别区",
        btnCalibrate: "开始校准",
        roiModalTitle: "📐 校准技能点识别区域",
        roiModalInst: "请在截图中用鼠标拖拽，将技能点数字（如 999）紧紧框住。",
        roiCapturing: "正在截图… 请确保游戏正在运行且未被最小化。",
        roiTimeout: "截图超时 — 请检查后端日志或重启服务。",
        btnCancel: "取消",
        btnReset: "恢复默认设定",
        btnSave: "保存选区",
    },
};

let currentLang = localStorage.getItem("fh6_lang") || "en";

function t(key) {
    return (I18N[currentLang] && I18N[currentLang][key]) || I18N.en[key] || key;
}

function applyI18n() {
    document.querySelectorAll("[data-i18n]").forEach((el) => {
        const key = el.getAttribute("data-i18n");
        el.textContent = t(key);
    });
    // Update HTML content blocks (guide)
    document.querySelectorAll("[data-i18n-html]").forEach((el) => {
        const key = el.getAttribute("data-i18n-html");
        el.innerHTML = t(key);
    });
    // Update connection badge
    const badge = document.getElementById("connection-status");
    if (socket.connected) {
        badge.textContent = t("connected");
    } else {
        badge.textContent = t("disconnected");
    }
    // Update log counter
    document.getElementById("log-count").textContent = `${logCount} ${t("entries")}`;
    // Re-render current state display
    const stateEl = document.getElementById("current-state");
    if (stateEl._rawState) {
        stateEl.textContent = formatState(stateEl._rawState);
    }
    // Highlight active language option
    document.querySelectorAll(".lang-option").forEach((el) => {
        el.classList.toggle("active", el.dataset.lang === currentLang);
    });
    // Sync custom dropdown display text
    if (typeof syncCustomSelect === "function") syncCustomSelect();
}

function setLang(lang) {
    currentLang = lang;
    localStorage.setItem("fh6_lang", currentLang);
    applyI18n();
    document.getElementById("lang-dropdown").classList.remove("open");
}

function toggleLangDropdown() {
    document.getElementById("lang-dropdown").classList.toggle("open");
}

// Close dropdowns on outside click
document.addEventListener("click", (e) => {
    const langWrap = document.querySelector(".lang-dropdown-wrap");
    if (langWrap && !langWrap.contains(e.target)) {
        document.getElementById("lang-dropdown").classList.remove("open");
    }
});

// ==========================================
// WebSocket 连接
// ==========================================
const socket = io({ transports: ["websocket", "polling"] });

let logCount = 0;
let autoScroll = true;
let botRunning = false;

// ==========================================
// 连接状态
// ==========================================
socket.on("connect", () => {
    const badge = document.getElementById("connection-status");
    badge.textContent = t("connected");
    badge.className = "badge badge-connected";
    badge.classList.remove("reconnecting");
});

socket.on("disconnect", () => {
    const badge = document.getElementById("connection-status");
    badge.textContent = t("disconnected");
    badge.className = "badge badge-disconnected";
});

socket.io.on("reconnect_attempt", (attempt) => {
    const badge = document.getElementById("connection-status");
    badge.textContent = t("reconnecting").replace("{n}", attempt);
    badge.className = "badge badge-disconnected reconnecting";
});

socket.io.on("reconnect", () => {
    const badge = document.getElementById("connection-status");
    badge.textContent = t("connected");
    badge.className = "badge badge-connected";
    badge.classList.remove("reconnecting");
});

// ==========================================
// 状态更新
// ==========================================
let previousState = null;

socket.on("state_update", (data) => {
    const stateEl = document.getElementById("current-state");
    stateEl._rawState = data.current_state;
    stateEl.textContent = formatState(data.current_state);
    document.getElementById("loop-count").textContent = data.loop_count || 0;

    if (data.uptime_seconds) {
        document.getElementById("uptime").innerHTML = formatUptime(data.uptime_seconds);
    }

    updateStageProgress(data.current_state);

    const currentState = data.current_state;
    if (currentState && currentState !== previousState) {
        onStateChanged(previousState, currentState);
        previousState = currentState;
    }
});

// Bot Config (单局点数/目标点数)
socket.on("bot_config", (data) => {
    if (data.points_per_match !== undefined) {
        document.getElementById("points-per-match").value = data.points_per_match;
    }
    if (data.target_points !== undefined) {
        document.getElementById("target-points").value = data.target_points;
    }
});

// Historical Stats
socket.on("historical_stats", (data) => {
    document.getElementById("hist-total-runs").textContent = data.total_matches || 0;
    document.getElementById("hist-total-points").textContent = data.est_points || 0;
    document.getElementById("super-wheelspins").textContent = data.total_wheelspins || 0;
    document.getElementById("hist-success-rate").textContent = (data.success_rate || 0) + "%";

    let avgTimeStr = "N/A";
    if (data.avg_time_seconds) {
        const m = Math.floor(data.avg_time_seconds / 60);
        const s = data.avg_time_seconds % 60;
        avgTimeStr = m > 0 ? `${m}m ${s}s` : `${s}s`;
    }
    document.getElementById("hist-avg-time").textContent = avgTimeStr;

    if (data.recent_races) {
        renderSVGChart(data.recent_races);
    }
});

socket.on("bot_status", (data) => {
    botRunning = data.running;
    updateButtons();
});

// ==========================================
// 日志流
// ==========================================
socket.on("log", (data) => {
    appendLog(data);
});

// ==========================================
// UI 交互
// ==========================================
function startBot() {
    const stageSelect = document.getElementById("stage-select");
    const skipBuy = document.getElementById("skip-buy").checked;
    const autoLoop = document.getElementById("auto-loop").checked;

    socket.emit("start_bot", {
        initial_state: stageSelect.value || null,
        skip_buy: skipBuy,
        loop: autoLoop,
    });

    botRunning = true;
    updateButtons();
}

function stopBot() {
    socket.emit("stop_bot");
    botRunning = false;
    updateButtons();
}

function clearLogs() {
    logBuffer = [];
    renderLogs();
}

function toggleAutoScroll() {
    autoScroll = !autoScroll;
    const btn = document.getElementById("btn-autoscroll");
    btn.classList.toggle("active", autoScroll);
    if (autoScroll) {
        const container = document.getElementById("log-container");
        container.scrollTop = container.scrollHeight;
    }
}

function copyLogs() {
    const text = logBuffer.map((data) => {
        const time = data.timestamp ? formatTime(data.timestamp) : "";
        const level = (data.level || "info").toUpperCase();
        return `${time} [${level}] ${data.msg || ""}`;
    }).join("\n");
    navigator.clipboard.writeText(text).then(() => {
        showToast(t("logsCopied"));
    });
}

function downloadLogs() {
    const text = logBuffer.map((data) => {
        const time = data.timestamp ? formatTime(data.timestamp) : "";
        const level = (data.level || "info").toUpperCase();
        return `${time} [${level}] ${data.msg || ""}`;
    }).join("\n");
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `fh6_autobot_${new Date().toISOString().slice(0, 19).replace(/:/g, "-")}.log`;
    a.click();
    URL.revokeObjectURL(url);
}

function showToast(msg) {
    let toast = document.getElementById("toast");
    if (!toast) {
        toast = document.createElement("div");
        toast.id = "toast";
        toast.style.cssText = `
            position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
            background: rgba(16,22,40,0.9); color: var(--neon-cyan);
            border: 1px solid rgba(0,229,200,0.3); border-radius: 8px;
            padding: 8px 20px; font-size: 0.82rem; backdrop-filter: blur(12px);
            box-shadow: 0 4px 20px rgba(0,0,0,0.4); z-index: 9999;
            opacity: 0; transition: opacity 0.3s;
        `;
        document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.style.opacity = "1";
    setTimeout(() => { toast.style.opacity = "0"; }, 2000);
}

function updateButtons() {
    document.getElementById("btn-start").disabled = botRunning;
    document.getElementById("btn-stop").disabled = !botRunning;
}

// ==========================================
// 日志渲染
// ==========================================
function appendLog(data) {
    logBuffer.push(data);
    if (logBuffer.length > 1000) {
        logBuffer.shift();
    }

    triggerNotificationForLog(data);
    renderLogs();
}

function renderLogs() {
    const container = document.getElementById("log-container");
    container.innerHTML = "";

    const filtered = logBuffer.filter((data) => {
        if (currentFilter !== "all" && (data.level || "info").toLowerCase() !== currentFilter) {
            return false;
        }
        if (searchQuery) {
            const query = searchQuery.toLowerCase();
            const msg = (data.msg || "").toLowerCase();
            const level = (data.level || "info").toLowerCase();
            const time = data.timestamp ? formatTime(data.timestamp).toLowerCase() : "";
            if (!msg.includes(query) && !level.includes(query) && !time.includes(query)) {
                return false;
            }
        }
        return true;
    });

    if (filtered.length === 0) {
        container.innerHTML = `<div class="log-empty">No matching entries</div>`;
        document.getElementById("log-count").textContent = `0 / ${logBuffer.length} ${t("entries")}`;
        return;
    }

    filtered.forEach((data) => {
        const entry = document.createElement("div");
        entry.className = `log-entry log-${data.level || "info"}`;
        const time = data.timestamp ? formatTime(data.timestamp) : "";
        const level = (data.level || "info").toUpperCase();
        const msg = escapeHtml(data.msg || "");
        entry.innerHTML = `<span class="log-time">${time}</span><span class="log-level">[${level}]</span><span class="log-msg">${msg}</span>`;
        container.appendChild(entry);
    });

    document.getElementById("log-count").textContent = `${filtered.length} / ${logBuffer.length} ${t("entries")}`;

    if (autoScroll) {
        container.scrollTop = container.scrollHeight;
    }
}

function filterLogs(level) {
    currentFilter = level;
    document.querySelectorAll(".filter-badge").forEach((el) => {
        el.classList.toggle("active", el.getAttribute("data-level") === level);
    });
    renderLogs();
}

function searchLogs() {
    searchQuery = document.getElementById("log-search").value;
    renderLogs();
}

// ==========================================
// 阶段进度（completed / active / pending）
// ==========================================
const STAGE_ORDER = [
    "STATE_FARM_POINTS",
    "STATE_BUY_CARS",
    "STATE_UPGRADE_CARS",
    "STATE_TRASH_CARS",
];

const CONNECTOR_IDS = [
    "conn-farm-buy",
    "conn-buy-upgrade",
    "conn-upgrade-sell",
];

function updateStageProgress(state) {
    const activeIdx = STAGE_ORDER.indexOf(state);
    const stages = document.querySelectorAll(".progress-stage");

    stages.forEach((el, i) => {
        el.classList.remove("active", "completed");

        if (activeIdx < 0) return; // IDLE — all grey

        if (i < activeIdx) {
            el.classList.add("completed");
        } else if (i === activeIdx) {
            el.classList.add("active");
        }
        // i > activeIdx: remains pending (default grey)
    });

    // Update connectors
    CONNECTOR_IDS.forEach((id, i) => {
        const conn = document.getElementById(id);
        if (!conn) return;
        conn.classList.remove("completed", "flowing");

        if (activeIdx < 0) return;

        if (i < activeIdx) {
            conn.classList.add("completed");
        } else if (i === activeIdx) {
            conn.classList.add("flowing");
        }
    });
}

// ==========================================
// 格式化工具
// ==========================================
function formatState(state) {
    const map = {
        IDLE: "stateIdle",
        STATE_FARM_POINTS: "stateFarm",
        STATE_BUY_CARS: "stateBuy",
        STATE_UPGRADE_CARS: "stateUpgrade",
        STATE_TRASH_CARS: "stateSell",
    };
    const key = map[state];
    return key ? t(key) : state || t("stateIdle");
}

function formatUptime(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    const cls = botRunning ? "colon blink" : "colon";
    return `${pad(h)}<span class="${cls}">:</span>${pad(m)}<span class="${cls}">:</span>${pad(s)}`;
}

function pad(n) {
    return n.toString().padStart(2, "0");
}

function formatTime(ts) {
    const d = new Date(ts * 1000);
    return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}



// ==========================================
// 自动滚动检测
// ==========================================
document.getElementById("log-container").addEventListener("scroll", function () {
    const el = this;
    const isAtBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 50;
    if (autoScroll !== isAtBottom) {
        autoScroll = isAtBottom;
        document.getElementById("btn-autoscroll").classList.toggle("active", autoScroll);
    }
});

// ==========================================
// 定时刷新 uptime
// ==========================================
setInterval(() => {
    if (botRunning) {
        socket.emit("get_state");
    }
}, 5000);

// ==========================================
// QR Code
// ==========================================
let lanUrl = "";

socket.on("lan_url", (data) => {
    lanUrl = data.url;
    generateQR(lanUrl);
});

function generateQR(url) {
    const canvas = document.getElementById("qr-canvas");
    canvas.innerHTML = "";
    if (!url || typeof qrcode === "undefined") return;

    const qr = qrcode(0, "M");
    qr.addData(url);
    qr.make();
    canvas.innerHTML = qr.createImgTag(5, 0);
    document.getElementById("qr-url").textContent = url;
}

function toggleQR() {
    const popover = document.getElementById("qr-popover");
    popover.classList.toggle("pinned");
}

// ==========================================
// Custom Dropdown (自定义下拉菜单)
// ==========================================
const customSelect = document.getElementById("custom-select");
const selectTrigger = document.getElementById("select-trigger");
const selectDropdown = document.getElementById("select-dropdown");
const selectDisplay = document.getElementById("select-display");
const nativeSelect = document.getElementById("stage-select");

// Toggle open/close
selectTrigger.addEventListener("click", (e) => {
    e.stopPropagation();
    customSelect.classList.toggle("open");
});

// Close on click outside
document.addEventListener("click", () => {
    customSelect.classList.remove("open");
});

// Prevent dropdown clicks from closing
selectDropdown.addEventListener("click", (e) => {
    e.stopPropagation();
});

// Option selection
selectDropdown.querySelectorAll(".custom-select-option").forEach((opt) => {
    opt.addEventListener("click", () => {
        // Update visual state
        selectDropdown.querySelectorAll(".custom-select-option").forEach((o) => o.classList.remove("selected"));
        opt.classList.add("selected");

        // Update display text
        selectDisplay.textContent = opt.textContent;

        // Sync hidden native select
        nativeSelect.value = opt.dataset.value;
        nativeSelect.dispatchEvent(new Event("change"));

        // Close
        customSelect.classList.remove("open");
    });
});

// Sync custom dropdown display from native select value
function syncCustomSelect() {
    const val = nativeSelect.value;
    const match = selectDropdown.querySelector(`[data-value="${val}"]`);
    if (match) {
        selectDropdown.querySelectorAll(".custom-select-option").forEach((o) => o.classList.remove("selected"));
        match.classList.add("selected");
        selectDisplay.textContent = match.textContent;
    }
}

// ==========================================
// 本地状态持久化 (localStorage)
// ==========================================
const PREFS_KEY = "fh6_prefs";

function savePrefs() {
    const prefs = {
        stage: document.getElementById("stage-select").value,
        autoLoop: document.getElementById("auto-loop").checked,
        skipBuy: document.getElementById("skip-buy").checked,
        pointsPerMatch: parseInt(document.getElementById("points-per-match").value) || 10,
        targetPoints: parseInt(document.getElementById("target-points").value) || 999,
        enableNotifications: document.getElementById("enable-notifications").checked,
        enableAudio: document.getElementById("enable-audio").checked,
    };
    localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
}

function restorePrefs() {
    try {
        const raw = localStorage.getItem(PREFS_KEY);
        if (!raw) return;
        const prefs = JSON.parse(raw);
        if (prefs.stage) {
            document.getElementById("stage-select").value = prefs.stage;
            syncCustomSelect();
        }
        if (prefs.autoLoop !== undefined) {
            document.getElementById("auto-loop").checked = prefs.autoLoop;
        }
        if (prefs.skipBuy !== undefined) {
            document.getElementById("skip-buy").checked = prefs.skipBuy;
        }
        if (prefs.pointsPerMatch !== undefined) {
            document.getElementById("points-per-match").value = prefs.pointsPerMatch;
        }
        if (prefs.targetPoints !== undefined) {
            document.getElementById("target-points").value = prefs.targetPoints;
        }
        if (prefs.enableNotifications !== undefined) {
            document.getElementById("enable-notifications").checked = prefs.enableNotifications;
            notificationsEnabled = prefs.enableNotifications;
        }
        if (prefs.enableAudio !== undefined) {
            document.getElementById("enable-audio").checked = prefs.enableAudio;
            audioEnabled = prefs.enableAudio;
        }
    } catch (_) {
        // ignore corrupt data
    }
}

// Listen for changes
document.getElementById("stage-select").addEventListener("change", savePrefs);
document.getElementById("auto-loop").addEventListener("change", savePrefs);
document.getElementById("skip-buy").addEventListener("change", savePrefs);
document.getElementById("enable-notifications").addEventListener("change", savePrefs);
document.getElementById("enable-audio").addEventListener("change", savePrefs);

// Config inputs — save to server on change (debounced)
let configSaveTimer = null;
function onConfigChange() {
    savePrefs();
    clearTimeout(configSaveTimer);
    configSaveTimer = setTimeout(() => {
        const ppm = parseInt(document.getElementById("points-per-match").value) || 10;
        const tp = parseInt(document.getElementById("target-points").value) || 999;
        socket.emit("save_bot_config", { points_per_match: ppm, target_points: tp });
    }, 500);
}
document.getElementById("points-per-match").addEventListener("input", onConfigChange);
document.getElementById("target-points").addEventListener("input", onConfigChange);

// ==========================================
// 初始化
// ==========================================
restorePrefs();
applyI18n();

// Auto-scroll button default active
document.getElementById("btn-autoscroll").classList.add("active");

// Typewriter effect for waiting text
(function typewriter() {
    const el = document.getElementById("typewriter-text");
    if (!el) return;
    const text = t("waitingConnection");
    let i = 0;
    function tick() {
        if (!el.parentElement) return; // removed by log entries
        el.textContent = text.slice(0, i + 1);
        i++;
        if (i < text.length) {
            setTimeout(tick, 60);
        }
    }
    tick();
})();

// ==========================================
// Auto-Update System
// ==========================================
let isRebooting = false;

socket.on("version_info", (data) => {
    document.title = `FH6 AutoBot v${data.version} — Control Panel`;
    const badge = document.getElementById("version-badge");
    if (badge) badge.textContent = `v${data.version}`;
});

socket.on("update_available", (data) => {
    const banner = document.getElementById("update-banner");
    const msg = document.getElementById("update-msg");
    const link = document.getElementById("update-release-link");
    const sizeMB = data.file_size ? ` (${(data.file_size / 1048576).toFixed(1)} MB)` : "";
    msg.textContent = `🆕 v${data.version} available${sizeMB} (current: v${data.current})`;
    if (data.release_url) {
        link.href = data.release_url;
        link.style.display = "";
    } else {
        link.style.display = "none";
    }
    banner.style.display = "flex";
});

socket.on("update_progress", (data) => {
    const bar = document.getElementById("update-progress-bar");
    const msg = document.getElementById("update-progress-msg");
    if (data.total > 0) {
        const pct = Math.round((data.downloaded / data.total) * 100);
        bar.style.width = pct + "%";
        const mbDone = (data.downloaded / 1048576).toFixed(1);
        const mbTotal = (data.total / 1048576).toFixed(1);
        msg.textContent = `⬇️ Downloading... ${mbDone} / ${mbTotal} MB (${pct}%)`;
    }
});

socket.on("update_status", (data) => {
    if (data.error) {
        alert("❌ " + data.msg);
        // Restore banner
        document.getElementById("update-progress").style.display = "none";
        document.getElementById("update-banner").style.display = "flex";
        document.getElementById("update-btn").disabled = false;
    }
});

socket.on("rebooting", () => {
    isRebooting = true;
    document.getElementById("update-progress").style.display = "none";
    document.getElementById("update-banner").style.display = "none";
    document.getElementById("rebooting-overlay").style.display = "flex";

    // Poll for reconnection every 3 seconds
    const pollReconnect = setInterval(() => {
        fetch("/", { method: "HEAD" })
            .then(() => {
                clearInterval(pollReconnect);
                window.location.reload();
            })
            .catch(() => {});
    }, 3000);
});

// Override disconnect handler — don't show error if rebooting
const origDisconnectHandler = socket.listeners("disconnect");
socket.on("disconnect", () => {
    if (isRebooting) return; // suppress disconnect error during reboot
});

function doUpdate() {
    document.getElementById("update-banner").style.display = "none";
    document.getElementById("update-progress").style.display = "flex";
    document.getElementById("update-btn").disabled = true;
    socket.emit("do_update");
}

function checkUpdate() {
    socket.emit("check_update");
}

// ==========================================
// Web UI Enhancements Helpers (Proposals 1-3)
// ==========================================

// Web Audio API Synthesizer
let audioCtx = null;

function getAudioContext() {
    if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioCtx.state === "suspended") {
        audioCtx.resume();
    }
    return audioCtx;
}

function playSuccessChime() {
    if (!audioEnabled) return;
    try {
        const ctx = getAudioContext();
        const now = ctx.currentTime;
        const freqs = [523.25, 659.25, 783.99, 1046.50]; // C5, E5, G5, C6
        
        freqs.forEach((freq, idx) => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            
            osc.type = "sine";
            osc.frequency.setValueAtTime(freq, now + idx * 0.08);
            
            gain.gain.setValueAtTime(0.15, now + idx * 0.08);
            gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.08 + 0.4);
            
            osc.connect(gain);
            gain.connect(ctx.destination);
            
            osc.start(now + idx * 0.08);
            osc.stop(now + idx * 0.08 + 0.4);
        });
    } catch (e) {
        console.error("Audio chime failed", e);
    }
}

function playWarningBeep() {
    if (!audioEnabled) return;
    try {
        const ctx = getAudioContext();
        const now = ctx.currentTime;
        const delays = [0, 0.2];
        
        delays.forEach(delay => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            const filter = ctx.createBiquadFilter();
            
            osc.type = "sawtooth";
            osc.frequency.setValueAtTime(150, now + delay);
            
            gain.gain.setValueAtTime(0.2, now + delay);
            gain.gain.exponentialRampToValueAtTime(0.001, now + delay + 0.15);
            
            filter.type = "lowpass";
            filter.frequency.setValueAtTime(600, now + delay);
            
            osc.connect(filter);
            filter.connect(gain);
            gain.connect(ctx.destination);
            
            osc.start(now + delay);
            osc.stop(now + delay + 0.15);
        });
    } catch (e) {
        console.error("Audio beep failed", e);
    }
}

// Notifications API Wrapper
function sendDesktopNotification(title, body) {
    if (!notificationsEnabled) return;
    if (Notification.permission === "granted") {
        try {
            new Notification(title, {
                body: body,
                tag: "fh6-autobot",
                icon: "/static/favicon.ico"
            });
        } catch (e) {
            console.error("Notification failed", e);
        }
    }
}

window.toggleNotifications = function() {
    const toggle = document.getElementById("enable-notifications");
    notificationsEnabled = toggle.checked;
    if (notificationsEnabled && Notification.permission !== "granted") {
        Notification.requestPermission().then(permission => {
            if (permission !== "granted") {
                toggle.checked = false;
                notificationsEnabled = false;
                savePrefs();
                showToast("Notification permission denied");
            } else {
                showToast("Notifications enabled!");
                sendDesktopNotification("FH6 AutoBot", "Desktop notifications are active.");
            }
        });
    }
};

window.toggleAudioPreference = function() {
    const toggle = document.getElementById("enable-audio");
    audioEnabled = toggle.checked;
    if (audioEnabled) {
        playSuccessChime();
    }
};

// Trigger Notifications based on log level or state changes
function triggerNotificationForLog(data) {
    if ((data.level || "info").toLowerCase() === "error") {
        playWarningBeep();
        sendDesktopNotification("Bot Alert - Error", data.msg);
    }
}

function onStateChanged(prev, curr) {
    if (curr === "STATE_TRASH_CARS") {
        playSuccessChime();
        sendDesktopNotification("Farming Finished", "Entering clean-up and sell phase.");
    } else if (curr === "STATE_UPGRADE_CARS") {
        playSuccessChime();
        sendDesktopNotification("Upgrade Phase", "Starting car skill points upgrade.");
    }
}

// Pure SVG Telemetry Chart Renderer
function renderSVGChart(races) {
    const container = document.getElementById("chart-svg-container");
    const section = document.getElementById("performance-chart-section");
    if (!container || !section) return;

    const validRaces = (races || []).filter(r => r.duration !== null && r.duration !== undefined);
    if (validRaces.length < 2) {
        section.style.display = "none";
        return;
    }

    section.style.display = "flex";
    container.innerHTML = "";

    // Lazy load standard tooltip element
    let tooltip = document.getElementById("chart-tooltip");
    if (!tooltip) {
        tooltip = document.createElement("div");
        tooltip.id = "chart-tooltip";
        tooltip.className = "chart-tooltip-el";
        document.body.appendChild(tooltip);
    }

    const width = container.clientWidth || 600;
    const height = 160;
    const paddingLeft = 45;
    const paddingRight = 20;
    const paddingTop = 25;
    const paddingBottom = 30;

    const chartWidth = width - paddingLeft - paddingRight;
    const chartHeight = height - paddingTop - paddingBottom;

    const durations = validRaces.map(r => r.duration);
    const minDur = Math.min(...durations);
    const maxDur = Math.max(...durations);
    const durRange = maxDur - minDur;

    const yMin = Math.max(0, minDur - Math.ceil(durRange * 0.15));
    const yMax = maxDur + Math.ceil(durRange * 0.15);
    const yRange = (yMax - yMin) || 1;

    const getX = (idx) => paddingLeft + (idx / (validRaces.length - 1)) * chartWidth;
    const getY = (val) => paddingTop + chartHeight - ((val - yMin) / yRange) * chartHeight;

    let svg = `<svg width="${width}" height="${height}" style="overflow: visible;">`;
    
    // Gradients and glow filter definitions
    svg += `
        <defs>
            <linearGradient id="chart-grad" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stop-color="var(--neon-blue)" />
                <stop offset="100%" stop-color="var(--neon-pink)" />
            </linearGradient>
            <linearGradient id="chart-area-grad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="var(--neon-blue)" stop-opacity="0.15" />
                <stop offset="100%" stop-color="var(--neon-blue)" stop-opacity="0.0" />
            </linearGradient>
            <filter id="glow-filter" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="3.5" result="blur" />
                <feMerge>
                    <feMergeNode in="blur" />
                    <feMergeNode in="SourceGraphic" />
                </feMerge>
            </filter>
        </defs>
    `;

    // Draw Y grid lines & labels
    const gridRows = 3;
    for (let i = 0; i <= gridRows; i++) {
        const val = yMin + (i / gridRows) * yRange;
        const y = getY(val);
        svg += `<line x1="${paddingLeft}" y1="${y}" x2="${width - paddingRight}" y2="${y}" stroke="rgba(255,255,255,0.04)" stroke-width="1" />`;
        
        const m = Math.floor(val / 60);
        const s = Math.round(val % 60);
        const label = m > 0 ? `${m}m` : `${s}s`;
        svg += `<text x="${paddingLeft - 8}" y="${y + 4}" fill="var(--text-secondary)" font-size="9" font-weight="600" text-anchor="end">${label}</text>`;
    }

    // Coordinates points list
    const points = validRaces.map((r, idx) => ({
        x: getX(idx),
        y: getY(r.duration),
        match: r.match,
        duration: r.duration,
        status: r.status,
        ts: r.ts
    }));

    const pathD = points.map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(" ");
    
    // Enclosed area path
    if (points.length > 0) {
        const areaD = `${pathD} L ${points[points.length - 1].x} ${paddingTop + chartHeight} L ${points[0].x} ${paddingTop + chartHeight} Z`;
        svg += `<path d="${areaD}" fill="url(#chart-area-grad)" />`;
    }

    // Stroke line path
    svg += `<path d="${pathD}" fill="none" stroke="url(#chart-grad)" stroke-width="2.5" filter="url(#glow-filter)" stroke-linecap="round" stroke-linejoin="round" />`;

    // Render circles on points
    points.forEach(p => {
        const color = p.status === "success" ? "var(--neon-cyan)" : "var(--neon-pink)";
        svg += `
            <circle cx="${p.x}" cy="${p.y}" r="4.2" fill="#070b1a" stroke="${color}" stroke-width="1.8"
                style="cursor: pointer; transition: r 0.15s ease;"
                onmouseover="showChartTooltip(event, '${p.match}', '${p.duration}', '${p.status}', '${p.ts}')"
                onmouseout="hideChartTooltip()"
                class="chart-point"
            />
        `;
    });

    // Draw X labels
    if (points.length > 0) {
        const indices = [0, Math.floor(points.length / 2), points.length - 1];
        const unique = [...new Set(indices)].filter(idx => idx < points.length);
        unique.forEach(idx => {
            const p = points[idx];
            svg += `<text x="${p.x}" y="${height - 8}" fill="var(--text-secondary)" font-size="9" text-anchor="middle">Run #${p.match}</text>`;
        });
    }

    svg += `</svg>`;
    container.innerHTML = svg;
}

window.showChartTooltip = function(event, match, duration, status, ts) {
    const tooltip = document.getElementById("chart-tooltip");
    if (!tooltip) return;

    const m = Math.floor(duration / 60);
    const s = duration % 60;
    const durStr = m > 0 ? `${m}m ${s}s` : `${s}s`;
    
    // Formatting date
    let dateStr = ts;
    try {
        const dt = new Date(ts);
        if (!isNaN(dt)) {
            dateStr = dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        }
    } catch (_) {}

    tooltip.innerHTML = `
        <div style="font-weight: 700; color: var(--neon-blue); margin-bottom: 2px;">Run #${match}</div>
        <div>Duration: <span style="font-weight: 600;">${durStr}</span></div>
        <div>Status: <span style="color: ${status === 'success' ? 'var(--neon-cyan)' : 'var(--neon-pink)'}; font-weight: 600;">${status.toUpperCase()}</span></div>
        <div style="font-size: 0.65rem; color: var(--text-muted); margin-top: 2px;">${dateStr}</div>
    `;
    tooltip.style.display = "block";

    const rect = event.target.getBoundingClientRect();
    tooltip.style.left = `${rect.left + window.scrollX + rect.width / 2}px`;
    tooltip.style.top = `${rect.top + window.scrollY}px`;
};

window.hideChartTooltip = function() {
    const tooltip = document.getElementById("chart-tooltip");
    if (tooltip) {
        tooltip.style.display = "none";
    }
};

// Re-apply saved preferences once the DOM is ready.
// (Toggle change handlers are already wired up above; restorePrefs is idempotent.)
document.addEventListener("DOMContentLoaded", () => {
    restorePrefs();
});

// ==========================================
// ROI Calibration Tool
// ==========================================
let roiModal = null;
let roiImage = null;
let roiBox = null;
let roiContainer = null;
let roiStatus = null;
let roiStatusText = null;
let roiSaveBtn = null;
let roiWatchdog = null;

let isDrawing = false;
let startX = 0;
let startY = 0;
let endX = 0;
let endY = 0;

document.addEventListener("DOMContentLoaded", () => {
    roiModal = document.getElementById("roi-modal");
    roiImage = document.getElementById("roi-image");
    roiBox = document.getElementById("roi-box");
    roiContainer = document.getElementById("roi-container");
    roiStatus = document.getElementById("roi-status");
    roiStatusText = document.getElementById("roi-status-text");
    roiSaveBtn = document.getElementById("btn-save-roi");

    if (roiContainer) {
        roiContainer.addEventListener("mousedown", onRoiMouseDown);
        roiContainer.addEventListener("mousemove", onRoiMouseMove);
        document.addEventListener("mouseup", onRoiMouseUp); // Listen on document to catch mouseup outside
    }
});

// Show the status overlay (loading spinner or error) and hide the drawing canvas.
function showRoiStatus(msg, isError) {
    if (roiStatus) {
        roiStatus.classList.toggle("error", !!isError);
        roiStatus.style.display = "flex";
    }
    if (roiStatusText) roiStatusText.textContent = msg;
    if (roiContainer) roiContainer.style.display = "none";
    if (roiSaveBtn) roiSaveBtn.disabled = true;
}

// Hide the status overlay and reveal the canvas so the user can draw the box.
function showRoiCanvas() {
    if (roiStatus) roiStatus.style.display = "none";
    if (roiContainer) roiContainer.style.display = "inline-block";
    if (roiSaveBtn) roiSaveBtn.disabled = false;
}

function clearRoiWatchdog() {
    if (roiWatchdog !== null) {
        clearTimeout(roiWatchdog);
        roiWatchdog = null;
    }
}

function startCalibration() {
    // Open the modal immediately in a loading state so the user always gets
    // feedback, then request the screenshot. Any reply (success/error) or the
    // watchdog timeout updates this already-open modal instead of a popup.
    if (!roiModal) {
        showToast("❌ roi-modal element not found");
        return;
    }
    if (roiBox) roiBox.style.display = "none";
    startX = startY = endX = endY = 0;
    showRoiStatus(t("roiCapturing"), false);
    roiModal.classList.add("active");

    clearRoiWatchdog();
    roiWatchdog = setTimeout(() => {
        roiWatchdog = null;
        showRoiStatus(t("roiTimeout"), true);
    }, 10000);

    socket.emit("capture_roi_screenshot");
}

socket.on("roi_capture_success", (data) => {
    console.log("Received roi_capture_success", data);
    clearRoiWatchdog();
    if (!roiImage) {
        showRoiStatus("❌ roi-image element not found", true);
        return;
    }
    roiImage.onload = () => {
        console.log("Image loaded successfully!");
        if (roiModal && !roiModal.classList.contains("active")) roiModal.classList.add("active");
        showRoiCanvas();
        if (roiBox) roiBox.style.display = "none";
        startX = startY = endX = endY = 0;
    };
    roiImage.onerror = () => {
        console.error("Failed to load image from URL:", data.url);
        showRoiStatus("❌ 无法加载截图文件 (HTTP 404 或网络错误): " + data.url, true);
    };
    roiImage.src = data.url;
});

socket.on("roi_capture_error", (data) => {
    console.warn("Received roi_capture_error", data);
    clearRoiWatchdog();
    // Ensure the modal is visible so the error is never silent.
    if (roiModal && !roiModal.classList.contains("active")) roiModal.classList.add("active");
    showRoiStatus("❌ " + (data && data.msg ? data.msg : "Capture failed"), true);
});

function closeCalibration() {
    clearRoiWatchdog();
    if (roiModal) {
        roiModal.classList.remove("active");
    }
}

function onRoiMouseDown(e) {
    if (e.button !== 0) return;
    
    const rect = roiImage.getBoundingClientRect();
    if (e.clientX < rect.left || e.clientX > rect.right || e.clientY < rect.top || e.clientY > rect.bottom) {
        return;
    }

    isDrawing = true;
    startX = e.clientX - rect.left;
    startY = e.clientY - rect.top;
    
    updateRoiBox(startX, startY, startX, startY);
    roiBox.style.display = "block";
    e.preventDefault();
}

function onRoiMouseMove(e) {
    if (!isDrawing) return;
    
    const rect = roiImage.getBoundingClientRect();
    
    let currentX = e.clientX - rect.left;
    let currentY = e.clientY - rect.top;
    currentX = Math.max(0, Math.min(currentX, rect.width));
    currentY = Math.max(0, Math.min(currentY, rect.height));

    updateRoiBox(startX, startY, currentX, currentY);
}

function onRoiMouseUp(e) {
    if (!isDrawing) return;
    isDrawing = false;
    
    const rect = roiImage.getBoundingClientRect();
    let currentX = e.clientX - rect.left;
    let currentY = e.clientY - rect.top;
    currentX = Math.max(0, Math.min(currentX, rect.width));
    currentY = Math.max(0, Math.min(currentY, rect.height));
    
    endX = currentX;
    endY = currentY;
    
    updateRoiBox(startX, startY, endX, endY);
}

function updateRoiBox(x1, y1, x2, y2) {
    const left = Math.min(x1, x2);
    const top = Math.min(y1, y2);
    const width = Math.abs(x1 - x2);
    const height = Math.abs(y1 - y2);
    
    roiBox.style.left = left + "px";
    roiBox.style.top = top + "px";
    roiBox.style.width = width + "px";
    roiBox.style.height = height + "px";
}

function saveCalibration() {
    if (!roiBox || roiBox.style.display === "none" || Math.abs(startX - endX) < 5 || Math.abs(startY - endY) < 5) {
        showToast("Please draw a valid box first!");
        return;
    }

    const rect = roiImage.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;

    const left = Math.min(startX, endX) / width;
    const right = Math.max(startX, endX) / width;
    const top = Math.min(startY, endY) / height;
    const bottom = Math.max(startY, endY) / height;

    const custom_roi = [top, bottom, left, right];
    socket.emit("save_bot_config", { custom_roi: custom_roi });
    showToast("Custom ROI Saved Successfully!");
    closeCalibration();
}

function resetCalibration() {
    socket.emit("save_bot_config", { custom_roi: null });
    showToast("ROI Reset to Default!");
    closeCalibration();
}
