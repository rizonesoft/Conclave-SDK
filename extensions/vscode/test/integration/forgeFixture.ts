import { join } from "node:path";
import type { ConclaveApi } from "../../src/extension";
import { run } from "../../src/host/run";

// Sets a test folder up with the SDK's own forge.py, run here rather than through the extension, which only ever reads
// (design/decisions.md, read-only kit view). Throws with forge's stderr when it fails.
export async function forgeFixture(api: ConclaveApi, sdk: string, args: string[]): Promise<void> {
  const python = await api.python();
  if (!python.ok) {
    throw new Error(`No usable Python to set up the fixture: ${python.message}`);
  }
  const result = await run(python.command, [...python.prefix, "-I", join(sdk, "forge.py"), ...args], 120_000, sdk);
  if (result.code !== 0) {
    throw new Error(`forge ${args.join(" ")} exited ${result.code ?? result.error}: ${result.stderr}`);
  }
}
