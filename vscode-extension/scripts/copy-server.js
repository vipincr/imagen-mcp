const fs = require('fs');
const path = require('path');

const workspaceRoot = path.resolve(__dirname, '..', '..');
const extensionRoot = path.resolve(__dirname, '..');
const serverDir = path.join(extensionRoot, 'server');

// Ensure server directory exists
if (!fs.existsSync(serverDir)) {
  fs.mkdirSync(serverDir, { recursive: true });
}

// Copy imagen_mcp package
const srcPackage = path.join(workspaceRoot, 'imagen_mcp');
const destPackage = path.join(serverDir, 'imagen_mcp');

if (!fs.existsSync(srcPackage)) {
  throw new Error(`Source package not found: ${srcPackage}`);
}

// Remove existing copy
if (fs.existsSync(destPackage)) {
  fs.rmSync(destPackage, { recursive: true, force: true });
}

// Copy package, excluding __pycache__ and .pyc files
fs.cpSync(srcPackage, destPackage, {
  recursive: true,
  filter: (entry) => {
    const base = path.basename(entry);
    if (base === '__pycache__') return false;
    if (base.endsWith('.pyc') || base.endsWith('.pyo')) return false;
    return true;
  },
});

console.log(`Copied ${path.relative(workspaceRoot, srcPackage)} -> ${path.relative(workspaceRoot, destPackage)}`);

// Create run_server.py
const runServerPath = path.join(serverDir, 'run_server.py');
const runServerContent = `#!/usr/bin/env python3
"""Startup script for the Imagen MCP Server."""

from imagen_mcp.server import mcp

if __name__ == "__main__":
    # Run with stdio transport (default for MCP) without banner noise
    mcp.run(show_banner=False, log_level="WARNING")
`;

fs.writeFileSync(runServerPath, runServerContent, 'utf8');
console.log(`Created ${path.relative(workspaceRoot, runServerPath)}`);

