// Check if puppeteer or playwright or selenium is in node_modules or system
const { execSync } = require('child_process');
try {
  console.log('Testing node modules...');
} catch(e) {
  console.error(e);
}
