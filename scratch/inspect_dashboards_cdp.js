const { spawn } = require('child_process');
const http = require('http');
const fs = require('fs');

async function runDashboardCdp() {
  const port = 9240;
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

          async function loginUser(email, password) {
            console.log(`[CDP] Logging in as ${email}...`);
            await send('Page.navigate', { url: 'http://127.0.0.1:5000/auth/login' });
            await new Promise(r => setTimeout(r, 1500));
            await send('Runtime.evaluate', {
              expression: `
                document.querySelector('input[name="email"]').value = '${email}';
                document.querySelector('input[name="password"]').value = '${password}';
                document.querySelector('form').submit();
              `
            });
            await new Promise(r => setTimeout(r, 2000));
          }

          async function checkDashboard(roleName, width, height, isMobile) {
            await send('Emulation.setDeviceMetricsOverride', {
              width: width,
              height: height,
              deviceScaleFactor: 2,
              mobile: isMobile
            });
            await send('Page.navigate', { url: 'http://127.0.0.1:5000/dashboard/' });
            await new Promise(r => setTimeout(r, 2000));

            const res = await send('Runtime.evaluate', {
              expression: `
                JSON.stringify({
                  role: '${roleName}',
                  viewportWidth: window.innerWidth,
                  docScrollWidth: document.documentElement.scrollWidth,
                  hasHorizontalOverflow: document.documentElement.scrollWidth > window.innerWidth,
                  hasH1: !!document.querySelector('h1'),
                  statCardsCount: document.querySelectorAll('.card').length
                })
              `
            });
            const metrics = JSON.parse(res.result.value);
            console.log(`[CDP] ${roleName} @ ${width}px:`, metrics);
            if (metrics.hasHorizontalOverflow) {
              console.error(`HORIZONTAL OVERFLOW DETECTED for ${roleName} at ${width}px!`);
              process.exit(1);
            }
          }

          // 1. Farmer with data (nimal@agrolink.lk)
          await loginUser('nimal@agrolink.lk', 'password123');
          await checkDashboard('Farmer (With Data)', 375, 812, true);
          await checkDashboard('Farmer (With Data)', 1280, 900, false);

          // 2. Farmer empty state (empty_farmer@agrolink.lk)
          await loginUser('empty_farmer@agrolink.lk', 'password123');
          await checkDashboard('Farmer (Empty State)', 375, 812, true);
          await checkDashboard('Farmer (Empty State)', 1280, 900, false);

          // 3. Buyer with data (kamal_buyer@agrolink.lk)
          await loginUser('kamal_buyer@agrolink.lk', 'password123');
          await checkDashboard('Buyer (With Data)', 375, 812, true);
          await checkDashboard('Buyer (With Data)', 1280, 900, false);

          // 4. Buyer empty state (empty_buyer@agrolink.lk)
          await loginUser('empty_buyer@agrolink.lk', 'password123');
          await checkDashboard('Buyer (Empty State)', 375, 812, true);
          await checkDashboard('Buyer (Empty State)', 1280, 900, false);

          console.log("[CDP] All responsive checks at 375px and 1280px passed with ZERO overflow!");
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

runDashboardCdp().catch(console.error);
