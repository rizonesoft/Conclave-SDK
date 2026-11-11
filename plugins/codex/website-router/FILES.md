# SSH/SFTP setup and use

SSH/SFTP is available in Website Router 0.2.1 on Windows and conclave-srv. It reuses the existing site IDs, seven tools and private tunnel. Credentials are imported once from Conclave, then read only from DPAPI/systemd encryption.

## Add or update

First register the WordPress site using configure.ps1. Store the SSH/SFTP username and password (or private key) in Conclave. Obtain the provider server host-key fingerprint from a trusted prior connection or provider support; a user public-key fingerprint is different. Run:

```powershell
pwsh -File R:\Codex\website-router\scripts\configure-files.ps1 -SiteId '<existing-site-id>' -ItemId '<Conclave-item-id>' -HostKey 'SHA256:<verified-server-fingerprint>'
pwsh -File R:\Codex\website-router\scripts\sync-ubuntu.ps1
codex plugin add website-router@rizonetech --json
```

Defaults target Pressable: sftp.pressable.com and ssh.pressable.com, port 22, discovered SFTP working root and SSH /srv/htdocs. Override SftpHost, SshHost, Port, SftpRoot and SshRoot for another provider. Hosts must currently share the supplied ed25519 pin. Setup probes both transports before replacing encrypted configuration. WordPress credential refresh preserves file settings. No new tunnel or code changes are needed for another compatible site.

## Workflows

Use list_sites, discover_operations and describe_operation, then read_operation. For a file change, prepare_change returns the exact site/environment, path, old hash, proposed content/hash, recovery behavior and expiry. Obtain explicit confirmation, then execute_change once. Keep the backup ID for restoration.

Reads: sftp/list-directory, sftp/stat-file, sftp/read-file, sftp/list-backups, ssh/diagnostics, ssh/php-lint.

Changes: sftp/write-file (UTF-8 or base64 upload, up to 1 MiB), sftp/delete-file, sftp/create-directory, sftp/restore-backup, ssh/flush-cache.

File changes are limited to wp-content. Credential files, traversal, symlinks, recursive deletion and arbitrary shell are blocked. WordPress object-cache flushing does not purge CDN or Pressable page cache. Filesystem fixtures cover changes and recovery; production testing uses reads only.

## Recovery

Backups use AES-256-GCM outside the website, keyed by a secret in the encrypted runtime registry. Keep that key when migrating backup files; generating a fresh key cannot decrypt old backups. Backup retention is manual. Each replacement/deletion records the original site, path and hash; restoring uses a fresh preview and protects any current file first.


## Recovery key in Conclave

The approved recovery item is **Website Router Backup Encryption**, immutable item ID `b6gfwr4xuqa477ovan76qil5uq`. On a new host/account, pass `-BackupKeyItemId 'b6gfwr4xuqa477ovan76qil5uq'` to configure-files.ps1 when importing the first SSH/SFTP connection. The script refuses a key that conflicts with an existing registry. Copy the encrypted `.backup` files into the new private state directory and retain its restrictive permissions. The key stays encrypted in the runtime registry; 1Password is used only for this explicit setup/recovery step.

These file copies complement the host's normal website/database backups. They do not encrypt or replace the live website files and are not a full disaster-recovery system.
