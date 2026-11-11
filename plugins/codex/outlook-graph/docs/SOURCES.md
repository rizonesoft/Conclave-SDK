# Official sources checked 13 October 2026

HTML draft update sources checked 23 October 2026:

- [Update an existing draft body with delegated Mail.ReadWrite](https://learn.microsoft.com/en-us/graph/api/message-update?view=graph-rest-1.0)
- [itemBody supports text and HTML](https://learn.microsoft.com/en-us/graph/api/resources/itembody?view=graph-rest-1.0)
- [Read complete attachment inventories](https://learn.microsoft.com/en-us/graph/api/message-list-attachments?view=graph-rest-1.0)
- [File attachment content IDs and inline metadata](https://learn.microsoft.com/en-us/graph/api/resources/fileattachment?view=graph-rest-1.0)
- [OData qualified select paths for derived properties](https://docs.oasis-open.org/odata/odata/v4.0/os/part2-url-conventions/odata-v4.0-os-part2-url-conventions.html#_System_Query_Option_4)
- [parse5 HTML parser and source locations](https://github.com/inikulin/parse5)

- [Graph message resource and identity fields](https://learn.microsoft.com/en-us/graph/api/resources/message?view=graph-rest-1.0)
- [List messages, filters and complete nextLink pagination](https://learn.microsoft.com/en-us/graph/api/user-list-messages?view=graph-rest-1.0)
- [Read message and plain-text body preference](https://learn.microsoft.com/en-us/graph/api/message-get?view=graph-rest-1.0)
- [List child folders](https://learn.microsoft.com/en-us/graph/api/mailfolder-list-childfolders?view=graph-rest-1.0)
- [Read master categories and MailboxSettings.Read](https://learn.microsoft.com/en-us/graph/api/outlookuser-list-mastercategories?view=graph-rest-1.0)
- [Update message categories and draft fields](https://learn.microsoft.com/en-us/graph/api/message-update?view=graph-rest-1.0)
- [Move message and returned replacement resource](https://learn.microsoft.com/en-us/graph/api/message-move?view=graph-rest-1.0)
- [Create new draft](https://learn.microsoft.com/en-us/graph/api/user-post-messages?view=graph-rest-1.0)
- [Create reply draft](https://learn.microsoft.com/en-us/graph/api/message-createreply?view=graph-rest-1.0)
- [Create reply-all draft](https://learn.microsoft.com/en-us/graph/api/message-createreplyall?view=graph-rest-1.0)
- [Translate Exchange IDs](https://learn.microsoft.com/en-us/graph/api/user-translateexchangeids?view=graph-rest-1.0)
- [Throttling and Retry-After](https://learn.microsoft.com/en-us/graph/throttling)
- [MSAL token acquisition](https://learn.microsoft.com/en-us/entra/msal/javascript/node/acquire-token-requests)
- [MSAL cache persistence](https://learn.microsoft.com/en-us/entra/msal/javascript/node/caching)
- [Microsoft app registration](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app)
- [Device-code authentication](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-device-code)
- [OpenAI portable plugin packaging](https://developers.openai.com/plugins/build/plugins)

Provider calls use Graph v1.0 and the signed-in `/me` mailbox only. Delegated scopes permit provider actions beyond the narrow tool surface, so the plugin also restricts its exposed operations. No Graph permission split exists for draft creation versus deletion under Mail.ReadWrite; deletion is excluded from the implementation. Move plus category change is not one Graph transaction.
