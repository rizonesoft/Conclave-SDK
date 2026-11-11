# API sources

Retrieved 2026-10-06 from Bunny.net:

- https://bunny.net/docs/api-reference/authentication
- https://bunny.net/docs/api-reference/core/openapi.json (saved as core-openapi.json)
- https://bunny.net/docs/api-reference/storage/openapi.json (saved as storage-openapi.json)
- https://bunny.net/docs/storage/http
- Icon: https://bunny.net/favicon-32x32.png?v=1ca91ab4134c7fdacfd5e433633a1572

Core requests use AccessKey with the account API key. Storage requests use a zone password and the official regional storage host, never the account key. Supported DNS enums and operation verbs come from the schema: record create PUT, update POST, delete DELETE. File PUT sends raw bytes and uppercase SHA-256 checksum.

Observed live: pullzone and storagezone list routes returned arrays, while dnszone returned Items/TotalItems/HasMoreItems. Both formats are handled without assuming array completeness. DNS list pages begin at 1; other documented list pages begin at 0. Tests verify official route contracts, credential redaction, response limits, path safety, retries, preview expiry and concurrency checks without changing production resources.
