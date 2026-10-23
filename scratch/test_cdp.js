const { spawn } = require('child_process');
const http = require('http');

const edge = spawn('C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe', [
  '--headless=new',
  '--remote-debugging-port=9222',
  '--disable-gpu',
  'http://127.0.0.1:5000/auth/login'
]);

setTimeout(() => {
  http.get('http://127.0.0.1:9222/json', (res) => {
    let data = '';
    res.on('data', chunk => data += chunk);
    res.on('end', () => {
      console.log('CDP targets:', data);
      edge.kill();
      process.exit(0);
    });
  }).on('error', (e) => {
    console.error('CDP error:', e.message);
    edge.kill();
    process.exit(1);
  });
}, 2500);
