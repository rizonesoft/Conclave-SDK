# Private ChatGPT cloud access

Source: R:\Codex\cloud-access. Uses official OpenAI tunnel-client v0.0.15 (release asset SHA-256 3b53133a1e24d43f63088d843860cb1701a4c3ed6390de2e19f69089e443bddc1).

## Current state (2026-10-05)

Production moved to Ubuntu conclave-srv. Both encrypted-credential provider probes and service restarts passed. Windows cloud scheduled task is disabled and tunnel aliases stopped. See [Ubuntu operations](linux/README.md). The Windows PC is no longer required for cloud access.


Both local tunnel runtimes have successfully polled OpenAI and reported healthy/ready. Both private plugins are now registered and connected in ChatGPT under derick@rizonetech.com. Cloud initialization and complete tools/list were verified: Atera 10 tools; Domains.co.za 23 tools. Harmless provider checks also passed locally with 1Password runtime access blocked. A model-driven account call from a ChatGPT conversation remains unverified.

Platform owner: derick@rizonetech.com, Rizonetech (Pty) Ltd.
Requested ChatGPT account: derick@rizonetech.com (corrected by user).
The earlier Gmail registration was rejected. Register under the matching derick@rizonetech.com account; no invitation or broader organization sharing is needed.

- Atera: tunnel_6ac348969d708191a2cb339de0c14070
- Domains.co.za: tunnel_6ac349a7309881918622712dca192ebc
- Current organization: org-VfkunBEjlO1475uR3boR16f5
- Current workspace association: 57d36c1b-3247-428d-b6ac-45bc8bea0511

Cloud plugin URLs: https://chatgpt.com/plugins/plugin_asdk_app_6ac34e005e8c8191885e572655a9cd56 (Atera); https://chatgpt.com/plugins/plugin_asdk_app_6ac34e8bce708191b57d5f4c53b19f41 (Domains.co.za).

## Windows runtime (standby, disabled after Ubuntu migration)

Scheduled task: Rizonetech Plugin Cloud Access. Runs hidden at this Windows user's sign-in using the explicit user SID and Limited privileges. The PC must remain running and the user must be signed in. This is not a pre-login system service.

Start-CloudAccess.ps1 supervises the official managed runtimes every 30 seconds and starts stopped runtimes. It writes only non-secret status; it does not send notifications or replay tool calls. Network reconnection is handled by the official tunnel client. Provider-side write replay across tunnel outages still requires an end-to-end test before being promised.

Secrets are DPAPI CurrentUser encrypted. Normal operation never reads 1Password. Recovery item: Conclave / OpenAI Plugin Cloud Tunnel. No plaintext key is stored in profiles or source.

Packaged Codex redirects LocalAppData to:
C:\Users\DerickPayne\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local
The runner resolves that physical location when the normal LocalAppData path is absent. This avoids a missing-file startup error outside the packaged app. It does not copy credentials. On another PC, configure credentials under its own Windows user.

## Verification and remaining work

- Windows scheduled task must remain Disabled while Ubuntu owns the tunnels.
- Run tunnel-client runtimes status <alias> --json; inspect control-plane last_success in health details.
- Account mismatch resolved: use derick@rizonetech.com. Both registrations completed.
- Cloud tools/list verified. Official icon upload is blocked by the Chrome extension file-URL permission. Cloud skill packaging and a model-driven harmless account call remain follow-up validation.
- Linux service restart passed. Network outage behavior remains to be tested. Tests cover expired or consumed domain-change previews. Never automatically retry provider writes.
- Keep normal ChatGPT/plugin approval policies; no public exposure or paid model API tests.

Official guide: https://developers.openai.com/api/docs/guides/secure-mcp-tunnels

## Bunny.net (2026-10-06)

Bunny.net is installed on Ubuntu and connected to derick@rizonetech.com using tunnel_6ac48be40bf0819186a83bbc42dcd6bb. ChatGPT displays all 18 tools, and Windows/Ubuntu harmless provider probes pass with encrypted credentials. [Cloud plugin](https://chatgpt.com/plugins/plugin_asdk_app_6ac48ced876c8191bdee42d5aaa0d42c). See [setup and limitations](../bunny-net/README.md). The official icon is installed locally; browser file-upload permission currently blocks its cloud upload.

## Conclave (2026-10-06)

Conclave has a dedicated private tunnel, `tunnel_6ac540220efc819195db5fc2880226f3`, serving its existing WSL checkout through the separate **Rizonetech Conclave Cloud Access** Windows task. Unlike the independent API integrations on Ubuntu, this backend requires the Windows PC to remain on and signed in. The retired Windows provider task remains disabled. See [Conclave cloud setup and current verification](../conclave/CLOUD.md).
