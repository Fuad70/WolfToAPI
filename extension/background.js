const AGENT_WS_URL = 'ws://127.0.0.1:8765';
const CALLBACK_URL = 'http://127.0.0.1:4040/api/ext/callback';
const FLOW_URL = 'https://labs.google/fx/tools/flow';

let ws = null;
let flowKey = null;
let callbackSecret = null;
let state = 'off';
let metrics = { tokenCapturedAt: null, successCount: 0, failedCount: 0, lastError: null };

chrome.runtime.onInstalled.addListener(init);
chrome.runtime.onStartup.addListener(init);
chrome.alarms.onAlarm.addListener(async alarm => {
  if (alarm.name === 'reconnect') connectToAgent();
  if (alarm.name === 'token-refresh') await captureTokenFromFlowTab(false);
  if (alarm.name === 'keepalive' && (!ws || ws.readyState !== WebSocket.OPEN)) connectToAgent();
});

async function init() {
  const saved = await chrome.storage.local.get(['flowKey', 'callbackSecret', 'metrics']);
  flowKey = saved.flowKey || null;
  callbackSecret = saved.callbackSecret || null;
  metrics = { ...metrics, ...(saved.metrics || {}) };
  chrome.alarms.create('keepalive', { periodInMinutes: 0.5 });
  connectToAgent();
  await captureTokenFromFlowTab(false);
}

chrome.webRequest.onBeforeSendHeaders.addListener(
  details => {
    const authHeader = (details.requestHeaders || []).find(h => h.name?.toLowerCase() === 'authorization');
    const value = authHeader?.value || '';
    if (!value.startsWith('Bearer ya29.')) return;
    flowKey = value.replace(/^Bearer\s+/i, '').trim();
    metrics.tokenCapturedAt = Date.now();
    chrome.storage.local.set({ flowKey, metrics });
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'token_captured', flowKey }));
    }
  },
  { urls: ['https://aisandbox-pa.googleapis.com/*', 'https://labs.google/*'] },
  ['requestHeaders', 'extraHeaders']
);

function connectToAgent() {
  if (ws?.readyState === WebSocket.OPEN || ws?.readyState === WebSocket.CONNECTING) return;
  try {
    ws = new WebSocket(AGENT_WS_URL);
  } catch (error) {
    scheduleReconnect();
    return;
  }

  ws.onopen = () => {
    setState('idle');
    chrome.alarms.clear('reconnect');
    chrome.alarms.create('token-refresh', { periodInMinutes: 45 });
    ws.send(JSON.stringify({
      type: 'extension_ready',
      flowKeyPresent: !!flowKey,
      tokenAge: metrics.tokenCapturedAt ? Date.now() - metrics.tokenCapturedAt : null,
    }));
    if (flowKey) ws.send(JSON.stringify({ type: 'token_captured', flowKey }));
  };

  ws.onmessage = async event => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === 'callback_secret') {
        callbackSecret = msg.secret;
        chrome.storage.local.set({ callbackSecret });
        return;
      }
      if (msg.method === 'api_request') return await handleApiRequest(msg);
      if (msg.method === 'trpc_request') return await handleTrpcRequest(msg);
      if (msg.method === 'get_status') return sendToAgent({
        id: msg.id,
        result: {
          state,
          flowKeyPresent: !!flowKey,
          tokenAge: metrics.tokenCapturedAt ? Date.now() - metrics.tokenCapturedAt : null,
          metrics,
        },
      });
      if (msg.method === 'open_flow') {
        const tab = await ensureFlowTab(true);
        return sendToAgent({ id: msg.id, ok: true, result: { tabId: tab.id } });
      }
      if (msg.type === 'pong') return;
    } catch (error) {
      console.error('[FlowKit] Message error', error);
    }
  };

  ws.onclose = () => {
    setState('off');
    scheduleReconnect();
  };

  ws.onerror = error => {
    metrics.lastError = 'WS_ERROR';
    chrome.storage.local.set({ metrics });
  };
}

