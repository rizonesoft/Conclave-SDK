// Choosing the Python that runs the workspace's dispatcher (design spec section 5).
//
// The setting conclave.pythonPath wins when set, and when it is set but unusable that is the answer: the operator's
// choice is never silently replaced by a discovered Python. Otherwise "py -3" then "python" on Windows, "python3" then
// "python" elsewhere (the Remote WSL host is Linux). Every candidate is resolved to an absolute path from PATH first
// (which.ts) and must report 3.11 or later, the first version with tomllib.

export const MINIMUM: readonly [number, number] = [3, 11];

export interface RunResult {
  // undefined when the process could not start (not found, not executable, timed out).
  code: number | undefined;
  stdout: string;
  // What the process wrote to stderr: the dispatcher's refusals are there.
  stderr?: string;
  error?: string;
  // Processes a cancel or timeout could not end: a caller keeps what they may still use until they have.
  survivors?: number[];
  // True when the process table could not be read to confirm that a cancel or timeout ended every process.
  unverified?: boolean;
}

export interface PythonDeps {
  platform: NodeJS.Platform;
  // False in Restricted Mode, where no process may start (design spec section 5): nothing is found or run.
  trusted: boolean;
  // An absolute path for a bare name, from PATH only, or undefined.
  find: (name: string) => string | undefined;
  // Runs an absolute path with arguments and returns its exit code and output.
  run: (file: string, args: string[]) => Promise<RunResult>;
}

export interface Python {
  ok: true;
  // The absolute executable and the arguments that come before a script: ["-3"] for the Windows launcher.
  command: string;
  prefix: string[];
  version: string;
  // How it was chosen, for the output channel and the status bar: "conclave.pythonPath", "py -3", "python3", "python".
  source: string;
}

export interface Attempt {
  candidate: string;
  reason: string;
}

export interface NoPython {
  ok: false;
  // True when conclave.pythonPath is set and unusable; discovery was not tried.
  fromSetting: boolean;
  // True in Restricted Mode: nothing was tried, and trusting the workspace resolves again.
  untrusted: boolean;
  tried: Attempt[];
  message: string;
}

// -I: isolated mode, so neither the working directory nor PYTHON* variables can put a module in front of the probe.
export const PROBE = ["-I", "-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"];

interface Candidate {
  label: string;
  name: string;
  prefix: string[];
}

function candidates(platform: NodeJS.Platform): Candidate[] {
  return platform === "win32"
    ? [
        { label: "py -3", name: "py", prefix: ["-3"] },
        { label: "python", name: "python", prefix: [] },
      ]
    : [
        { label: "python3", name: "python3", prefix: [] },
        { label: "python", name: "python", prefix: [] },
      ];
}

function isAbsolute(path: string, platform: NodeJS.Platform): boolean {
  return platform === "win32" ? /^[A-Za-z]:[\\/]/.test(path) || /^[\\/]{2}[^\\/]/.test(path) : path.startsWith("/");
}

async function probe(command: string, prefix: string[], deps: PythonDeps): Promise<{ version?: string; reason?: string }> {
  // Node runs a .bat or .cmd only through a shell, which the extension never uses (an argument array, no shell), so a
  // batch shim such as pyenv-win's python.bat is named as the reason instead of failing to start.
  if (deps.platform === "win32" && /\.(bat|cmd)$/i.test(command)) {
    return { reason: `is a batch file (${command}); set conclave.pythonPath to the python.exe it runs` };
  }
  const result = await deps.run(command, [...prefix, ...PROBE]);
  if (result.code === undefined) {
    return { reason: `could not start (${result.error ?? "unknown error"})` };
  }
  if (result.code !== 0) {
    return { reason: `exited ${result.code}` };
  }
  const version = result.stdout.trim();
  const match = /^(\d+)\.(\d+)\.(\d+)$/.exec(version);
  if (!match) {
    return { reason: `printed no version (${JSON.stringify(version.slice(0, 40))})` };
  }
  const [major, minor] = [Number(match[1]), Number(match[2])];
  if (major < MINIMUM[0] || (major === MINIMUM[0] && minor < MINIMUM[1])) {
    return { reason: `is Python ${version}, older than ${MINIMUM.join(".")}` };
  }
  return { version };
}

function refusal(fromSetting: boolean, tried: Attempt[]): NoPython {
  const detail = tried.map((t) => `${t.candidate}: ${t.reason}`).join("; ");
  const message = fromSetting
    ? `conclave.pythonPath is set but cannot be used (${detail}). Fix or clear the setting; discovery is not tried.`
    : `No Python ${MINIMUM.join(".")} or later was found (${detail}). Install one or set conclave.pythonPath.`;
  return { ok: false, fromSetting, untrusted: false, tried, message };
}

export async function resolvePython(setting: string, deps: PythonDeps): Promise<Python | NoPython> {
  if (!deps.trusted) {
    return {
      ok: false, fromSetting: false, untrusted: true, tried: [],
      message: "Restricted Mode: no Python is looked for or run until the workspace is trusted.",
    };
  }
  const configured = setting.trim();
  if (configured !== "") {
    // An absolute path is used as given; a bare name is found on PATH like any other, never in the workspace.
    const command = isAbsolute(configured, deps.platform) ? configured : deps.find(configured);
    if (!command) {
      return refusal(true, [{ candidate: configured, reason: "not found on PATH" }]);
    }
    const { version, reason } = await probe(command, [], deps);
    return version
      ? { ok: true, command, prefix: [], version, source: "conclave.pythonPath" }
      : refusal(true, [{ candidate: configured, reason: reason ?? "unusable" }]);
  }
  const tried: Attempt[] = [];
  for (const candidate of candidates(deps.platform)) {
    const command = deps.find(candidate.name);
    if (!command) {
      tried.push({ candidate: candidate.label, reason: "not found on PATH" });
      continue;
    }
    const { version, reason } = await probe(command, candidate.prefix, deps);
    if (version) {
      return { ok: true, command, prefix: candidate.prefix, version, source: candidate.label };
    }
    tried.push({ candidate: candidate.label, reason: reason ?? "unusable" });
  }
  return refusal(false, tried);
}
