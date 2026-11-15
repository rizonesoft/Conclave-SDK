# Bosun: the queue for heavy jobs

The global rules for Claude Code and Codex (section 11, "Heavy jobs queue") say to run full builds and full test suites through `bosun run --`. This page says what that means and what to do when Bosun is not there. It summarises Bosun's own README; that README is the source of truth.

## What is Bosun?

Bosun is a separate tool beside Conclave, kept in its own repository (`D:\Bosun` on Windows, `/mnt/d/Bosun` from WSL). Heavy jobs take turns across Windows and WSL through one queue, and a logger records what each repo really uses. No repository depends on Bosun and Bosun writes into no other repository, so nothing here requires it.

## Which commands do I wrap?

Put `bosun run --` in front of heavy commands, on Windows or in WSL:

```text
bosun run -- python forge.py check-all --full
bosun run -- npm test
bosun status
bosun report --days 7
```

Wrap full builds and full test suites. Do not wrap quick commands, and never wrap dev servers or watchers: they would hold a slot for as long as they run. Sessions and editors stay open as normal; only commands wrapped in `bosun run` queue. `bosun status` shows the slots in use and the memory available, and `bosun report --days 7` summarises the memory logs.

## What if `bosun` is not installed?

Run the command normally, without `bosun run --`. Bosun's installer puts it in `%LOCALAPPDATA%\Bosun\bin` on Windows and on the user `PATH`, with a shim for WSL; when `bosun` is not on `PATH`, nothing waits for it.

## How does the queue decide?

- There are 2 slots by default, shared by Windows and WSL.
- The first slot always admits a job. The second needs 6 GB available on Windows, and in WSL also 3 GB available inside the VM.
- After 15 minutes a waiting job starts anyway, with a warning.
- A crashed job frees its slot at once.

## What does exit code 74 mean?

The job wrote more than its budget and was stopped. A job and everything it starts may write at most 100 GB together; over that, it is stopped, children and all, and `bosun run` exits 74 and says why. Look for a test or a child process writing without end. The budget is changed with `--max-write-gb` or `BOSUN_MAX_WRITE_GB`, and 0 turns it off.

In WSL the budget is off until it is turned on once with `sudo ~/.local/share/bosun/enable-write-budget.sh` and then `wsl --shutdown`; until then `bosun run` says so once per boot. Even then it counts writes to the Linux disk only: writes to a Windows drive through `/mnt/c` (or `/mnt/d`, where this checkout is) travel over the host file share and are not counted.

## How do I change a limit, check it, and put it back?

```text
bosun config set slots 3
bosun config get
bosun config unset slots
```

`bosun config set` saves a limit for every job on Windows and in WSL (`slots`, `min_avail_mb`, `max_wait_s`, `min_guest_mb`), `bosun config get` shows each limit and where it came from (`--json` shows the value in effect, its source and what is saved, apart), and `bosun config unset <key>` puts it back to the default. A flag wins over a variable, a variable over the saved file, and the file over the default, so a variable such as `BOSUN_SLOTS` can override a saved value: `config get` shows when it does. The file is `%LOCALAPPDATA%\Bosun\config.json`.

## Where are the logs?

`%LOCALAPPDATA%\Bosun\logs`: one CSV per side per day, sampled every 30 seconds and kept for 14 days. A process is credited to the git repo holding its working directory, otherwise to its parent's repo.

Checked against Bosun's `README.md` at commit `99fd0410083f083164dc332e22bc6067805db5c3`, 2026-11-15.
