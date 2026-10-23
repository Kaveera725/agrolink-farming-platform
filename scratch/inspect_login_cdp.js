const { spawn } = require('child_process');
const http = require('http');
const fs = require('fs');

const edge = spawn('C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe', [
  '--headless=new',
  '--remote-debugging-port=9222',
  '--disable-gpu',
  '--window-size=1280,800',
  'http://127.0.0.1:5000/auth/login'
]);

setTimeout(() => {
  http.get('http://127.0.0.1:9222/json', (res) => {
    let data = '';
    res.on('data', chunk => data += chunk);
    res.on('end', async () => {
      const targets = JSON.parse(data);
      const pageTarget = targets.find(t => t.type === 'page' && t.url.includes('auth/login'));
      if (!pageTarget) {
        console.error('Page target not found');
        edge.kill();
        process.exit(1);
      }
      console.log('Connecting to target:', pageTarget.webSocketDebuggerUrl);

      const ws = new WebSocket(pageTarget.webSocketDebuggerUrl);
      let msgId = 1;

      function send(method, params = {}) {
        return new Promise((resolve) => {
          const id = msgId++;
          const handler = (evt) => {
            const resp = JSON.parse(evt.data);
            if (resp.id === id) {
              ws.removeEventListener('message', handler);
              resolve(resp.result);
            }
          };
          ws.addEventListener('message', handler);
          ws.send(JSON.stringify({ id, method, params }));
        });
      }

      ws.onopen = async () => {
        ws.addEventListener('message', (evt) => {
          const msg = JSON.parse(evt.data);
          if (msg.method === 'Runtime.consoleAPICalled') {
            console.log('[BROWSER CONSOLE]', msg.params.type, msg.params.args.map(a => a.value || a.description).join(' '));
          }
          if (msg.method === 'Runtime.exceptionThrown') {
            console.error('[BROWSER EXCEPTION]', msg.params.exceptionDetails.text, msg.params.exceptionDetails.exception?.description);
          }
        });

        await send('Runtime.enable');
        await send('Page.enable');

        // Wait 2 seconds for Tailwind CDN to finish or fail
        await new Promise(r => setTimeout(r, 2000));

        // Evaluate body styles and tailwind status
        const evalRes = await send('Runtime.evaluate', {
          expression: `
            JSON.stringify({
              hasTailwind: typeof tailwind !== 'undefined',
              styleSheets: Array.from(document.styleSheets).map(s => {
                try { return { href: s.href, rulesCount: s.cssRules.length }; } catch(e) { return { href: s.href, error: e.message }; }
              }),
              bodyBg: getComputedStyle(document.body).backgroundColor,
              headerHeight: document.getElementById('main-header')?.offsetHeight,
              svgWidth: document.querySelector('#main-header svg')?.getBoundingClientRect().width,
              svgHeight: document.querySelector('#main-header svg')?.getBoundingClientRect().height
            })
          `
        });
        console.log('Browser Evaluation:', evalRes.result.value);

        const screenshot = await send('Page.captureScreenshot', { format: 'png' });
        fs.writeFileSync('scratch/login_cdp.png', Buffer.from(screenshot.data, 'base64'));
        console.log('Saved screenshot to scratch/login_cdp.png');

        ws.close();
        edge.kill();
        process.exit(0);
      };
    });
  }).on('error', (e) => {
    console.error('HTTP error:', e.message);
    edge.kill();
    process.exit(1);
  });
}, 2000);
