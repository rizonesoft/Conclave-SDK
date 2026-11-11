import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const launcher = fileURLToPath(new URL('../scripts/run-hidden.py', import.meta.url));
const manageCloud = readFileSync(new URL('../scripts/Manage-Cloud.ps1', import.meta.url), 'utf8');
const options = { skip: process.platform !== 'win32' };

const isAlive = (pid) => {
  try { process.kill(pid, 0); return true; } catch { return false; }
};
const waitFor = async (condition, label) => {
  const deadline = Date.now() + 15000;
  while (!condition()) {
    assert.ok(Date.now() < deadline, `timed out waiting for ${label}`);
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
};

test('the scheduled task starts through the windowless launcher', () => {
  const action = manageCloud.split('\n').find((line) => line.includes('New-ScheduledTaskAction'));
  assert.match(action, /-Execute \$pythonw /);
  assert.match(action, /\$launcher/);
  assert.doesNotMatch(action, /-Execute \$pwsh/);
  assert.doesNotMatch(action, /-WindowStyle/);
});

test('the launcher returns the exit code of its command', options, () => {
  const result = spawnSync('pythonw', [launcher, process.execPath, '-e', 'process.exit(7)'], { windowsHide: true, timeout: 15000 });
  assert.equal(result.status, 7);
});

test('the launcher fails when given no command', options, () => {
  const result = spawnSync('pythonw', [launcher], { windowsHide: true, timeout: 15000 });
  assert.equal(result.status, 2);
});

test('the command is inside the job from creation, so a stop at any moment cannot orphan it', options, () => {
  const probe = `
import ctypes, importlib.util, sys
from ctypes import wintypes
spec = importlib.util.spec_from_file_location('run_hidden', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
kernel32 = ctypes.WinDLL('kernel32')
kernel32.IsProcessInJob.argtypes = (wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL))
jobs = []
original_create_job = module.create_job
def create_job():
    jobs.append(original_create_job())
    return jobs[0]
module.create_job = create_job
original_popen = module.subprocess.Popen
def popen(*args, **kwargs):
    child = original_popen(*args, **kwargs)
    inside = wintypes.BOOL()
    assert kernel32.IsProcessInJob(int(child._handle), jobs[0], ctypes.byref(inside))
    print('inside at creation:', bool(inside))
    return child
module.subprocess.Popen = popen
sys.exit(module.main(sys.argv[2:]))
`;
  const result = spawnSync('python', ['-B', '-c', probe, launcher, process.execPath, '-e', 'process.exit(7)'], { encoding: 'utf8', windowsHide: true, timeout: 15000 });
  assert.equal(result.stdout.trim(), 'inside at creation: True', result.stderr);
  assert.equal(result.status, 7, result.stderr);
});

test('terminating the launcher stops its command but not processes the command started', options, async () => {
  const work = mkdtempSync(join(tmpdir(), 'conclave-run-hidden-'));
  const pidFile = join(work, 'pids.json');
  // The command is pwsh starting a process with Process.Start, as Manage-Cloud.ps1 starts the tunnel client.
  // A Node command would not do: libuv kills its own children when it exits, whatever the launcher does.
  const command = `
    $info = [Diagnostics.ProcessStartInfo]::new($env:TEST_NODE)
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.ArgumentList.Add('-e')
    $info.ArgumentList.Add('setTimeout(() => {}, 60000)')
    $daemon = [Diagnostics.Process]::Start($info)
    [IO.File]::WriteAllText($env:TEST_PID_FILE, (@{ command = $PID; daemon = $daemon.Id } | ConvertTo-Json -Compress))
    Start-Sleep -Seconds 60
  `;
  const run = spawn('pythonw', [launcher, 'pwsh', '-NoProfile', '-NonInteractive', '-Command', command], {
    stdio: 'ignore',
    windowsHide: true,
    env: { ...process.env, TEST_NODE: process.execPath, TEST_PID_FILE: pidFile },
  });
  let pids = null;
  try {
    await waitFor(() => existsSync(pidFile) && readFileSync(pidFile, 'utf8').length > 0, 'the command to start');
    pids = JSON.parse(readFileSync(pidFile, 'utf8'));
    assert.ok(isAlive(pids.command));
    run.kill();
    await waitFor(() => !isAlive(pids.command), 'the command to stop');
    assert.ok(isAlive(pids.daemon), 'a process started by the command must survive');
  } finally {
    run.kill();
    for (const pid of [pids?.command, pids?.daemon]) {
      if (pid && isAlive(pid)) process.kill(pid);
    }
    rmSync(work, { recursive: true, force: true });
  }
});
