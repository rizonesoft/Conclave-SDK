# WordPress kit connection setup: plan

Spec: `docs/specs/2026-10-16-wordpress-kit-connect-design.md`.

1. Common helpers in `kits/wordpress/templates/`: `scripts/lib/wp_site.py`, `scripts/lib/site_ssh.py`, `bin/wp-remote`, `scripts/site-access.py`, `scripts/tests/test_site_access.py`. Done when the tests pass from the SDK.
2. Pressable helpers in `kits/wordpress/hosts/pressable/templates/`: `scripts/mcp-headers.py`, `scripts/lib/mcp_http.py`, `scripts/check-mcp.py`, `scripts/sftp-item.py`, `scripts/create-application-password.py`, `bin/ddev`, `bin/wp`, `.ddev/providers/production.yaml`, `mcp.wordpress.example.json`, `scripts/tests/test_mcp_headers.py`, and the pin. Done when the tests pass.
3. WordPress.com pin in `kits/wordpress/hosts/wpcom/templates/.conclave/wordpress-site.json`.
4. `wordpress-connect` skill for `.agents/`, `.claude/` and `.codex/` (plus `agents/openai.yaml`); update `docs/wordpress-agent-tooling.md` and the site-safety skill.
5. Host-aware `install.sh`, `doctor.sh`, `forge.py` (`apply_kit`, `doctor_repo`, CLI `--host`), with `test-install.sh` and `tests/test_forge.py` covering both hosts.
6. READMEs (`kits/wordpress/README.md`, `kits/README.md`).
7. Apply to `~/www/uptime247-coza` with `--host wpcom`, fill the pin for site `257780254`, update its `docs/connections.md`, run the doctor.
