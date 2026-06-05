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
          const scriptRegex = /<script>([\s\S]*?)<\/script>/g;
          let match;
          let scriptContent = '';
          let scriptCounter = 0;
          
          while ((match = scriptRegex.exec(content)) !== null) {
            scriptContent += match[1] + '\n';
          }
          
          if (scriptContent) {
            const scriptName = `inline-script-${Date.now()}.js`;
            fs.writeFileSync(path.join(dir, scriptName), scriptContent);
            
            // Replace all inline scripts with a single external script reference
            content = content.replace(scriptRegex, '');
            // Append the external script before </body>
            content = content.replace('</body>', `<script src="./${scriptName}"></script></body>`);
          }
        }

        fs.writeFileSync(filePath, content);
      }
    }
  });
}

replaceInFiles(outDir);
console.log('Successfully prepared out/ directory for Chrome Extension!');
