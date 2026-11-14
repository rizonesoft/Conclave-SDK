# Connected WordPress websites

Verified on 2026-10-07 from both Windows and **conclave-srv**, using authenticated `core/get-site-info` with only `url` and `name` requested. All ten succeeded. Availability is a point-in-time result; `connection_status` checks again without reading site content.

| Site ID | Website | Environment | WordPress abilities | Verified |
| --- | --- | --- | ---: | --- |
| rizonetech | https://rizonetech.com | Production | 43 | Connected |
| rizonesoft | https://rizonesoft.com | Production | 44 | Connected |
| jmr-group-production | https://jmrgroup.co.za | Production | 9 | Connected |
| vormann-production | https://vormann.co.za | Production | 84 | Connected |
| redfern-shop-production | https://redfernshop.co.za | Production | 73 | Connected |
| rizonesoft-staging | https://rizonesoft-com.mystagingwebsite.com | Staging | 59 | Connected |
| rizonesoft-staging-eu | https://rizonesoft-com-eu.mystagingwebsite.com | Staging EU | 59 | Connected |
| rizonetech-launch | https://rizonetech-com.mystagingwebsite.com | Staging | 55 | Connected |
| rizonetech-launch-eu | https://rizonetech-com-eu.mystagingwebsite.com | Staging EU | 55 | Connected |
| swiss-hotel-school-staging | https://swisshotelschool-co-za.mystagingwebsite.com | Staging | 59 | Connected |

Discovered abilities are not automatically executable: only reviewed matching schemas pass the router policy. See `discover_operations` and `describe_operation` per site.

## Vault entries not connected

These entries lack the required public HTTPS MCP fields and were reported as skipped. Their saved credentials were not repurposed:

- JMR Cape Town WordPress Admin
- JMR Group WordPress Admin (the separate Production MCP entry is connected above)
- JMR Group Local WordPress Admin (DDEV)
- JMR Group Local WordPress DB
- Redfern Shop Local WordPress Admin
- Swiss Hotel School Local WordPress Admin

Novamira entries are excluded because that project was discontinued. Version 0.2.1 imports SSH/SFTP for the same ten sites. Swiss Hotel School production (https://swisshotelschool.co.za) remains unconnected because its Conclave SSH/SFTP username and password fields are empty. The older JMR private-key entry is a duplicate and was not activated. No website content, settings, orders or files were changed during setup and verification.

SSH/SFTP adds 11 router operations to each configured site; those are separate from the WordPress ability counts above.
