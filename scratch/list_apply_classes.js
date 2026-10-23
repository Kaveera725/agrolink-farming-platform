const fs = require('fs');
const html = fs.readFileSync('templates/base.html', 'utf8');

// Find all classes used in @apply in base.html
const styleMatch = html.match(/<style type="text\/tailwindcss">([\s\S]*?)<\/style>/);
const css = styleMatch[1];
const applyMatches = css.match(/@apply\s+([^;]+);/g) || [];

const allClasses = new Set();
applyMatches.forEach(m => {
  const line = m.replace(/@apply\s+/, '').replace(';', '').trim();
  line.split(/\s+/).forEach(c => {
    if (c) allClasses.add(c);
  });
});

console.log('Classes to verify:', Array.from(allClasses));
