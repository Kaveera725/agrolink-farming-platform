const { spawn } = require('child_process');
const http = require('http');
const fs = require('fs');

async function inspect(width, height, isMobile, outfile) {
  return new Promise((resolve, reject) => {
    const port = Math.floor(9220 + Math.random() * 20);
    const edge = spawn('C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe', [
      '--headless=new',
      `--remote-debugging-port=${port}`,
      '--disable-gpu',
      '--window-size=1280,1000',
      'http://127.0.0.1:5000/marketplace/product/4'
    ]);

    setTimeout(() => {
      http.get(`http://127.0.0.1:${port}/json`, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', async () => {
          try {
            const targets = JSON.parse(data);
            const pageTarget = targets.find(t => t.type === 'page' && t.url.includes('/marketplace/product/'));
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
                    hasBreadcrumbs: document.querySelectorAll('nav[aria-label="Breadcrumb"] li').length,
                    hasMobileStickyBar: !!document.querySelector('.sm\\\\:hidden.fixed.bottom-0'),
                    hasFarmerCard: !!document.querySelector('.card h3'),
                    hasFarmerMap: !!document.getElementById('farmer_map'),
                    hasLightbox: !!document.getElementById('image-lightbox')
                  })
                `
              });
              console.log(`[Viewport ${width}x${height} (Mobile: ${isMobile})] Evaluation:`, evalRes.result.value);

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
  console.log('Inspecting Mobile 360px...');
  await inspect(360, 800, true, 'scratch/detail_360.png');
  console.log('Inspecting Desktop 1280px...');
  await inspect(1280, 900, false, 'scratch/detail_1280.png');
  console.log('All product detail visual inspections finished!');
}

run().catch(console.error);
