const SITE_KEY = '6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV';

window.addEventListener('GET_CAPTCHA', async ({ detail }) => {
  const { requestId, pageAction } = detail;
  try {
    await waitForGrecaptcha();
    const token = await window.grecaptcha.enterprise.execute(SITE_KEY, { action: pageAction });
    window.dispatchEvent(new CustomEvent('CAPTCHA_RESULT', { detail: { requestId, token } }));
  } catch (error) {
    window.dispatchEvent(new CustomEvent('CAPTCHA_RESULT', { detail: { requestId, error: error.message } }));
  }
});

function waitForGrecaptcha(timeout = 15000) {
  return new Promise((resolve, reject) => {
    const started = Date.now();
    const check = () => {
      if (window.grecaptcha?.enterprise?.execute) return resolve();
      if (Date.now() - started > timeout) return reject(new Error('grecaptcha not available'));
      setTimeout(check, 200);
    };
    check();
  });
}
