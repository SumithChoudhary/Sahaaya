import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';

const root = process.cwd();
const windows = process.platform === 'win32';
const venvPython = resolve(root, windows ? '.venv/Scripts/python.exe' : '.venv/bin/python');
const python = existsSync(venvPython) ? venvPython : (windows ? 'python' : 'python3');

const services = [
  {
    name: 'API',
    command: python,
    args: ['-m', 'uvicorn', 'backend.app.main:app', '--reload', '--host', '127.0.0.1', '--port', '8000'],
  },
  {
    name: 'WEB',
    command: process.execPath,
    args: [resolve(root, 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1'],
  },
];

const children = [];
let stopping = false;

function stopAll(exitCode = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) {
    if (child && child.exitCode === null) child.kill('SIGTERM');
  }
  setTimeout(() => process.exit(exitCode), 300);
}

for (const service of services) {
  const child = spawn(service.command, service.args, {
    cwd: root,
    env: process.env,
    stdio: ['inherit', 'pipe', 'pipe'],
    shell: false,
  });
  children.push(child);

  for (const stream of ['stdout', 'stderr']) {
    child[stream].on('data', (chunk) => {
      for (const line of chunk.toString().split(/(?<=\n)/)) {
        if (line) process[stream].write(`[${service.name}] ${line}`);
      }
    });
  }

  child.on('error', (error) => {
    process.stderr.write(`[${service.name}] Could not start: ${error.message}\n`);
    stopAll(1);
  });
  child.on('exit', (code) => {
    if (!stopping) {
      process.stderr.write(`[${service.name}] stopped${code === 0 ? '' : ` with exit code ${code}`}\n`);
      stopAll(code || 1);
    }
  });
}

process.on('SIGINT', () => stopAll(0));
process.on('SIGTERM', () => stopAll(0));
