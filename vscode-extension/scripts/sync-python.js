const fs = require('fs');
const path = require('path');

const workspaceRoot = path.resolve(__dirname, '..', '..');
const extensionRoot = path.resolve(__dirname, '..');
const packagesToCopy = ['imagen_mcp'];

function copyTree(src, dest) {
  if (!fs.existsSync(src)) {
    throw new Error(`Missing source package: ${src}`);
  }

  fs.rmSync(dest, { recursive: true, force: true });
  fs.mkdirSync(path.dirname(dest), { recursive: true });

  fs.cpSync(src, dest, {
    recursive: true,
    filter: (entry) => {
      const base = path.basename(entry);
      if (base === '__pycache__') return false;
      if (base.endsWith('.pyc') || base.endsWith('.pyo')) return false;
      return true;
    },
  });

  console.log(`Synced ${path.relative(workspaceRoot, src)} -> ${path.relative(workspaceRoot, dest)}`);
}

packagesToCopy.forEach((pkg) => {
  const src = path.join(workspaceRoot, pkg);
  const dest = path.join(extensionRoot, 'server', pkg);
  copyTree(src, dest);
});
