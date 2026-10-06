/**
 * VICTOR Node.js Powerhouse Service
 * Bridges high-performance Node capabilities to VICTOR:
 * - Real-time WebSocket IPC (port 8765) connecting Web UI, Gestures, and Python Core
 * - In-depth hardware, GPU, thermal, and network telemetry via 'systeminformation'
 * - Deep browser automation and web extraction via 'playwright'
 * - Native desktop toast notifications via 'node-notifier'
 * - Multi-monitor display capture via 'screenshot-desktop'
 */
const { WebSocketServer } = require('ws');
const si = require('systeminformation');
const notifier = require('node-notifier');
const path = require('path');
const fs = require('fs');

const WS_PORT = process.env.VICTOR_WS_PORT || 8765;
let wss = null;
const clients = new Set();

function startWebSocketServer() {
  try {
    wss = new WebSocketServer({ port: WS_PORT });
    console.log(`[VICTOR Node] WebSocket IPC Server listening on ws://127.0.0.1:${WS_PORT}`);

    wss.on('connection', (ws) => {
      clients.add(ws);
      console.log(`[VICTOR Node] Client connected. Total active connections: ${clients.size}`);

      ws.on('message', async (raw) => {
        try {
          const msg = JSON.parse(raw.toString());
          await handleMessage(ws, msg);
        } catch (err) {
          console.error('[VICTOR Node] Message parse error:', err.message);
        }
      });

      ws.on('close', () => {
        clients.delete(ws);
        console.log(`[VICTOR Node] Client disconnected. Active connections: ${clients.size}`);
      });

      ws.on('error', (err) => {
        console.error('[VICTOR Node] Client socket error:', err.message);
        clients.delete(ws);
      });
    });

    wss.on('error', (err) => {
      if (err.code === 'EADDRINUSE') {
        console.log(`[VICTOR Node] Port ${WS_PORT} already in use. Assuming service instance already running.`);
      } else {
        console.error('[VICTOR Node] Server error:', err);
      }
    });
  } catch (err) {
    console.error('[VICTOR Node] Failed to bind WebSocket server:', err.message);
  }
}

async function handleMessage(senderWs, msg) {
  const type = msg.type;

  switch (type) {
    case 'ping':
      senderWs.send(JSON.stringify({ type: 'pong', timestamp: Date.now() }));
      break;

    case 'gesture':
      // Broadcast gesture events from Web camera to all listeners (including Python core)
      console.log(`[VICTOR Gesture] Detected: ${msg.gesture} (Confidence: ${msg.confidence || 1.0})`);
      broadcast(msg, senderWs);
      break;

    case 'status_update':
    case 'subtitle_update':
      // Relay status and speech subtitles between components
      broadcast(msg, senderWs);
      break;

    case 'get_telemetry':
      const telemetry = await getSystemTelemetry();
      senderWs.send(JSON.stringify({ type: 'telemetry_result', data: telemetry }));
      break;

    case 'notify':
      showNotification(msg.title || 'VICTOR System', msg.message || 'Directive executed.');
      senderWs.send(JSON.stringify({ type: 'notify_sent', success: true }));
      break;

    case 'browser_extract':
      const content = await extractWebContent(msg.url);
      senderWs.send(JSON.stringify({ type: 'browser_extract_result', url: msg.url, data: content }));
      break;

    default:
      // Relay any other broadcast messages
      broadcast(msg, senderWs);
      break;
  }
}

function broadcast(data, excludeWs = null) {
  const payload = typeof data === 'string' ? data : JSON.stringify(data);
  for (const client of clients) {
    if (client !== excludeWs && client.readyState === 1) { // OPEN
      client.send(payload);
    }
  }
}

function showNotification(title, message) {
  try {
    notifier.notify({
      title: title,
      message: message,
      sound: true,
      wait: false
    });
  } catch (e) {
    console.error('[VICTOR Node] Notification error:', e.message);
  }
}

async function getSystemTelemetry() {
  try {
    const [cpu, mem, graphics, currentLoad, temp, battery] = await Promise.all([
      si.cpu(),
      si.mem(),
      si.graphics(),
      si.currentLoad(),
      si.cpuTemperature().catch(() => ({ main: -1 })),
      si.battery().catch(() => ({ hasBattery: false }))
    ]);

    return {
      cpu: {
        manufacturer: cpu.manufacturer,
        brand: cpu.brand,
        cores: cpu.cores,
        speed: cpu.speed,
        currentLoad: Math.round(currentLoad.currentLoad),
        temperature: temp.main > 0 ? `${temp.main}°C` : 'N/A'
      },
      memory: {
        totalGb: (mem.total / 1024 ** 3).toFixed(1),
        usedGb: (mem.used / 1024 ** 3).toFixed(1),
        freeGb: (mem.free / 1024 ** 3).toFixed(1),
        usedPercent: Math.round((mem.used / mem.total) * 100)
      },
      gpu: graphics.controllers.map((g) => ({
        model: g.model,
        vram: g.vram ? `${g.vram} MB` : 'Dynamic'
      })),
      battery: battery.hasBattery
        ? {
            percent: battery.percent,
            isCharging: battery.isCharging
          }
        : null
    };
  } catch (err) {
    return { error: err.message };
  }
}

async function extractWebContent(url) {
  try {
    const { chromium } = require('playwright');
    const browser = await chromium.launch({ channel: 'msedge', headless: true });
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 });
    const title = await page.title();
    const bodyText = await page.innerText('body');
    await browser.close();

    return {
      title,
      summary: bodyText.slice(0, 2000).replace(/\s+/g, ' ').trim()
    };
  } catch (err) {
    return { error: `Playwright extraction failed: ${err.message}` };
  }
}

async function searchAndSummarize(query) {
  try {
    const { chromium } = require('playwright');
    const browser = await chromium.launch({ channel: 'msedge', headless: true });
    const page = await browser.newPage();
    const encoded = encodeURIComponent(query);
    await page.goto(`https://www.bing.com/search?q=${encoded}`, { waitUntil: 'load', timeout: 12000 });

    const results = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('li.b_algo'))
        .slice(0, 4)
        .map((el) => el.textContent.replace(/\s+/g, ' ').trim().slice(0, 300));
    });

    await browser.close();
    return results.length > 0 ? results : ['No search results found.'];
  } catch (err) {
    return [`Search error: ${err.message}`];
  }
}

// CLI handler for direct execution
if (require.main === module) {
  const args = process.argv.slice(2);
  if (args.includes('--telemetry')) {
    getSystemTelemetry().then((res) => {
      console.log(JSON.stringify(res, null, 2));
      process.exit(0);
    });
  } else if (args.includes('--search')) {
    const q = args.slice(args.indexOf('--search') + 1).join(' ');
    searchAndSummarize(q).then((res) => {
      console.log(JSON.stringify(res, null, 2));
      process.exit(0);
    });
  } else if (args.includes('--notify')) {
    const title = args[args.indexOf('--notify') + 1] || 'VICTOR';
    const msg = args[args.indexOf('--notify') + 2] || 'Directive acknowledged.';
    showNotification(title, msg);
    console.log('Notification dispatched.');
    process.exit(0);
  } else {
    startWebSocketServer();
  }
}

module.exports = {
  startWebSocketServer,
  getSystemTelemetry,
  extractWebContent,
  showNotification,
  broadcast
};
