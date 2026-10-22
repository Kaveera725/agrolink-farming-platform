const { spawn } = require('child_process');
const http = require('http');
const fs = require('fs');

async function inspectWithEmulation(width, height, isMobile, outfile) {
  return new Promise((resolve, reject) => {
    const port = Math.floor(9220 + Math.random() * 20);
    const edge = spawn('C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe', [
      '--headless=new',
      `--remote-debugging-port=${port}`,
      '--disable-gpu',
      '--window-size=1280,1000',
      'http://127.0.0.1:5000/marketplace/'
    ]);

    setTimeout(() => {
      http.get(`http://127.0.0.1:${port}/json`, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', async () => {
          try {
            const targets = JSON.parse(data);
            const pageTarget = targets.find(t => t.type === 'page' && t.url.includes('marketplace'));
            if (!pageTarget) { edge.kill(); return reject(new Error('Target not found')); }
            
            const ws = new WebSocket(pageTarget.webSocketDebuggerUrl);
            let id = 1;
            const send = (method, params = {}) => new Promise((resSend) => {
              const mid = id++;
              const handler = (evt) => {
                const resp = JSON.parse(evt.data);
                if (resp.id === mid) {
                  ws.removeEventListener('message', handler);
                  resSend(resp.result);
                }
              };
              ws.addEventListener('message', handler);
              ws.send(JSON.stringify({ id: mid, method, params }));
            });

            ws.onopen = async () => {
              await send('Page.enable');
              await send('Runtime.enable');
              await send('Emulation.setDeviceMetricsOverride', {
                width: width,
                height: height,
                deviceScaleFactor: 2,
                mobile: isMobile
              });

              await new Promise(r => setTimeout(r, 2000));

              const evalRes = await send('Runtime.evaluate', {
                expression: `
                  JSON.stringify({
                    viewportWidth: window.innerWidth,
                    docScrollWidth: document.documentElement.scrollWidth,
                    hasHorizontalOverflow: document.documentElement.scrollWidth > window.innerWidth,
                    cardCount: document.querySelectorAll('article').length,
                    gridCols: getComputedStyle(document.querySelector('.grid-marketplace')).gridTemplateColumns.split(' ').length,
                    firstCardWidth: document.querySelector('article')?.offsetWidth
                  })
                `
              });
              console.log(`[Viewport ${width}x${height} (Mobile: ${isMobile})] Layout evaluation:`, evalRes.result.value);

              const screenshot = await send('Page.captureScreenshot', { format: 'png' });
              fs.writeFileSync(outfile, Buffer.from(screenshot.data, 'base64'));
              console.log(`Saved screenshot to ${outfile}`);

              ws.close();
              edge.kill();
              resolve();
            };
          } catch (err) {
            edge.kill();
            reject(err);
          }
        });
      }).on('error', err => {
        edge.kill();
        reject(err);
      });
    }, 2000);
  });
}

async function run() {
  console.log('Testing True Mobile 360px...');
  await inspectWithEmulation(360, 800, true, 'scratch/marketplace_360.png');
  console.log('Testing Mobile 420px (2 cols)...');
  await inspectWithEmulation(420, 800, true, 'scratch/marketplace_420.png');
  console.log('Testing Desktop 1280px (4 cols)...');
  await inspectWithEmulation(1280, 900, false, 'scratch/marketplace_1280.png');
  console.log('All CDP visual checks finished successfully!');
}

run().catch(console.error);
