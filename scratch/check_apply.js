const fs = require('fs');
const html = fs.readFileSync('templates/base.html', 'utf8');

const styleMatch = html.match(/<style type="text\/tailwindcss">([\s\S]*?)<\/style>/);
if (!styleMatch) {
  console.log('No style match');
  process.exit(1);
}
const css = styleMatch[1];
const applyLines = css.match(/@apply\s+[^;]+;/g) || [];
console.log('Found', applyLines.length, '@apply directives');

// Check for circular @apply or applying custom classes that aren't base tailwind
// For example:
// .btn-secondary { @apply btn-outline ... }
// .card-hover { @apply card ... }
// .btn-soft.btn-sm { @apply btn-sm; }
// .btn-soft.btn-lg { @apply btn-lg; }
// .textarea { @apply input; }
// .map-container-sq { @apply map-container; }
// .btn-danger.btn-sm { @apply btn-sm; }
applyLines.forEach(line => {
  console.log(line);
});
