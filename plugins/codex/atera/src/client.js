import { loadToken } from './credentials.js';

const ORIGIN = 'https://api.atera.com';
const allowed = /^\/api\/v3\/(agents(?:\/(?:[0-9]+|customer\/[0-9]+|machine\/[^/]+|[0-9a-f-]+\/(?:installed|available)-patches))?|alerts(?:\/[0-9]+)?|devices\/(?:snmp|tcp|http|generic)devices?|devices\/(?:snmp|tcp|http|generic)device\/[0-9]+)$/i;
const sensitive = /^(community|authentication|privacy|password|token|secret|credential|windowsserialnumber|officeserialnumber|authorization|apikey|api_key)$/i;

export function sanitize(value, token = '') {
  if (Array.isArray(value)) return value.map(v => sanitize(v, token));
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).filter(([key]) => !sensitive.test(key)).map(([k,v]) => [k, sanitize(v, token)]));
  if (typeof value === 'string') {
    let text = token ? value.split(token).join('[REDACTED]') : value;
    // Monitor URLs may themselves contain credentials or query tokens.
    if (/^https?:\/\//i.test(text)) {
      try { const u = new URL(text); u.username = ''; u.password = ''; u.search = ''; u.hash = ''; text = u.toString(); } catch { return '[invalid URL]'; }
    }
    return text;
  }
  return value;
}

export class AteraClient {
  constructor({ fetchImpl = fetch, tokenProvider = loadToken, sleep = ms => new Promise(r => setTimeout(r, ms)), now = Date.now } = {}) {
    this.fetch = fetchImpl; this.tokenProvider = tokenProvider; this.sleep = sleep; this.now = now;
    this.queue = Promise.resolve(); this.nextRequestAt = 0;
    this.token = null; this.tokenExpiresAt = 0;
  }
  get(path, query = {}) {
    if (!allowed.test(path)) return Promise.reject(new Error('Unsupported Atera endpoint.'));
    const task = this.queue.then(() => this.request(path, query));
    this.queue = task.catch(() => {});
    return task;
  }
  async request(path, query) {
    if (!this.token || this.now() >= this.tokenExpiresAt) {
      this.token = await this.tokenProvider();
      this.tokenExpiresAt = this.now() + 300000;
    }
    const token = this.token;
    const url = new URL(path, ORIGIN);
    for (const [k,v] of Object.entries(query)) if (v !== undefined) url.searchParams.set(k, String(v));
    for (let attempt = 0; attempt < 3; attempt++) {
      const wait = this.nextRequestAt - this.now();
      if (wait > 15000) throw new Error('Atera is rate limited. Retry later; no early retry was sent.');
      if (wait > 0) await this.sleep(wait);
      this.nextRequestAt = this.now() + 250;
      let response;
      try { response = await this.fetch(url, { method: 'GET', redirect: 'error', signal: AbortSignal.timeout(15000), headers: { Authorization: `Bearer ${token}`, Accept: 'application/json', 'Accept-Encoding': 'gzip' } }); }
      catch { throw new Error('Atera request failed or timed out. Check network connectivity and retry.'); }
      if ([429,502,503,504].includes(response.status)) {
        const header = response.headers.get('retry-after');
        let delay = 1000 * 2 ** attempt;
        if (header) {
          const seconds = Number(header);
          const fromHeader = Number.isFinite(seconds) ? seconds * 1000 : Date.parse(header) - this.now();
          if (Number.isFinite(fromHeader)) delay = Math.max(delay, fromHeader, 0);
        }
        await response.body?.cancel();
        this.nextRequestAt = this.now() + delay;
        if (delay > 15000 || attempt === 2) throw new Error(`Atera is temporarily unavailable (HTTP ${response.status}). Retry after at least ${Math.ceil(delay / 1000)} seconds.`);
        continue;
      }
      if (!response.ok) {
        if (response.status === 401) { this.token = null; this.tokenExpiresAt = 0; }
        await response.body?.cancel();
        const messages = {401:'Atera rejected the token. Check the credential and expiration.',403:'Atera denied access. Check token Read permissions and allowed IP addresses.',404:'The requested Atera record was not found.'};
        throw new Error(messages[response.status] || `Atera returned HTTP ${response.status}.`);
      }
      try {
        const reader = response.body.getReader(); const chunks = []; let bytes = 0;
        for (;;) { const {done,value} = await reader.read(); if (done) break; bytes += value.byteLength; if (bytes > 4 * 1024 * 1024) { await reader.cancel(); throw new Error('size'); } chunks.push(value); }
        return sanitize(JSON.parse(Buffer.concat(chunks).toString('utf8')), token);
      } catch { throw new Error('Atera returned an invalid or oversized response. Try a smaller page.'); }
    }
  }
}

export function pageResult(data, requestedPage) {
  if (!data || !Array.isArray(data.items) || !Number.isInteger(data.totalPages) || data.totalPages < 0) throw new Error('Unexpected Atera pagination response.');
  const more = requestedPage < data.totalPages;
  return { items: data.items, page: requestedPage, totalPages: data.totalPages, totalItemCount: data.totalItemCount, nextPage: more ? requestedPage + 1 : null, hasMore: more };
}

export async function scan(client, path, query, maxPages) {
  const items = []; let last; let pagesFetched = 0;
  for (let page = 1; page <= maxPages; page++) {
    last = pageResult(await client.get(path, {...query, page, itemsInPage: 50}), page);
    items.push(...last.items); pagesFetched++;
    if (!last.hasMore) break;
  }
  return { items, pagesFetched, complete: !last.hasMore, nextPage: last.nextPage, totalItemCount: last.totalItemCount };
}
