const fs = require('fs');
const crypto = require('crypto');
const path = require('path');

const content = fs.readFileSync(path.join(__dirname, 'out/index.html'), 'utf8');
const scriptRegex = /<script(?![^>]*src=)(?![^>]*type="application\/json")[^>]*>([\s\S]*?)<\/script>/g;

let match;
const hashes = [];

while ((match = scriptRegex.exec(content)) !== null) {
  const scriptContent = match[1];
  const hash = crypto.createHash('sha256').update(scriptContent).digest('base64');
  hashes.push(`'sha256-${hash}'`);
  console.log("Found script:\n", scriptContent.substring(0, 100), "...\nHash:", hash, "\n");
}

console.log("CSP Hashes:", hashes.join(" "));
