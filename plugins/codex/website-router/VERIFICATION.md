# Verification record

2026-10-07:

- 12 Node tests passed: schema compatibility, cross-site routing, argument validation, confirmation/expiry, credential rotation, schema drift, uncertain-write single use, new-site configuration, destination validation and redaction.
- Isolated Windows setup tests passed: encrypted add/remove, preservation of unrelated configuration and failed-input preservation.
- Source/compiled bundle credential scan passed against the imported real credential values without printing them.
- Windows source and installed plugin each exposed seven tools; all ten WordPress sites passed a filtered authenticated site-information read. The installed probe was also run with an inherited preload rejecting 1Password process calls.
- Ubuntu DynamicUser probe used LoadCredentialEncrypted and passed the same ten site reads. Runtime reported systemd-encrypted credentials and no 1Password use.
- No live website changes were executed. Write behavior was tested with controlled fixtures.
- Private tunnel live/ready/control-plane checks passed. ChatGPT account derick@rizonetech.com called connection_status through the private plugin and reported all ten sites connected, systemd-encrypted credentials and runtime1Password false. See CLOUD.md for identities and the verification chat.

Limits: no live destructive/write test, no full host-outage simulation, for the original 0.1.0 baseline. SSH/SFTP extension evidence follows. Adding new provider schema variants needs explicit developer review; adding another connection using existing reviewed variants only needs configuration and encrypted sync.


## SSH/SFTP extension 0.2.1 (2026-10-07)

- 18 Node tests pass, including isolated real file replacement, binary upload, deletion, encrypted backup restoration, stale preview rejection, corruption rejection, uncertain-write consumption, SFTP EOF handling and a real loopback SSH server host-key/authentication test.
- Windows credential-preservation tests pass. Source/bundle scans found no imported credentials; installed-tool discovery also passed with 1Password process access blocked.
- All ten sites passed pinned SSH and SFTP checks from Windows. One Windows WordPress check was transiently unavailable; the subsequent authoritative Ubuntu check passed all thirty transport checks (WordPress, SSH and SFTP for ten sites).
- The deployed service is active, uses StateDirectory=rizonetech-website-router with mode 0700, and its private tunnel passed live/ready/control-plane checks.
- ChatGPT Cloud used the existing connection to discover all eight SFTP operations, describe sftp/write-file, execute ssh/diagnostics (PHP version), and stat wp-content successfully. No cloud writes were prepared or executed.
- Read and PHP lint of the staging wp-content/index.php succeeded. Pressable advertises the OpenSSH atomic-rename extension; the staging host reports /tmp and the website on the same filesystem. Upload staging now uses exclusive mode-0600 files outside the web root; cross-filesystem rename failure remains fail-closed.
- User approved encrypted backups and the recovery key in Conclave. Item: Website Router Backup Encryption (b6gfwr4xuqa477ovan76qil5uq). Credentials and recovery key remain encrypted at runtime; no runtime vault access.
- A setup diagnostic exposed SSH/SFTP inventory in tool output. The parser path was replaced and the user notified. Credential rotation remains outstanding; see SECURITY_NOTES.md.

No production files were modified. Write/recovery tests use isolated local filesystem fixtures, not real websites. Swiss Hotel School production remains unconfigured because its vault credential fields are empty. Existing Codex sessions may need a new chat/app restart to load the refreshed plugin; cloud behavior is already verified. Backup files are not currently replicated between hosts or off-site.
