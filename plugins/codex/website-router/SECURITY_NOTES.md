# Setup incident and follow-up

2026-10-07: an uncaught Node JSON parser error in the initial SSH setup diagnostic printed decrypted Conclave SSH/SFTP inventory into tool output. The user was notified immediately. The affected inventory contained ten site password entries plus the duplicate JMR Group private-key entry; Swiss Hotel School production had empty credential fields. No WordPress application passwords, tunnel key or backup-encryption key were in that inventory.

The diagnostic has been replaced with a runtime-store probe that suppresses parser details. Source and bundle scans check imported credentials without printing them. Rotate the ten SSH/SFTP passwords and retire/replace the exposed duplicate JMR private key, coordinating other applications that use them. Update the Conclave items and encrypted runtime stores after rotation. Rotation was not performed automatically because shared integrations may depend on these credentials.
