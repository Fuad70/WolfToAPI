(() => {
  const script = document.createElement('script');
  script.src = chrome.runtime.getURL('injected.js');
  script.onload = () => script.remove();
  (document.head || document.documentElement).appendChild(script);
})();

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type !== 'GET_CAPTCHA') return;
  const { requestId, pageAction } = message;
  const timer = setTimeout(() => sendResponse({ error: 'CAPTCHA_TIMEOUT' }), 25000);
  const handler = event => {
    if (event.detail?.requestId !== requestId) return;
    clearTimeout(timer);
    window.removeEventListener('CAPTCHA_RESULT', handler);
    sendResponse({ token: event.detail.token, error: event.detail.error });
  };
  window.addEventListener('CAPTCHA_RESULT', handler);
  window.dispatchEvent(new CustomEvent('GET_CAPTCHA', { detail: { requestId, pageAction } }));
  return true;
});
