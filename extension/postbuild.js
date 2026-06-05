const fs = require('fs');
const path = require('path');

const outDir = path.join(__dirname, 'out');

// 1. Remove unnecessary files starting with _
const filesToRemove = [
  '__next.__PAGE__.txt',
  '__next._full.txt',
  '__next._head.txt',
  '__next._index.txt',
  '__next._tree.txt',
  '_not-found.html',
  '_not-found.txt',
];

filesToRemove.forEach(file => {
  const filePath = path.join(outDir, file);
  if (fs.existsSync(filePath)) {
    fs.unlinkSync(filePath);
  }
});

const notFoundDir = path.join(outDir, '_not-found');
if (fs.existsSync(notFoundDir)) {
  fs.rmSync(notFoundDir, { recursive: true, force: true });
}

// 2. Rename _next to next
const oldNextDir = path.join(outDir, '_next');
const newNextDir = path.join(outDir, 'next');

if (fs.existsSync(oldNextDir)) {
  if (fs.existsSync(newNextDir)) {
    fs.rmSync(newNextDir, { recursive: true, force: true });
  }
  fs.renameSync(oldNextDir, newNextDir);
}

// 3. Find all files and replace /_next/ with /next/
function replaceInFiles(dir) {
  const files = fs.readdirSync(dir);
  
  files.forEach(file => {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);
    
    if (stat.isDirectory()) {
      replaceInFiles(filePath);
    } else {
      const ext = path.extname(file);
      if (['.html', '.js', '.css', '.json'].includes(ext)) {
        let content = fs.readFileSync(filePath, 'utf8');
        
        if (content.includes('/_next/')) {
          content = content.replace(/\/_next\//g, '/next/');
        }

        // Extract inline scripts for Chrome Extension MV3 compatibility
        if (ext === '.html') {
          // Match any script that does NOT have a src attribute and does NOT have type="application/json"
          const scriptRegex = /<script(?![^>]*src=)(?![^>]*type="application\/json")[^>]*>([\s\S]*?)<\/script>/g;
          let match;
          let scriptContent = '';
          let newContent = content;
          
          while ((match = scriptRegex.exec(content)) !== null) {
            scriptContent += match[1] + '\n';
            newContent = newContent.replace(match[0], ''); // safely remove exactly what we matched
          }
          
          if (scriptContent.trim()) {
            const scriptName = `inline-script-${Date.now()}.js`;
            // Place it in the 'next' folder to keep things clean
            const nextDirPath = path.join(outDir, 'next');
            if (!fs.existsSync(nextDirPath)) fs.mkdirSync(nextDirPath, { recursive: true });
            
            fs.writeFileSync(path.join(nextDirPath, scriptName), scriptContent);
            
            // Append the external script before </body>
            newContent = newContent.replace('</body>', `<script src="/next/${scriptName}"></script></body>`);
          }
          
          content = newContent;
        }

        fs.writeFileSync(filePath, content);
      }
    }
  });
}

replaceInFiles(outDir);

// 4. Remove any invalid CSP from manifest.json
const manifestPath = path.join(outDir, 'manifest.json');
if (fs.existsSync(manifestPath)) {
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  
  // MV3 completely forbids sha256 hashes in script-src for extension_pages
  // We rely on the default CSP instead.
  if (manifest.content_security_policy) {
    delete manifest.content_security_policy;
    fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
    console.log('Removed invalid CSP from manifest.json');
  }
}

console.log('Successfully prepared out/ directory for Chrome Extension!');