function scheduleReconnect() {
  chrome.alarms.create('reconnect', { delayInMinutes: 0.1 });
}

function setState(next) {
  state = next;
}

async function ensureFlowTab(active = false) {
  const tabs = await chrome.tabs.query({ url: ['https://labs.google/fx/tools/flow*', 'https://labs.google/fx/*/tools/flow*'] });
  if (tabs.length) {
    if (active) await chrome.tabs.update(tabs[0].id, { active: true });
    return tabs[0];
  }
  return await chrome.tabs.create({ url: FLOW_URL, active });
}

async function captureTokenFromFlowTab(active = false) {
  const tab = await ensureFlowTab(active);
  try {
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['content.js'] });
  } catch (error) {
    console.warn('[FlowKit] failed to inject content script', error);
  }
}

async function solveCaptcha(pageAction) {
  const tab = await ensureFlowTab(false);
  return await new Promise(resolve => {
    chrome.tabs.sendMessage(tab.id, {
      type: 'GET_CAPTCHA',
      requestId: crypto.randomUUID(),
      pageAction,
    }, response => {
      if (chrome.runtime.lastError) {
        resolve({ error: chrome.runtime.lastError.message });
        return;
      }
      resolve(response || { error: 'No captcha response' });
    });
  });
}

function cloneJson(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value));
}

function injectCaptcha(body, token) {
  const next = cloneJson(body || {});
  if (next.clientContext?.recaptchaContext) next.clientContext.recaptchaContext.token = token;
  for (const item of next.requests || []) {
    if (item.clientContext?.recaptchaContext) item.clientContext.recaptchaContext.token = token;
  }
  return next;
}

async function handleApiRequest(msg) {
  const { id, params } = msg;
  setState('running');
  try {
    if (!flowKey) {
      await captureTokenFromFlowTab(false);
      await sleep(2000);
    }
    if (!flowKey) throw new Error('No Flow bearer token captured yet. Log in and leave a Flow tab open.');
    let body = cloneJson(params.body);
    if (params.captchaAction) {
      const captcha = await solveCaptcha(params.captchaAction);
      if (captcha.error) throw new Error(captcha.error);
      body = injectCaptcha(body, captcha.token);
    }
    const headers = { ...(params.headers || {}), authorization: `Bearer ${flowKey}` };
    const response = await fetch(params.url, {
      method: params.method || 'GET',
      headers,
      body: body ? JSON.stringify(body) : undefined,
      credentials: 'include',
    });
    const text = await response.text();
    let data;
    try { data = JSON.parse(text); } catch { data = { raw: text }; }
    if (!response.ok) throw new Error(`HTTP ${response.status}: ${text.slice(0, 400)}`);
    metrics.successCount += 1;
    metrics.lastError = null;
    chrome.storage.local.set({ metrics });
    sendToAgent({ id, ok: true, status: response.status, data });
  } catch (error) {
    metrics.failedCount += 1;
    metrics.lastError = error.message;
    chrome.storage.local.set({ metrics });
    sendToAgent({ id, error: error.message });
  } finally {
    setState('idle');
  }
}

async function handleTrpcRequest(msg) {
  const { id, params } = msg;
  try {
    const response = await fetch(params.url, {
      method: params.method || 'POST',
      headers: { 'content-type': 'application/json', ...(params.headers || {}) },
      body: JSON.stringify(params.body || {}),
      credentials: 'include',
    });
    const text = await response.text();
    let data;
    try { data = JSON.parse(text); } catch { data = { raw: text }; }
    if (!response.ok) throw new Error(`HTTP ${response.status}: ${text.slice(0, 400)}`);
    sendToAgent({ id, ok: true, status: response.status, data });
  } catch (error) {
    sendToAgent({ id, error: error.message });
  }
}

function sendToAgent(message) {
  fetch(CALLBACK_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Flowkit-Secret': callbackSecret || '' },
    body: JSON.stringify(message),
  }).catch(() => {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message));
    }
  });
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
