// Finding an executable by name, from the fully qualified directories on PATH only.
//
// On Windows, child_process and CreateProcess look in the working directory before PATH, and the extension runs from
// the workspace folder, so a python.exe committed to a repository would run if the bare name were spawned. The
// extension therefore resolves every executable to an absolute path here and spawns that path. The rules match the
// reviewer kit's find_cli (D01 T01 §5): no relative or drive-relative PATH entry, PATHEXT entries only when shaped like
// an extension, and on Windows the bare name only after every PATHEXT candidate in a directory.

export interface PathEnvironment {
  platform: NodeJS.Platform;
  path: string;
  pathext?: string;
  // True for a file this platform would run: on POSIX it must also be executable, as shutil.which requires, so a
  // non-executable python3 earlier on PATH does not hide a usable one later.
  runnable: (path: string) => boolean;
}

const DEFAULT_PATHEXT = [".COM", ".EXE", ".BAT", ".CMD"];
const EXTENSION = /^\.[A-Za-z0-9]+$/;

// True for a PATH entry that names one place whatever the working directory: on Windows a drive with a root or a UNC
// share, never "\x" (the current drive's) or "C:x" (that drive's current directory).
export function fullyQualified(directory: string, platform: NodeJS.Platform): boolean {
  if (platform !== "win32") {
    return directory.startsWith("/");
  }
  return /^[A-Za-z]:[\\/]/.test(directory) || /^[\\/]{2}[^\\/]/.test(directory);
}

export function findOnPath(name: string, env: PathEnvironment): string | undefined {
  const windows = env.platform === "win32";
  const separator = windows ? ";" : ":";
  // Each platform's own separator: on Linux a backslash is a character of a directory name, not a separator.
  const join = (directory: string, file: string) =>
    windows
      ? directory.endsWith("\\") || directory.endsWith("/") ? directory + file : `${directory}\\${file}`
      : directory.endsWith("/") ? directory + file : `${directory}/${file}`;
  const directories = env.path.split(separator).filter((d) => d !== "" && fullyQualified(d, env.platform));
  const extensions = (env.pathext ?? "").split(";").filter((e) => EXTENSION.test(e));
  for (const directory of directories) {
    const candidates = windows
      ? [...(extensions.length ? extensions : DEFAULT_PATHEXT).map((e) => join(directory, name + e)), join(directory, name)]
      : [join(directory, name)];
    const found = candidates.find((candidate) => env.runnable(candidate));
    if (found) {
      return found;
    }
  }
  return undefined;
}
