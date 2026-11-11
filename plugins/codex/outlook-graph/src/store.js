import { spawn, execFile } from "node:child_process";
import { promisify } from "node:util";
import { release } from "node:os";
import {
  mkdir,
  readFile,
  writeFile,
  rename,
  unlink,
  rmdir,
  stat,
} from "node:fs/promises";
import { join, dirname, isAbsolute, delimiter } from "node:path";
import { fileURLToPath } from "node:url";
import {
  createCipheriv,
  createDecipheriv,
  randomBytes,
  randomUUID,
} from "node:crypto";
import { GraphError } from "./client.js";
const exec = promisify(execFile);
const delay = (ms) => new Promise((r) => setTimeout(r, ms));
const here = dirname(fileURLToPath(import.meta.url));

export function validateRecord(r) {
  if (
    r?.schemaVersion !== 1 ||
    !r.config ||
    typeof r.cache !== "string" ||
    !r.cache ||
    r.cache.length > 4 * 1024 * 1024
  )
    throw new GraphError("Invalid encrypted session record.");
  const guid =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  if (
    !guid.test(r.config.clientId) ||
    !guid.test(r.config.tenantId) ||
    typeof r.config.mailbox !== "string" ||
    !r.config.mailbox.includes("@") ||
    !r.config.homeAccountId ||
    !r.config.graphUserId
  )
    throw new GraphError("Session configuration is incomplete. Run setup.");
  try {
    JSON.parse(r.cache);
  } catch {
    throw new GraphError("Invalid authentication cache.");
  }
  return r;
}
export async function locked(folder, fn, { timeout = 30000 } = {}) {
  await mkdir(folder, { recursive: true, mode: 0o700 });
  const lock = join(folder, "session.lock");
  const until = Date.now() + timeout;
  for (;;) {
    try {
      await mkdir(lock, { mode: 0o700 });
      break;
    } catch (e) {
      if (e.code !== "EEXIST")
        throw new GraphError("Cannot lock encrypted store.");
      if (Date.now() >= until)
        throw new GraphError(
          "Encrypted store is busy. If setup crashed, verify no process owns it before removing session.lock.",
        );
      await delay(100);
    }
  }
  try {
    return await fn();
  } finally {
    await rmdir(lock);
  }
}

