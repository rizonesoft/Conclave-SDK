import { PublicClientApplication, LogLevel } from "@azure/msal-node";
import { createStore } from "./store.js";
import { GraphError, GraphClient } from "./client.js";
export const SCOPES = ["User.Read", "Mail.ReadWrite", "MailboxSettings.Read"];
export function application(config) {
  return new PublicClientApplication({
    auth: {
      clientId: config.clientId,
      authority: "https://login.microsoftonline.com/" + config.tenantId,
    },
    system: {
      loggerOptions: {
        piiLoggingEnabled: false,
        logLevel: LogLevel.Error,
        loggerCallback: () => {},
      },
    },
  });
}
export function tokenProvider(
  store = createStore(),
  makeApplication = application,
) {
  return async () =>
    store.withLock(async () => {
      const record = await store.read();
      if (!record)
        throw new GraphError("Not signed in. Run outlook-graph setup login.");
      try {
        const app = makeApplication(record.config),
          cache = app.getTokenCache();
        cache.deserialize(record.cache);
        const account = await cache.getAccountByHomeId(
          record.config.homeAccountId,
        );
        if (!account) throw new Error();
        const response = await app.acquireTokenSilent({
          scopes: SCOPES,
          account,
        });
        if (
          !response?.accessToken ||
          response.account?.homeAccountId !== record.config.homeAccountId
        )
          throw new Error();
        const updated = cache.serialize();
        if (updated !== record.cache)
          await store.save({ ...record, cache: updated });
        return response.accessToken;
      } catch (e) {
        if (e instanceof GraphError) throw e;
        throw new GraphError(
          "Microsoft sign-in needs attention. Run setup login again; no automatic vault access.",
        );
      }
    });
}
export async function login(
  store,
  config,
  onDeviceCode,
  {
    makeApplication = application,
    makeClient = (token) => new GraphClient(token),
  } = {},
) {
  return store.withLock(async () => {
    const old = await store.read();
    const app = makeApplication(config);
    let result;
    try {
      result = await app.acquireTokenByDeviceCode({
        scopes: SCOPES,
        deviceCodeCallback: onDeviceCode,
      });
    } catch {
      throw new GraphError(
        "Microsoft sign-in failed or expired. Existing encrypted session is unchanged.",
      );
    }
    if (!result?.accessToken || !result.account?.homeAccountId)
      throw new GraphError(
        "Microsoft sign-in returned no account. Existing session is unchanged.",
      );
    const client = makeClient(async () => result.accessToken),
      me = await client.me();
    if (
      ![me.mail, me.userPrincipalName].some(
        (a) => a?.toLowerCase() === config.mailbox.toLowerCase(),
      )
    )
      throw new GraphError(
        "Signed-in mailbox does not match setup. Existing session is unchanged.",
      );
    const record = {
      schemaVersion: 1,
      config: {
        ...old?.config,
        ...config,
        homeAccountId: result.account.homeAccountId,
        graphUserId: me.id,
      },
      cache: app.getTokenCache().serialize(),
    };
    await store.save(record);
    return {
      connected: true,
      mailboxMatched: true,
      sendPermissionRequested: false,
    };
  });
}
