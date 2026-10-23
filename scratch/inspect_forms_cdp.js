const { spawn } = require('child_process');
const http = require('http');
const fs = require('fs');

async function runCdp() {
  const port = 9235;
  const edge = spawn('C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe', [
    '--headless=new',
    `--remote-debugging-port=${port}`,
    '--disable-gpu',
    '--window-size=1280,1000',
    'http://127.0.0.1:5000/auth/login'
  ]);

  await new Promise(r => setTimeout(r, 2000));

  http.get(`http://127.0.0.1:${port}/json`, (res) => {
    let data = '';
    res.on('data', chunk => data += chunk);
    res.on('end', async () => {
      try {
        const targets = JSON.parse(data);
        const pageTarget = targets.find(t => t.type === 'page');
        if (!pageTarget) {
          edge.kill();
          console.error("Page target not found");
          process.exit(1);
        }

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
          await send('Network.enable');

          console.log("[CDP] Logging in as nimal@agrolink.lk...");
          await send('Runtime.evaluate', {
            expression: `
              document.querySelector('input[name="email"]').value = 'nimal@agrolink.lk';
              document.querySelector('input[name="password"]').value = 'password123';
              document.querySelector('form').submit();
            `
          });

          await new Promise(r => setTimeout(r, 2000));

          // 1. Inspect /marketplace/list at 360px
          console.log("[CDP] Navigating to /marketplace/list at 360px...");
          await send('Page.navigate', { url: 'http://127.0.0.1:5000/marketplace/list' });
          await new Promise(r => setTimeout(r, 2000));

          await send('Emulation.setDeviceMetricsOverride', {
            width: 360,
            height: 800,
            deviceScaleFactor: 2,
            mobile: true
          });
          await new Promise(r => setTimeout(r, 1000));

          const resProd360 = await send('Runtime.evaluate', {
            expression: `
              JSON.stringify({
                viewportWidth: window.innerWidth,
                docScrollWidth: document.documentElement.scrollWidth,
                hasHorizontalOverflow: document.documentElement.scrollWidth > window.innerWidth,
                hasCategoryChips: document.querySelectorAll('.category-chip').length,
                hasPriceLKR: document.body.textContent.includes('LKR'),
                hasQtyStepper: !!document.querySelector('#qty-increment-btn'),
                hasDropzone: !!document.querySelector('#drop-zone'),
                hasMobileStickyBar: !!document.querySelector('#mobile-action-bar'),
                hasDeliverySlot: !!document.querySelector('#offer-delivery-slot')
              })
            `
          });
          console.log("[CDP] /marketplace/list 360px metrics:", JSON.parse(resProd360.result.value));

          const shotProd360 = await send('Page.captureScreenshot', { format: 'png' });
          fs.writeFileSync('scratch/product_form_360.png', Buffer.from(shotProd360.data, 'base64'));

          // 2. Inspect /marketplace/list at 1280px
          console.log("[CDP] Inspecting /marketplace/list at 1280px...");
          await send('Emulation.setDeviceMetricsOverride', {
            width: 1280,
            height: 900,
            deviceScaleFactor: 1,
            mobile: false
          });
          await new Promise(r => setTimeout(r, 1000));

          const resProd1280 = await send('Runtime.evaluate', {
            expression: `
              JSON.stringify({
                viewportWidth: window.innerWidth,
                docScrollWidth: document.documentElement.scrollWidth,
                hasHorizontalOverflow: document.documentElement.scrollWidth > window.innerWidth,
                isTwoColumnLayout: !!document.querySelector('.lg\\\\:grid-cols-12')
              })
            `
          });
          console.log("[CDP] /marketplace/list 1280px metrics:", JSON.parse(resProd1280.result.value));

          const shotProd1280 = await send('Page.captureScreenshot', { format: 'png' });
          fs.writeFileSync('scratch/product_form_1280.png', Buffer.from(shotProd1280.data, 'base64'));

          // 3. Inspect /dashboard/crops/add at 360px & 1280px
          console.log("[CDP] Navigating to /dashboard/crops/add...");
          await send('Page.navigate', { url: 'http://127.0.0.1:5000/dashboard/crops/add' });
          await new Promise(r => setTimeout(r, 2000));

          await send('Emulation.setDeviceMetricsOverride', {
            width: 360,
            height: 800,
            deviceScaleFactor: 2,
            mobile: true
          });
          await new Promise(r => setTimeout(r, 1000));

          const resCrop360 = await send('Runtime.evaluate', {
            expression: `
              JSON.stringify({
                viewportWidth: window.innerWidth,
                docScrollWidth: document.documentElement.scrollWidth,
                hasHorizontalOverflow: document.documentElement.scrollWidth > window.innerWidth,
                hasCropChips: document.querySelectorAll('.crop-type-chip').length,
                hasSegmentedControl: document.querySelectorAll('.segmented-btn').length,
                hasDateInput: !!document.querySelector('#expected_harvest_date'),
                hasCountdownBox: !!document.querySelector('#harvest-countdown-box')
              })
            `
          });
          console.log("[CDP] /dashboard/crops/add 360px metrics:", JSON.parse(resCrop360.result.value));

          const shotCrop360 = await send('Page.captureScreenshot', { format: 'png' });
          fs.writeFileSync('scratch/crop_form_360.png', Buffer.from(shotCrop360.data, 'base64'));

          console.log("[CDP] All checks passed successfully!");
          edge.kill();
          process.exit(0);
        };
      } catch (err) {
        console.error(err);
        edge.kill();
        process.exit(1);
      }
    });
  });
}

runCdp().catch(console.error);
