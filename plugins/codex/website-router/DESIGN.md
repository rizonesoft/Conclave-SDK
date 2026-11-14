# Router design

Authoritative source: D:\Conclave-SDK\plugins\codex\website-router. Local catalogue: Rizonetech. Cloud host: conclave-srv. One dedicated outbound OpenAI tunnel serves the router's registered websites. Website additions update the encrypted registry, not the plugin source or tunnel configuration.

## Target and policy boundaries

Each connection has a stable site ID, name, environment, canonical origin and exact MCP endpoint. Tool callers can supply a registered ID, never an endpoint or credential. Same-named production and staging sites are separate targets. Endpoint redirects and private/reserved IPs are blocked; DNS validation is performed by the HTTPS socket lookup. WordPress Application Passwords are sent only to their registered origin/path.

Dynamic discovery exposes site capabilities without automatically expanding execution authority. The checked-in operation policy holds reviewed names, read/change routes and schema/annotation variants. Only matching definitions execute. Read-only declarations alone do not grant execution access. The generic upstream ability executor is never directly exposed. No cross-site read/write fallback exists.

Previews bind the entire connection, operation schema, parameters and environment. A preview returned to the caller is detached from its stored copy. Execution requires a matching site ID, caller-held explicit user authorization, and an unexpired preview. The preview is consumed before validation/network dispatch, preventing uncertain replay. Restart clears previews.

## Credentials and hosting

Conclave is the recovery source. Windows DPAPI CurrentUser and Ubuntu systemd LoadCredentialEncrypted are the normal runtime stores. Import/sync are explicit administration actions; no MCP runtime path invokes 1Password. Ubuntu runs a separate DynamicUser service, encrypted provider registry and encrypted tunnel key. The router does not require Windows to be online for ChatGPT cloud operation.

## SSH and SFTP (0.2.1)

SSH/SFTP share each website identity but use distinct encrypted transport settings: exact hosts, ports, accounts, canonical roots and SHA-256 server host-key pins. DNS is resolved once and only public addresses are passed to SSH2. Agent forwarding and unpinned hosts are not supported. Pressable pins were matched to existing WSL known_hosts and the saved Conclave server host key.

The seven router tools expose eleven additional reviewed operations. File reads and writes are bounded to 1 MiB; listings stop at 10,000 entries and paginate output. Changes are restricted to wp-content. Traversal, protected credential paths and symlink components are rejected. Mutation previews capture remote existence, hash and permissions; these are rechecked before dispatch. Replacements use exclusive private temporary creation outside the web root, checksum verification and the OpenSSH atomic rename extension. Unsupported atomic rename fails closed. No automatic retries.

Before replacement/deletion, save a durable AES-256-GCM backup outside the remote web root. The encryption key is inside the DPAPI/systemd credential registry. Ubuntu uses StateDirectory=rizonetech-website-router (0700); Windows inherits the protected credential-directory ACL. Backups bind their original site/path; restoring is another previewed change. Backups are retained until operator maintenance, not automatically purged.

SSH commands are fixed diagnostics or a confirmed WordPress object-cache flush. PHP lint uses php -n and a quoted relative path. WP-CLI skips plugin/theme loading; host-installed WordPress code remains part of that execution environment. No generic shell, eval, database SQL or arbitrary WP-CLI parameters.

Limits: SFTP offers no server-side compare-and-swap across separate path-check and rename requests. Hash checks catch ordinary concurrent edits but cannot make a hostile filesystem race impossible. Temporary uploads are created exclusively with mode 0600 in /tmp outside the web root. The atomic rename requires the staging directory and target to share a filesystem; failure is not bypassed. No recursive deletion, directory moves, general shell or large-file streaming. File changes are tested using isolated filesystem fixtures; live website checks are read-only.