export class WindowsStore {
  constructor({ bridge = false, env = process.env } = {}) {
    this.bridge = bridge;
    this.env = env;
  }
  async run(action, input) {
    let script = join(here, "../scripts/dpapi-store.ps1");
    if (this.bridge)
      script = (
        await exec("wslpath", ["-w", script], { timeout: 5000 })
      ).stdout.trim();
    const executable = this.bridge
      ? "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
      : join(
          this.env.SystemRoot || "C:\\Windows",
          "System32/WindowsPowerShell/v1.0/powershell.exe",
        );
    const env = Object.fromEntries(
      Object.entries(this.env).filter(
        ([k]) => k.toLowerCase() !== "psmodulepath",
      ),
    );
    return await new Promise((resolve, reject) => {
      const child = spawn(
        executable,
        [
          "-NoLogo",
          "-NoProfile",
          "-NonInteractive",
          "-WindowStyle",
          "Hidden",
          "-File",
          script,
          "-Action",
          action,
        ],
        { env, windowsHide: true, stdio: ["pipe", "pipe", "pipe"] },
      );
      let output = "",
        size = 0,
        failed = false;
      const fail = () => {
        failed = true;
        child.kill();
      };
      const timer = setTimeout(fail, 20000);
      child.on("error", () => {
        clearTimeout(timer);
        reject(new GraphError("Windows DPAPI helper unavailable."));
      });
      child.stdout.setEncoding("utf8");
      child.stdout.on("data", (b) => {
        size += Buffer.byteLength(b);
        if (size > 5 * 1024 * 1024) fail();
        else output += b;
      });
      child.stderr.on("data", () => {}); // Helper errors never include credential content in a tool response.
      child.stdin.on("error", () => {});
      child.on("close", (code) => {
        clearTimeout(timer);
        if (code !== 0 || failed)
          return reject(
            new GraphError(
              "Cannot access Windows DPAPI session store. Run setup under the owning Windows account.",
            ),
          );
        try {
          resolve(JSON.parse(output.replace(/^\uFEFF/, "")));
        } catch {
          reject(new GraphError("Invalid credential helper response."));
        }
      });
      child.stdin.end(input === undefined ? "" : JSON.stringify(input));
    });
  }
  async status() {
    return this.run("status");
  }
  async withLock(fn) {
    const s = await this.status();
    const folder = this.bridge
      ? (
          await exec("wslpath", ["-u", s.folder], { timeout: 5000 })
        ).stdout.trim()
      : s.folder;
    return locked(folder, fn);
  }
  async read() {
    const r = await this.run("load");
    return r === null ? null : validateRecord(r);
  }
  async save(record) {
    validateRecord(record);
    await this.run("save", record);
  }
}
export class LinuxStore {
  constructor(env = process.env) {
    this.folder = env.STATE_DIRECTORY;
    this.keyPath =
      env.CREDENTIALS_DIRECTORY && join(env.CREDENTIALS_DIRECTORY, "cache-key");
    if (
      !this.folder ||
      !isAbsolute(this.folder) ||
      this.folder.includes(delimiter) ||
      !this.keyPath
    )
      throw new GraphError(
        "Linux requires systemd encrypted cache-key and private STATE_DIRECTORY. No plaintext fallback.",
      );
  }
  async key() {
    const b = await readFile(this.keyPath);
    if (b.length !== 32) throw new GraphError("Invalid systemd cache key.");
    return b;
  }
  async status() {
    let present = false;
    try {
      await stat(join(this.folder, "session.enc"));
      present = true;
    } catch (e) {
      if (e.code !== "ENOENT")
        throw new GraphError("Cannot inspect encrypted cache.");
    }
    return {
      mode: "systemd-encrypted-key",
      credentialPresent: present,
      onePasswordRuntimeAccess: false,
    };
  }
  withLock(fn) {
    return locked(this.folder, fn);
  }
  async read() {
    let bytes;
    try {
      bytes = await readFile(join(this.folder, "session.enc"));
    } catch (e) {
      if (e.code === "ENOENT") return null;
      throw new GraphError("Cannot read encrypted cache.");
    }
    try {
      const d = createDecipheriv(
        "aes-256-gcm",
        await this.key(),
        bytes.subarray(0, 12),
      );
      d.setAAD(Buffer.from("outlook-graph:1"));
      d.setAuthTag(bytes.subarray(12, 28));
      return validateRecord(
        JSON.parse(
          Buffer.concat([d.update(bytes.subarray(28)), d.final()]).toString(
            "utf8",
          ),
        ),
      );
    } catch {
      throw new GraphError(
        "Encrypted cache authentication failed. Recover by signing in on this host.",
      );
    }
  }
  async save(record) {
    validateRecord(record);
    await mkdir(this.folder, { recursive: true, mode: 0o700 });
    const iv = randomBytes(12);
    const c = createCipheriv("aes-256-gcm", await this.key(), iv);
    c.setAAD(Buffer.from("outlook-graph:1"));
    const body = Buffer.concat([
      c.update(JSON.stringify(record), "utf8"),
      c.final(),
    ]);
    const tmp = join(this.folder, randomUUID() + ".tmp");
    try {
      await writeFile(tmp, Buffer.concat([iv, c.getAuthTag(), body]), {
        mode: 0o600,
        flag: "wx",
      });
      await rename(tmp, join(this.folder, "session.enc"));
    } finally {
      try {
        await unlink(tmp);
      } catch (e) {
        if (e.code !== "ENOENT") throw e;
      }
    }
  }
}
export function createStore(env = process.env, {platform=process.platform,kernelRelease=release()}={}) {
  if (platform === "win32") return new WindowsStore({ env });
  if (env.CREDENTIALS_DIRECTORY) return new LinuxStore(env);
  if (platform === "linux" && (env.WSL_DISTRO_NAME || /microsoft/i.test(kernelRelease))) return new WindowsStore({ bridge: true, env });
  throw new GraphError(
    "Configure systemd encrypted credentials on Linux. No plaintext token store is supported.",
  );
}
