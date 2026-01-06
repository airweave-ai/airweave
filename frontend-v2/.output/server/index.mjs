globalThis.__nitro_main__ = import.meta.url;
import nodeHTTP from "node:http";
import { Readable } from "node:stream";
import nodeHTTPS from "node:https";
import nodeHTTP2 from "node:http2";
import { promises } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
function lazyService(loader) {
  let promise, mod;
  return {
    fetch(req) {
      if (mod) {
        return mod.fetch(req);
      }
      if (!promise) {
        promise = loader().then((_mod) => mod = _mod.default || _mod);
      }
      return promise.then((mod2) => mod2.fetch(req));
    }
  };
}
const services = {
  ["ssr"]: lazyService(() => import("./chunks/_/server.mjs"))
};
globalThis.__nitro_vite_envs__ = services;
function lazyInherit$1(target, source, sourceKey) {
  for (const key2 of [...Object.getOwnPropertyNames(source), ...Object.getOwnPropertySymbols(source)]) {
    if (key2 === "constructor") continue;
    const targetDesc = Object.getOwnPropertyDescriptor(target, key2);
    const desc = Object.getOwnPropertyDescriptor(source, key2);
    let modified = false;
    if (desc.get) {
      modified = true;
      desc.get = targetDesc?.get || function() {
        return this[sourceKey][key2];
      };
    }
    if (desc.set) {
      modified = true;
      desc.set = targetDesc?.set || function(value) {
        this[sourceKey][key2] = value;
      };
    }
    if (!targetDesc?.value && typeof desc.value === "function") {
      modified = true;
      desc.value = function(...args) {
        return this[sourceKey][key2](...args);
      };
    }
    if (modified) Object.defineProperty(target, key2, desc);
  }
}
const FastURL$1 = /* @__PURE__ */ (() => {
  const NativeURL = globalThis.URL;
  const FastURL$12 = class URL {
    #url;
    #href;
    #protocol;
    #host;
    #pathname;
    #search;
    #searchParams;
    #pos;
    constructor(url) {
      if (typeof url === "string") this.#href = url;
      else {
        this.#protocol = url.protocol;
        this.#host = url.host;
        this.#pathname = url.pathname;
        this.#search = url.search;
      }
    }
    static [Symbol.hasInstance](val) {
      return val instanceof NativeURL;
    }
    get _url() {
      if (this.#url) return this.#url;
      this.#url = new NativeURL(this.href);
      this.#href = void 0;
      this.#protocol = void 0;
      this.#host = void 0;
      this.#pathname = void 0;
      this.#search = void 0;
      this.#searchParams = void 0;
      this.#pos = void 0;
      return this.#url;
    }
    get href() {
      if (this.#url) return this.#url.href;
      if (!this.#href) this.#href = `${this.#protocol || "http:"}//${this.#host || "localhost"}${this.#pathname || "/"}${this.#search || ""}`;
      return this.#href;
    }
    #getPos() {
      if (!this.#pos) {
        const url = this.href;
        const protoIndex = url.indexOf("://");
        const pathnameIndex = protoIndex === -1 ? -1 : url.indexOf("/", protoIndex + 4);
        this.#pos = [
          protoIndex,
          pathnameIndex,
          pathnameIndex === -1 ? -1 : url.indexOf("?", pathnameIndex)
        ];
      }
      return this.#pos;
    }
    get pathname() {
      if (this.#url) return this.#url.pathname;
      if (this.#pathname === void 0) {
        const [, pathnameIndex, queryIndex] = this.#getPos();
        if (pathnameIndex === -1) return this._url.pathname;
        this.#pathname = this.href.slice(pathnameIndex, queryIndex === -1 ? void 0 : queryIndex);
      }
      return this.#pathname;
    }
    get search() {
      if (this.#url) return this.#url.search;
      if (this.#search === void 0) {
        const [, pathnameIndex, queryIndex] = this.#getPos();
        if (pathnameIndex === -1) return this._url.search;
        const url = this.href;
        this.#search = queryIndex === -1 || queryIndex === url.length - 1 ? "" : url.slice(queryIndex);
      }
      return this.#search;
    }
    get searchParams() {
      if (this.#url) return this.#url.searchParams;
      if (!this.#searchParams) this.#searchParams = new URLSearchParams(this.search);
      return this.#searchParams;
    }
    get protocol() {
      if (this.#url) return this.#url.protocol;
      if (this.#protocol === void 0) {
        const [protocolIndex] = this.#getPos();
        if (protocolIndex === -1) return this._url.protocol;
        this.#protocol = this.href.slice(0, protocolIndex + 1);
      }
      return this.#protocol;
    }
    toString() {
      return this.href;
    }
    toJSON() {
      return this.href;
    }
  };
  lazyInherit$1(FastURL$12.prototype, NativeURL.prototype, "_url");
  Object.setPrototypeOf(FastURL$12.prototype, NativeURL.prototype);
  Object.setPrototypeOf(FastURL$12, NativeURL);
  return FastURL$12;
})();
function resolvePortAndHost(opts) {
  const _port = opts.port ?? globalThis.process?.env.PORT ?? 3e3;
  const port2 = typeof _port === "number" ? _port : Number.parseInt(_port, 10);
  if (port2 < 0 || port2 > 65535) throw new RangeError(`Port must be between 0 and 65535 (got "${port2}").`);
  return {
    port: port2,
    hostname: opts.hostname ?? globalThis.process?.env.HOST
  };
}
function fmtURL(host2, port2, secure) {
  if (!host2 || !port2) return;
  if (host2.includes(":")) host2 = `[${host2}]`;
  return `http${secure ? "s" : ""}://${host2}:${port2}/`;
}
function printListening(opts, url) {
  if (!url || (opts.silent ?? globalThis.process?.env?.TEST)) return;
  const _url = new URL(url);
  const allInterfaces = _url.hostname === "[::]" || _url.hostname === "0.0.0.0";
  if (allInterfaces) {
    _url.hostname = "localhost";
    url = _url.href;
  }
  let listeningOn = `➜ Listening on:`;
  let additionalInfo = allInterfaces ? " (all interfaces)" : "";
  if (globalThis.process.stdout?.isTTY) {
    listeningOn = `\x1B[32m${listeningOn}\x1B[0m`;
    url = `\x1B[36m${url}\x1B[0m`;
    additionalInfo = `\x1B[2m${additionalInfo}\x1B[0m`;
  }
  console.log(`${listeningOn} ${url}${additionalInfo}`);
}
function resolveTLSOptions(opts) {
  if (!opts.tls || opts.protocol === "http") return;
  const cert2 = resolveCertOrKey(opts.tls.cert);
  const key2 = resolveCertOrKey(opts.tls.key);
  if (!cert2 && !key2) {
    if (opts.protocol === "https") throw new TypeError("TLS `cert` and `key` must be provided for `https` protocol.");
    return;
  }
  if (!cert2 || !key2) throw new TypeError("TLS `cert` and `key` must be provided together.");
  return {
    cert: cert2,
    key: key2,
    passphrase: opts.tls.passphrase
  };
}
function resolveCertOrKey(value) {
  if (!value) return;
  if (typeof value !== "string") throw new TypeError("TLS certificate and key must be strings in PEM format or file paths.");
  if (value.startsWith("-----BEGIN ")) return value;
  const { readFileSync } = process.getBuiltinModule("node:fs");
  return readFileSync(value, "utf8");
}
function createWaitUntil() {
  const promises2 = /* @__PURE__ */ new Set();
  return {
    waitUntil: (promise) => {
      if (typeof promise?.then !== "function") return;
      promises2.add(Promise.resolve(promise).catch(console.error).finally(() => {
        promises2.delete(promise);
      }));
    },
    wait: () => {
      return Promise.all(promises2);
    }
  };
}
const noColor = /* @__PURE__ */ (() => {
  const env = globalThis.process?.env ?? {};
  return env.NO_COLOR === "1" || env.TERM === "dumb";
})();
const _c = (c, r = 39) => (t) => noColor ? t : `\x1B[${c}m${t}\x1B[${r}m`;
const red = /* @__PURE__ */ _c(31);
const gray = /* @__PURE__ */ _c(90);
function wrapFetch(server) {
  const fetchHandler = server.options.fetch;
  const middleware = server.options.middleware || [];
  return middleware.length === 0 ? fetchHandler : (request) => callMiddleware$1(request, fetchHandler, middleware, 0);
}
function callMiddleware$1(request, fetchHandler, middleware, index) {
  if (index === middleware.length) return fetchHandler(request);
  return middleware[index](request, () => callMiddleware$1(request, fetchHandler, middleware, index + 1));
}
const errorPlugin = (server) => {
  const errorHandler2 = server.options.error;
  if (!errorHandler2) return;
  server.options.middleware.unshift((_req, next) => {
    try {
      const res = next();
      return res instanceof Promise ? res.catch((error) => errorHandler2(error)) : res;
    } catch (error) {
      return errorHandler2(error);
    }
  });
};
const gracefulShutdownPlugin = (server) => {
  const config = server.options?.gracefulShutdown;
  if (!globalThis.process?.on || config === false || config === void 0 && (process.env.CI || process.env.TEST)) return;
  const gracefulShutdown = config === true || !config?.gracefulTimeout ? Number.parseInt(process.env.SERVER_SHUTDOWN_TIMEOUT || "") || 3 : config.gracefulTimeout;
  const forceShutdown = config === true || !config?.forceTimeout ? Number.parseInt(process.env.SERVER_FORCE_SHUTDOWN_TIMEOUT || "") || 5 : config.forceTimeout;
  let isShuttingDown = false;
  const shutdown = async () => {
    if (isShuttingDown) return;
    isShuttingDown = true;
    const w = process.stderr.write.bind(process.stderr);
    w(gray(`
Shutting down server in ${gracefulShutdown}s...`));
    let timeout;
    await Promise.race([server.close().finally(() => {
      clearTimeout(timeout);
      w(gray(" Server closed.\n"));
    }), new Promise((resolve2) => {
      timeout = setTimeout(() => {
        w(gray(`
Force closing connections in ${forceShutdown}s...`));
        timeout = setTimeout(() => {
          w(red("\nCould not close connections in time, force exiting."));
          resolve2();
        }, forceShutdown * 1e3);
        return server.close(true);
      }, gracefulShutdown * 1e3);
    })]);
    globalThis.process.exit(0);
  };
  for (const sig of ["SIGINT", "SIGTERM"]) globalThis.process.on(sig, shutdown);
};
const NodeResponse$1 = /* @__PURE__ */ (() => {
  const NativeResponse = globalThis.Response;
  const STATUS_CODES = globalThis.process?.getBuiltinModule?.("node:http")?.STATUS_CODES || {};
  class NodeResponse$12 {
    #body;
    #init;
    #headers;
    #response;
    constructor(body, init) {
      this.#body = body;
      this.#init = init;
    }
    static [Symbol.hasInstance](val) {
      return val instanceof NativeResponse;
    }
    get status() {
      return this.#response?.status || this.#init?.status || 200;
    }
    get statusText() {
      return this.#response?.statusText || this.#init?.statusText || STATUS_CODES[this.status] || "";
    }
    get headers() {
      if (this.#response) return this.#response.headers;
      if (this.#headers) return this.#headers;
      const initHeaders = this.#init?.headers;
      return this.#headers = initHeaders instanceof Headers ? initHeaders : new Headers(initHeaders);
    }
    get ok() {
      if (this.#response) return this.#response.ok;
      const status = this.status;
      return status >= 200 && status < 300;
    }
    get _response() {
      if (this.#response) return this.#response;
      this.#response = new NativeResponse(this.#body, this.#headers ? {
        ...this.#init,
        headers: this.#headers
      } : this.#init);
      this.#init = void 0;
      this.#headers = void 0;
      this.#body = void 0;
      return this.#response;
    }
    _toNodeResponse() {
      const status = this.status;
      const statusText = this.statusText;
      let body;
      let contentType;
      let contentLength;
      if (this.#response) body = this.#response.body;
      else if (this.#body) if (this.#body instanceof ReadableStream) body = this.#body;
      else if (typeof this.#body === "string") {
        body = this.#body;
        contentType = "text/plain; charset=UTF-8";
        contentLength = Buffer.byteLength(this.#body);
      } else if (this.#body instanceof ArrayBuffer) {
        body = Buffer.from(this.#body);
        contentLength = this.#body.byteLength;
      } else if (this.#body instanceof Uint8Array) {
        body = this.#body;
        contentLength = this.#body.byteLength;
      } else if (this.#body instanceof DataView) {
        body = Buffer.from(this.#body.buffer);
        contentLength = this.#body.byteLength;
      } else if (this.#body instanceof Blob) {
        body = this.#body.stream();
        contentType = this.#body.type;
        contentLength = this.#body.size;
      } else if (typeof this.#body.pipe === "function") body = this.#body;
      else body = this._response.body;
      const headers2 = [];
      const initHeaders = this.#init?.headers;
      const headerEntries = this.#response?.headers || this.#headers || (initHeaders ? Array.isArray(initHeaders) ? initHeaders : initHeaders?.entries ? initHeaders.entries() : Object.entries(initHeaders).map(([k, v]) => [k.toLowerCase(), v]) : void 0);
      let hasContentTypeHeader;
      let hasContentLength;
      if (headerEntries) for (const [key2, value] of headerEntries) {
        if (Array.isArray(value)) for (const v of value) headers2.push([key2, v]);
        else headers2.push([key2, value]);
        if (key2 === "content-type") hasContentTypeHeader = true;
        else if (key2 === "content-length") hasContentLength = true;
      }
      if (contentType && !hasContentTypeHeader) headers2.push(["content-type", contentType]);
      if (contentLength && !hasContentLength) headers2.push(["content-length", String(contentLength)]);
      this.#init = void 0;
      this.#headers = void 0;
      this.#response = void 0;
      this.#body = void 0;
      return {
        status,
        statusText,
        headers: headers2,
        body
      };
    }
  }
  lazyInherit$1(NodeResponse$12.prototype, NativeResponse.prototype, "_response");
  Object.setPrototypeOf(NodeResponse$12, NativeResponse);
  Object.setPrototypeOf(NodeResponse$12.prototype, NativeResponse.prototype);
  return NodeResponse$12;
})();
async function sendNodeResponse(nodeRes, webRes) {
  if (!webRes) {
    nodeRes.statusCode = 500;
    return endNodeResponse(nodeRes);
  }
  if (webRes._toNodeResponse) {
    const res = webRes._toNodeResponse();
    writeHead(nodeRes, res.status, res.statusText, res.headers);
    if (res.body) {
      if (res.body instanceof ReadableStream) return streamBody(res.body, nodeRes);
      else if (typeof res.body?.pipe === "function") {
        res.body.pipe(nodeRes);
        return new Promise((resolve2) => nodeRes.on("close", resolve2));
      }
      nodeRes.write(res.body);
    }
    return endNodeResponse(nodeRes);
  }
  const rawHeaders = [...webRes.headers];
  writeHead(nodeRes, webRes.status, webRes.statusText, rawHeaders);
  return webRes.body ? streamBody(webRes.body, nodeRes) : endNodeResponse(nodeRes);
}
function writeHead(nodeRes, status, statusText, rawHeaders) {
  const writeHeaders = globalThis.Deno ? rawHeaders : rawHeaders.flat();
  if (!nodeRes.headersSent) if (nodeRes.req?.httpVersion === "2.0") nodeRes.writeHead(status, writeHeaders);
  else nodeRes.writeHead(status, statusText, writeHeaders);
}
function endNodeResponse(nodeRes) {
  return new Promise((resolve2) => nodeRes.end(resolve2));
}
function streamBody(stream, nodeRes) {
  if (nodeRes.destroyed) {
    stream.cancel();
    return;
  }
  const reader = stream.getReader();
  function streamCancel(error) {
    reader.cancel(error).catch(() => {
    });
    if (error) nodeRes.destroy(error);
  }
  function streamHandle({ done, value }) {
    try {
      if (done) nodeRes.end();
      else if (nodeRes.write(value)) reader.read().then(streamHandle, streamCancel);
      else nodeRes.once("drain", () => reader.read().then(streamHandle, streamCancel));
    } catch (error) {
      streamCancel(error instanceof Error ? error : void 0);
    }
  }
  nodeRes.on("close", streamCancel);
  nodeRes.on("error", streamCancel);
  reader.read().then(streamHandle, streamCancel);
  return reader.closed.catch(streamCancel).finally(() => {
    nodeRes.off("close", streamCancel);
    nodeRes.off("error", streamCancel);
  });
}
var NodeRequestURL = class extends FastURL$1 {
  #req;
  constructor({ req }) {
    const path = req.url || "/";
    if (path[0] === "/") {
      const qIndex = path.indexOf("?");
      const pathname = qIndex === -1 ? path : path?.slice(0, qIndex) || "/";
      const search = qIndex === -1 ? "" : path?.slice(qIndex) || "";
      const host2 = req.headers.host || req.headers[":authority"] || `${req.socket.localFamily === "IPv6" ? "[" + req.socket.localAddress + "]" : req.socket.localAddress}:${req.socket?.localPort || "80"}`;
      const protocol = req.socket?.encrypted || req.headers["x-forwarded-proto"] === "https" || req.headers[":scheme"] === "https" ? "https:" : "http:";
      super({
        protocol,
        host: host2,
        pathname,
        search
      });
    } else super(path);
    this.#req = req;
  }
  get pathname() {
    return super.pathname;
  }
  set pathname(value) {
    this._url.pathname = value;
    this.#req.url = this._url.pathname + this._url.search;
  }
};
const NodeRequestHeaders = /* @__PURE__ */ (() => {
  const NativeHeaders = globalThis.Headers;
  class Headers2 {
    #req;
    #headers;
    constructor(req) {
      this.#req = req;
    }
    static [Symbol.hasInstance](val) {
      return val instanceof NativeHeaders;
    }
    get _headers() {
      if (!this.#headers) {
        const headers2 = new NativeHeaders();
        const rawHeaders = this.#req.rawHeaders;
        const len = rawHeaders.length;
        for (let i = 0; i < len; i += 2) {
          const key2 = rawHeaders[i];
          if (key2.charCodeAt(0) === 58) continue;
          const value = rawHeaders[i + 1];
          headers2.append(key2, value);
        }
        this.#headers = headers2;
      }
      return this.#headers;
    }
    get(name) {
      if (this.#headers) return this.#headers.get(name);
      const value = this.#req.headers[name.toLowerCase()];
      return Array.isArray(value) ? value.join(", ") : value || null;
    }
    has(name) {
      if (this.#headers) return this.#headers.has(name);
      return name.toLowerCase() in this.#req.headers;
    }
    getSetCookie() {
      if (this.#headers) return this.#headers.getSetCookie();
      const value = this.#req.headers["set-cookie"];
      return Array.isArray(value) ? value : value ? [value] : [];
    }
    *_entries() {
      const rawHeaders = this.#req.rawHeaders;
      const len = rawHeaders.length;
      for (let i = 0; i < len; i += 2) {
        const key2 = rawHeaders[i];
        if (key2.charCodeAt(0) === 58) continue;
        yield [key2.toLowerCase(), rawHeaders[i + 1]];
      }
    }
    entries() {
      return this.#headers ? this.#headers.entries() : this._entries();
    }
    [Symbol.iterator]() {
      return this.entries();
    }
  }
  lazyInherit$1(Headers2.prototype, NativeHeaders.prototype, "_headers");
  Object.setPrototypeOf(Headers2, NativeHeaders);
  Object.setPrototypeOf(Headers2.prototype, NativeHeaders.prototype);
  return Headers2;
})();
const NodeRequest = /* @__PURE__ */ (() => {
  const NativeRequest = globalThis[/* @__PURE__ */ Symbol.for("srvx.nativeRequest")] ??= globalThis.Request;
  const PatchedRequest = class Request$1 extends NativeRequest {
    static _srvx = true;
    static [Symbol.hasInstance](instance) {
      if (this === PatchedRequest) return instance instanceof NativeRequest;
      else return Object.prototype.isPrototypeOf.call(this.prototype, instance);
    }
    constructor(input, options) {
      if (typeof input === "object" && "_request" in input) input = input._request;
      if (options?.body?.getReader !== void 0) options.duplex ??= "half";
      super(input, options);
    }
  };
  if (!globalThis.Request._srvx) globalThis.Request = PatchedRequest;
  class Request2 {
    runtime;
    #req;
    #url;
    #bodyStream;
    #request;
    #headers;
    #abortController;
    constructor(ctx) {
      this.#req = ctx.req;
      this.runtime = {
        name: "node",
        node: ctx
      };
    }
    static [Symbol.hasInstance](val) {
      return val instanceof NativeRequest;
    }
    get ip() {
      return this.#req.socket?.remoteAddress;
    }
    get method() {
      if (this.#request) return this.#request.method;
      return this.#req.method || "GET";
    }
    get _url() {
      return this.#url ||= new NodeRequestURL({ req: this.#req });
    }
    set _url(url) {
      this.#url = url;
    }
    get url() {
      if (this.#request) return this.#request.url;
      return this._url.href;
    }
    get headers() {
      if (this.#request) return this.#request.headers;
      return this.#headers ||= new NodeRequestHeaders(this.#req);
    }
    get _abortController() {
      if (!this.#abortController) {
        this.#abortController = new AbortController();
        const { req, res } = this.runtime.node;
        const abortController = this.#abortController;
        const abort = (err) => abortController.abort?.(err);
        req.once("error", abort);
        if (res) res.once("close", () => {
          const reqError = req.errored;
          if (reqError) abort(reqError);
          else if (!res.writableEnded) abort();
        });
        else req.once("close", () => {
          if (!req.complete) abort();
        });
      }
      return this.#abortController;
    }
    get signal() {
      return this.#request ? this.#request.signal : this._abortController.signal;
    }
    get body() {
      if (this.#request) return this.#request.body;
      if (this.#bodyStream === void 0) {
        const method = this.method;
        this.#bodyStream = !(method === "GET" || method === "HEAD") ? Readable.toWeb(this.#req) : null;
      }
      return this.#bodyStream;
    }
    text() {
      if (this.#request) return this.#request.text();
      if (this.#bodyStream !== void 0) return this.#bodyStream ? new Response(this.#bodyStream).text() : Promise.resolve("");
      return readBody(this.#req).then((buf) => buf.toString());
    }
    json() {
      if (this.#request) return this.#request.json();
      return this.text().then((text) => JSON.parse(text));
    }
    get _request() {
      if (!this.#request) {
        this.#request = new PatchedRequest(this.url, {
          method: this.method,
          headers: this.headers,
          body: this.body,
          signal: this._abortController.signal
        });
        this.#headers = void 0;
        this.#bodyStream = void 0;
      }
      return this.#request;
    }
  }
  lazyInherit$1(Request2.prototype, NativeRequest.prototype, "_request");
  Object.setPrototypeOf(Request2.prototype, NativeRequest.prototype);
  return Request2;
})();
function readBody(req) {
  return new Promise((resolve2, reject) => {
    const chunks = [];
    const onData = (chunk) => {
      chunks.push(chunk);
    };
    const onError = (err) => {
      reject(err);
    };
    const onEnd = () => {
      req.off("error", onError);
      req.off("data", onData);
      resolve2(Buffer.concat(chunks));
    };
    req.on("data", onData).once("end", onEnd).once("error", onError);
  });
}
function serve(options) {
  return new NodeServer(options);
}
var NodeServer = class {
  runtime = "node";
  options;
  node;
  serveOptions;
  fetch;
  #isSecure;
  #listeningPromise;
  #wait;
  constructor(options) {
    this.options = {
      ...options,
      middleware: [...options.middleware || []]
    };
    for (const plugin of options.plugins || []) plugin(this);
    errorPlugin(this);
    gracefulShutdownPlugin(this);
    const fetchHandler = this.fetch = wrapFetch(this);
    this.#wait = createWaitUntil();
    const handler = (nodeReq, nodeRes) => {
      const request = new NodeRequest({
        req: nodeReq,
        res: nodeRes
      });
      request.waitUntil = this.#wait.waitUntil;
      const res = fetchHandler(request);
      return res instanceof Promise ? res.then((resolvedRes) => sendNodeResponse(nodeRes, resolvedRes)) : sendNodeResponse(nodeRes, res);
    };
    const tls = resolveTLSOptions(this.options);
    const { port: port2, hostname: host2 } = resolvePortAndHost(this.options);
    this.serveOptions = {
      port: port2,
      host: host2,
      exclusive: !this.options.reusePort,
      ...tls ? {
        cert: tls.cert,
        key: tls.key,
        passphrase: tls.passphrase
      } : {},
      ...this.options.node
    };
    let server;
    this.#isSecure = !!this.serveOptions.cert && this.options.protocol !== "http";
    if (this.options.node?.http2 ?? this.#isSecure) if (this.#isSecure) server = nodeHTTP2.createSecureServer({
      allowHTTP1: true,
      ...this.serveOptions
    }, handler);
    else throw new Error("node.http2 option requires tls certificate!");
    else if (this.#isSecure) server = nodeHTTPS.createServer(this.serveOptions, handler);
    else server = nodeHTTP.createServer(this.serveOptions, handler);
    this.node = {
      server,
      handler
    };
    if (!options.manual) this.serve();
  }
  serve() {
    if (this.#listeningPromise) return Promise.resolve(this.#listeningPromise).then(() => this);
    this.#listeningPromise = new Promise((resolve2) => {
      this.node.server.listen(this.serveOptions, () => {
        printListening(this.options, this.url);
        resolve2();
      });
    });
  }
  get url() {
    const addr = this.node?.server?.address();
    if (!addr) return;
    return typeof addr === "string" ? addr : fmtURL(addr.address, addr.port, this.#isSecure);
  }
  ready() {
    return Promise.resolve(this.#listeningPromise).then(() => this);
  }
  async close(closeAll) {
    await Promise.all([this.#wait.wait(), new Promise((resolve2, reject) => {
      const server = this.node?.server;
      if (!server) return resolve2();
      if (closeAll && "closeAllConnections" in server) server.closeAllConnections();
      server.close((error) => error ? reject(error) : resolve2());
    })]);
  }
};
const NullProtoObj = /* @__PURE__ */ (() => {
  const e = function() {
  };
  return e.prototype = /* @__PURE__ */ Object.create(null), Object.freeze(e.prototype), e;
})();
function lazyInherit(target, source, sourceKey) {
  for (const key2 of [...Object.getOwnPropertyNames(source), ...Object.getOwnPropertySymbols(source)]) {
    if (key2 === "constructor") continue;
    const targetDesc = Object.getOwnPropertyDescriptor(target, key2);
    const desc = Object.getOwnPropertyDescriptor(source, key2);
    let modified = false;
    if (desc.get) {
      modified = true;
      desc.get = targetDesc?.get || function() {
        return this[sourceKey][key2];
      };
    }
    if (desc.set) {
      modified = true;
      desc.set = targetDesc?.set || function(value) {
        this[sourceKey][key2] = value;
      };
    }
    if (!targetDesc?.value && typeof desc.value === "function") {
      modified = true;
      desc.value = function(...args) {
        return this[sourceKey][key2](...args);
      };
    }
    if (modified) Object.defineProperty(target, key2, desc);
  }
}
const FastURL = /* @__PURE__ */ (() => {
  const NativeURL = globalThis.URL;
  const FastURL$12 = class URL {
    #url;
    #href;
    #protocol;
    #host;
    #pathname;
    #search;
    #searchParams;
    #pos;
    constructor(url) {
      if (typeof url === "string") this.#href = url;
      else {
        this.#protocol = url.protocol;
        this.#host = url.host;
        this.#pathname = url.pathname;
        this.#search = url.search;
      }
    }
    static [Symbol.hasInstance](val) {
      return val instanceof NativeURL;
    }
    get _url() {
      if (this.#url) return this.#url;
      this.#url = new NativeURL(this.href);
      this.#href = void 0;
      this.#protocol = void 0;
      this.#host = void 0;
      this.#pathname = void 0;
      this.#search = void 0;
      this.#searchParams = void 0;
      this.#pos = void 0;
      return this.#url;
    }
    get href() {
      if (this.#url) return this.#url.href;
      if (!this.#href) this.#href = `${this.#protocol || "http:"}//${this.#host || "localhost"}${this.#pathname || "/"}${this.#search || ""}`;
      return this.#href;
    }
    #getPos() {
      if (!this.#pos) {
        const url = this.href;
        const protoIndex = url.indexOf("://");
        const pathnameIndex = protoIndex === -1 ? -1 : url.indexOf("/", protoIndex + 4);
        this.#pos = [
          protoIndex,
          pathnameIndex,
          pathnameIndex === -1 ? -1 : url.indexOf("?", pathnameIndex)
        ];
      }
      return this.#pos;
    }
    get pathname() {
      if (this.#url) return this.#url.pathname;
      if (this.#pathname === void 0) {
        const [, pathnameIndex, queryIndex] = this.#getPos();
        if (pathnameIndex === -1) return this._url.pathname;
        this.#pathname = this.href.slice(pathnameIndex, queryIndex === -1 ? void 0 : queryIndex);
      }
      return this.#pathname;
    }
    get search() {
      if (this.#url) return this.#url.search;
      if (this.#search === void 0) {
        const [, pathnameIndex, queryIndex] = this.#getPos();
        if (pathnameIndex === -1) return this._url.search;
        const url = this.href;
        this.#search = queryIndex === -1 || queryIndex === url.length - 1 ? "" : url.slice(queryIndex);
      }
      return this.#search;
    }
    get searchParams() {
      if (this.#url) return this.#url.searchParams;
      if (!this.#searchParams) this.#searchParams = new URLSearchParams(this.search);
      return this.#searchParams;
    }
    get protocol() {
      if (this.#url) return this.#url.protocol;
      if (this.#protocol === void 0) {
        const [protocolIndex] = this.#getPos();
        if (protocolIndex === -1) return this._url.protocol;
        this.#protocol = this.href.slice(0, protocolIndex + 1);
      }
      return this.#protocol;
    }
    toString() {
      return this.href;
    }
    toJSON() {
      return this.href;
    }
  };
  lazyInherit(FastURL$12.prototype, NativeURL.prototype, "_url");
  Object.setPrototypeOf(FastURL$12.prototype, NativeURL.prototype);
  Object.setPrototypeOf(FastURL$12, NativeURL);
  return FastURL$12;
})();
const NodeResponse = /* @__PURE__ */ (() => {
  const NativeResponse = globalThis.Response;
  const STATUS_CODES = globalThis.process?.getBuiltinModule?.("node:http")?.STATUS_CODES || {};
  class NodeResponse$12 {
    #body;
    #init;
    #headers;
    #response;
    constructor(body, init) {
      this.#body = body;
      this.#init = init;
    }
    static [Symbol.hasInstance](val) {
      return val instanceof NativeResponse;
    }
    get status() {
      return this.#response?.status || this.#init?.status || 200;
    }
    get statusText() {
      return this.#response?.statusText || this.#init?.statusText || STATUS_CODES[this.status] || "";
    }
    get headers() {
      if (this.#response) return this.#response.headers;
      if (this.#headers) return this.#headers;
      const initHeaders = this.#init?.headers;
      return this.#headers = initHeaders instanceof Headers ? initHeaders : new Headers(initHeaders);
    }
    get ok() {
      if (this.#response) return this.#response.ok;
      const status = this.status;
      return status >= 200 && status < 300;
    }
    get _response() {
      if (this.#response) return this.#response;
      this.#response = new NativeResponse(this.#body, this.#headers ? {
        ...this.#init,
        headers: this.#headers
      } : this.#init);
      this.#init = void 0;
      this.#headers = void 0;
      this.#body = void 0;
      return this.#response;
    }
    _toNodeResponse() {
      const status = this.status;
      const statusText = this.statusText;
      let body;
      let contentType;
      let contentLength;
      if (this.#response) body = this.#response.body;
      else if (this.#body) if (this.#body instanceof ReadableStream) body = this.#body;
      else if (typeof this.#body === "string") {
        body = this.#body;
        contentType = "text/plain; charset=UTF-8";
        contentLength = Buffer.byteLength(this.#body);
      } else if (this.#body instanceof ArrayBuffer) {
        body = Buffer.from(this.#body);
        contentLength = this.#body.byteLength;
      } else if (this.#body instanceof Uint8Array) {
        body = this.#body;
        contentLength = this.#body.byteLength;
      } else if (this.#body instanceof DataView) {
        body = Buffer.from(this.#body.buffer);
        contentLength = this.#body.byteLength;
      } else if (this.#body instanceof Blob) {
        body = this.#body.stream();
        contentType = this.#body.type;
        contentLength = this.#body.size;
      } else if (typeof this.#body.pipe === "function") body = this.#body;
      else body = this._response.body;
      const headers2 = [];
      const initHeaders = this.#init?.headers;
      const headerEntries = this.#response?.headers || this.#headers || (initHeaders ? Array.isArray(initHeaders) ? initHeaders : initHeaders?.entries ? initHeaders.entries() : Object.entries(initHeaders).map(([k, v]) => [k.toLowerCase(), v]) : void 0);
      let hasContentTypeHeader;
      let hasContentLength;
      if (headerEntries) for (const [key2, value] of headerEntries) {
        if (Array.isArray(value)) for (const v of value) headers2.push([key2, v]);
        else headers2.push([key2, value]);
        if (key2 === "content-type") hasContentTypeHeader = true;
        else if (key2 === "content-length") hasContentLength = true;
      }
      if (contentType && !hasContentTypeHeader) headers2.push(["content-type", contentType]);
      if (contentLength && !hasContentLength) headers2.push(["content-length", String(contentLength)]);
      this.#init = void 0;
      this.#headers = void 0;
      this.#response = void 0;
      this.#body = void 0;
      return {
        status,
        statusText,
        headers: headers2,
        body
      };
    }
  }
  lazyInherit(NodeResponse$12.prototype, NativeResponse.prototype, "_response");
  Object.setPrototypeOf(NodeResponse$12, NativeResponse);
  Object.setPrototypeOf(NodeResponse$12.prototype, NativeResponse.prototype);
  return NodeResponse$12;
})();
const kEventNS = "h3.internal.event.";
const kEventRes = /* @__PURE__ */ Symbol.for(`${kEventNS}res`);
const kEventResHeaders = /* @__PURE__ */ Symbol.for(`${kEventNS}res.headers`);
var H3Event = class {
  app;
  req;
  url;
  context;
  static __is_event__ = true;
  constructor(req, context, app) {
    this.context = context || req.context || new NullProtoObj();
    this.req = req;
    this.app = app;
    const _url = req._url;
    this.url = _url && _url instanceof URL ? _url : new FastURL(req.url);
  }
  get res() {
    return this[kEventRes] ||= new H3EventResponse();
  }
  get runtime() {
    return this.req.runtime;
  }
  waitUntil(promise) {
    this.req.waitUntil?.(promise);
  }
  toString() {
    return `[${this.req.method}] ${this.req.url}`;
  }
  toJSON() {
    return this.toString();
  }
  get node() {
    return this.req.runtime?.node;
  }
  get headers() {
    return this.req.headers;
  }
  get path() {
    return this.url.pathname + this.url.search;
  }
  get method() {
    return this.req.method;
  }
};
var H3EventResponse = class {
  status;
  statusText;
  get headers() {
    return this[kEventResHeaders] ||= new Headers();
  }
};
const DISALLOWED_STATUS_CHARS = /[^\u0009\u0020-\u007E]/g;
function sanitizeStatusMessage(statusMessage = "") {
  return statusMessage.replace(DISALLOWED_STATUS_CHARS, "");
}
function sanitizeStatusCode(statusCode, defaultStatusCode = 200) {
  if (!statusCode) return defaultStatusCode;
  if (typeof statusCode === "string") statusCode = +statusCode;
  if (statusCode < 100 || statusCode > 599) return defaultStatusCode;
  return statusCode;
}
var HTTPError = class HTTPError2 extends Error {
  get name() {
    return "HTTPError";
  }
  status;
  statusText;
  headers;
  cause;
  data;
  body;
  unhandled;
  static isError(input) {
    return input instanceof Error && input?.name === "HTTPError";
  }
  static status(status, statusText, details) {
    return new HTTPError2({
      ...details,
      statusText,
      status
    });
  }
  constructor(arg1, arg2) {
    let messageInput;
    let details;
    if (typeof arg1 === "string") {
      messageInput = arg1;
      details = arg2;
    } else details = arg1;
    const status = sanitizeStatusCode(details?.status || details?.cause?.status || details?.status || details?.statusCode, 500);
    const statusText = sanitizeStatusMessage(details?.statusText || details?.cause?.statusText || details?.statusText || details?.statusMessage);
    const message = messageInput || details?.message || details?.cause?.message || details?.statusText || details?.statusMessage || [
      "HTTPError",
      status,
      statusText
    ].filter(Boolean).join(" ");
    super(message, { cause: details });
    this.cause = details;
    Error.captureStackTrace?.(this, this.constructor);
    this.status = status;
    this.statusText = statusText || void 0;
    const rawHeaders = details?.headers || details?.cause?.headers;
    this.headers = rawHeaders ? new Headers(rawHeaders) : void 0;
    this.unhandled = details?.unhandled ?? details?.cause?.unhandled ?? void 0;
    this.data = details?.data;
    this.body = details?.body;
  }
  get statusCode() {
    return this.status;
  }
  get statusMessage() {
    return this.statusText;
  }
  toJSON() {
    const unhandled = this.unhandled;
    return {
      status: this.status,
      statusText: this.statusText,
      unhandled,
      message: unhandled ? "HTTPError" : this.message,
      data: unhandled ? void 0 : this.data,
      ...unhandled ? void 0 : this.body
    };
  }
};
function isJSONSerializable(value, _type) {
  if (value === null || value === void 0) return true;
  if (_type !== "object") return _type === "boolean" || _type === "number" || _type === "string";
  if (typeof value.toJSON === "function") return true;
  if (Array.isArray(value)) return true;
  if (typeof value.pipe === "function" || typeof value.pipeTo === "function") return false;
  if (value instanceof NullProtoObj) return true;
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}
const kNotFound = /* @__PURE__ */ Symbol.for("h3.notFound");
const kHandled = /* @__PURE__ */ Symbol.for("h3.handled");
function toResponse(val, event, config = {}) {
  if (typeof val?.then === "function") return (val.catch?.((error) => error) || Promise.resolve(val)).then((resolvedVal) => toResponse(resolvedVal, event, config));
  const response = prepareResponse(val, event, config);
  if (typeof response?.then === "function") return toResponse(response, event, config);
  const { onResponse: onResponse$1 } = config;
  return onResponse$1 ? Promise.resolve(onResponse$1(response, event)).then(() => response) : response;
}
var HTTPResponse = class {
  #headers;
  #init;
  body;
  constructor(body, init) {
    this.body = body;
    this.#init = init;
  }
  get status() {
    return this.#init?.status || 200;
  }
  get statusText() {
    return this.#init?.statusText || "OK";
  }
  get headers() {
    return this.#headers ||= new Headers(this.#init?.headers);
  }
};
function prepareResponse(val, event, config, nested) {
  if (val === kHandled) return new NodeResponse(null);
  if (val === kNotFound) val = new HTTPError({
    status: 404,
    message: `Cannot find any route matching [${event.req.method}] ${event.url}`
  });
  if (val && val instanceof Error) {
    const isHTTPError = HTTPError.isError(val);
    const error = isHTTPError ? val : new HTTPError(val);
    if (!isHTTPError) {
      error.unhandled = true;
      if (val?.stack) error.stack = val.stack;
    }
    if (error.unhandled && !config.silent) console.error(error);
    const { onError: onError$1 } = config;
    return onError$1 && !nested ? Promise.resolve(onError$1(error, event)).catch((error$1) => error$1).then((newVal) => prepareResponse(newVal ?? val, event, config, true)) : errorResponse(error, config.debug);
  }
  const preparedRes = event[kEventRes];
  const preparedHeaders = preparedRes?.[kEventResHeaders];
  if (!(val instanceof Response)) {
    const res = prepareResponseBody(val, event, config);
    const status = res.status || preparedRes?.status;
    return new NodeResponse(nullBody(event.req.method, status) ? null : res.body, {
      status,
      statusText: res.statusText || preparedRes?.statusText,
      headers: res.headers && preparedHeaders ? mergeHeaders$1(res.headers, preparedHeaders) : res.headers || preparedHeaders
    });
  }
  if (!preparedHeaders || nested || !val.ok) return val;
  try {
    mergeHeaders$1(val.headers, preparedHeaders, val.headers);
    return val;
  } catch {
    return new NodeResponse(nullBody(event.req.method, val.status) ? null : val.body, {
      status: val.status,
      statusText: val.statusText,
      headers: mergeHeaders$1(val.headers, preparedHeaders)
    });
  }
}
function mergeHeaders$1(base, overrides, target = new Headers(base)) {
  for (const [name, value] of overrides) if (name === "set-cookie") target.append(name, value);
  else target.set(name, value);
  return target;
}
const frozenHeaders = () => {
  throw new Error("Headers are frozen");
};
var FrozenHeaders = class extends Headers {
  constructor(init) {
    super(init);
    this.set = this.append = this.delete = frozenHeaders;
  }
};
const emptyHeaders = /* @__PURE__ */ new FrozenHeaders({ "content-length": "0" });
const jsonHeaders = /* @__PURE__ */ new FrozenHeaders({ "content-type": "application/json;charset=UTF-8" });
function prepareResponseBody(val, event, config) {
  if (val === null || val === void 0) return {
    body: "",
    headers: emptyHeaders
  };
  const valType = typeof val;
  if (valType === "string") return { body: val };
  if (val instanceof Uint8Array) {
    event.res.headers.set("content-length", val.byteLength.toString());
    return { body: val };
  }
  if (val instanceof HTTPResponse || val?.constructor?.name === "HTTPResponse") return val;
  if (isJSONSerializable(val, valType)) return {
    body: JSON.stringify(val, void 0, config.debug ? 2 : void 0),
    headers: jsonHeaders
  };
  if (valType === "bigint") return {
    body: val.toString(),
    headers: jsonHeaders
  };
  if (val instanceof Blob) {
    const headers2 = new Headers({
      "content-type": val.type,
      "content-length": val.size.toString()
    });
    let filename = val.name;
    if (filename) {
      filename = encodeURIComponent(filename);
      headers2.set("content-disposition", `filename="${filename}"; filename*=UTF-8''${filename}`);
    }
    return {
      body: val.stream(),
      headers: headers2
    };
  }
  if (valType === "symbol") return { body: val.toString() };
  if (valType === "function") return { body: `${val.name}()` };
  return { body: val };
}
function nullBody(method, status) {
  return method === "HEAD" || status === 100 || status === 101 || status === 102 || status === 204 || status === 205 || status === 304;
}
function errorResponse(error, debug) {
  return new NodeResponse(JSON.stringify({
    ...error.toJSON(),
    stack: debug && error.stack ? error.stack.split("\n").map((l) => l.trim()) : void 0
  }, void 0, debug ? 2 : void 0), {
    status: error.status,
    statusText: error.statusText,
    headers: error.headers ? mergeHeaders$1(jsonHeaders, error.headers) : new Headers(jsonHeaders)
  });
}
function callMiddleware(event, middleware, handler, index = 0) {
  if (index === middleware.length) return handler(event);
  const fn = middleware[index];
  let nextCalled;
  let nextResult;
  const next = () => {
    if (nextCalled) return nextResult;
    nextCalled = true;
    nextResult = callMiddleware(event, middleware, handler, index + 1);
    return nextResult;
  };
  const ret = fn(event, next);
  return isUnhandledResponse(ret) ? next() : typeof ret?.then === "function" ? ret.then((resolved) => isUnhandledResponse(resolved) ? next() : resolved) : ret;
}
function isUnhandledResponse(val) {
  return val === void 0 || val === kNotFound;
}
function toRequest(input, options) {
  if (typeof input === "string") {
    let url = input;
    if (url[0] === "/") {
      const host2 = "localhost";
      url = `${"http"}://${host2}${url}`;
    }
    return new Request(url, options);
  } else if (input instanceof URL) return new Request(input, options);
  return input;
}
function defineHandler(input) {
  if (typeof input === "function") return handlerWithFetch(input);
  const handler = input.handler || (input.fetch ? function _fetchHandler(event) {
    return input.fetch(event.req);
  } : NoHandler);
  return Object.assign(handlerWithFetch(input.middleware?.length ? function _handlerMiddleware(event) {
    return callMiddleware(event, input.middleware, handler);
  } : handler), input);
}
function handlerWithFetch(handler) {
  if ("fetch" in handler) return handler;
  return Object.assign(handler, { fetch: (req) => {
    if (typeof req === "string") req = new URL(req, "http://_");
    if (req instanceof URL) req = new Request(req);
    const event = new H3Event(req);
    try {
      return Promise.resolve(toResponse(handler(event), event));
    } catch (error) {
      return Promise.resolve(toResponse(error, event));
    }
  } });
}
function defineLazyEventHandler(loader) {
  let handler;
  let promise;
  const resolveLazyHandler = () => {
    if (handler) return Promise.resolve(handler);
    return promise ??= Promise.resolve(loader()).then((r) => {
      handler = toEventHandler(r) || toEventHandler(r.default);
      if (typeof handler !== "function") throw new TypeError("Invalid lazy handler", { cause: { resolved: r } });
      return handler;
    });
  };
  return defineHandler(function lazyHandler(event) {
    return handler ? handler(event) : resolveLazyHandler().then((r) => r(event));
  });
}
function toEventHandler(handler) {
  if (typeof handler === "function") return handler;
  if (typeof handler?.handler === "function") return handler.handler;
  if (typeof handler?.fetch === "function") return function _fetchHandler(event) {
    return handler.fetch(event.req);
  };
}
const NoHandler = () => kNotFound;
var H3Core = class {
  config;
  "~middleware";
  "~routes" = [];
  constructor(config = {}) {
    this["~middleware"] = [];
    this.config = config;
    this.fetch = this.fetch.bind(this);
    this.handler = this.handler.bind(this);
  }
  fetch(request) {
    return this["~request"](request);
  }
  handler(event) {
    const route = this["~findRoute"](event);
    if (route) {
      event.context.params = route.params;
      event.context.matchedRoute = route.data;
    }
    const routeHandler = route?.data.handler || NoHandler;
    const middleware = this["~getMiddleware"](event, route);
    return middleware.length > 0 ? callMiddleware(event, middleware, routeHandler) : routeHandler(event);
  }
  "~request"(request, context) {
    const event = new H3Event(request, context, this);
    let handlerRes;
    try {
      if (this.config.onRequest) {
        const hookRes = this.config.onRequest(event);
        handlerRes = typeof hookRes?.then === "function" ? hookRes.then(() => this.handler(event)) : this.handler(event);
      } else handlerRes = this.handler(event);
    } catch (error) {
      handlerRes = Promise.reject(error);
    }
    return toResponse(handlerRes, event, this.config);
  }
  "~findRoute"(_event) {
  }
  "~addRoute"(_route) {
    this["~routes"].push(_route);
  }
  "~getMiddleware"(_event, route) {
    const routeMiddleware = route?.data.middleware;
    const globalMiddleware2 = this["~middleware"];
    return routeMiddleware ? [...globalMiddleware2, ...routeMiddleware] : globalMiddleware2;
  }
};
const errorHandler$1 = (error, event) => {
  const res = defaultHandler(error, event);
  return new NodeResponse$1(typeof res.body === "string" ? res.body : JSON.stringify(res.body, null, 2), res);
};
function defaultHandler(error, event, opts) {
  const isSensitive = error.unhandled;
  const status = error.status || 500;
  const url = event.url || new URL(event.req.url);
  if (status === 404) {
    const baseURL = "/";
    if (/^\/[^/]/.test(baseURL) && !url.pathname.startsWith(baseURL)) {
      const redirectTo = `${baseURL}${url.pathname.slice(1)}${url.search}`;
      return {
        status: 302,
        statusText: "Found",
        headers: { location: redirectTo },
        body: `Redirecting...`
      };
    }
  }
  if (isSensitive && !opts?.silent) {
    const tags = [error.unhandled && "[unhandled]"].filter(Boolean).join(" ");
    console.error(`[request error] ${tags} [${event.req.method}] ${url}
`, error);
  }
  const headers2 = {
    "content-type": "application/json",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "content-security-policy": "script-src 'none'; frame-ancestors 'none';"
  };
  if (status === 404 || !event.res.headers.has("cache-control")) {
    headers2["cache-control"] = "no-cache";
  }
  const body = {
    error: true,
    url: url.href,
    status,
    statusText: error.statusText,
    message: isSensitive ? "Server Error" : error.message,
    data: isSensitive ? void 0 : error.data
  };
  return {
    status,
    statusText: error.statusText,
    headers: headers2,
    body
  };
}
const errorHandlers = [errorHandler$1];
async function errorHandler(error, event) {
  for (const handler of errorHandlers) {
    try {
      const response = await handler(error, event, { defaultHandler });
      if (response) {
        return response;
      }
    } catch (error2) {
      console.error(error2);
    }
  }
}
const ENC_SLASH_RE = /%2f/gi;
function decode(text = "") {
  try {
    return decodeURIComponent("" + text);
  } catch {
    return "" + text;
  }
}
function decodePath(text) {
  return decode(text.replace(ENC_SLASH_RE, "%252F"));
}
const JOIN_LEADING_SLASH_RE = /^\.?\//;
function hasTrailingSlash(input = "", respectQueryAndFragment) {
  {
    return input.endsWith("/");
  }
}
function withoutTrailingSlash(input = "", respectQueryAndFragment) {
  {
    return (hasTrailingSlash(input) ? input.slice(0, -1) : input) || "/";
  }
}
function withTrailingSlash(input = "", respectQueryAndFragment) {
  {
    return input.endsWith("/") ? input : input + "/";
  }
}
function hasLeadingSlash(input = "") {
  return input.startsWith("/");
}
function withLeadingSlash(input = "") {
  return hasLeadingSlash(input) ? input : "/" + input;
}
function isNonEmptyURL(url) {
  return url && url !== "/";
}
function joinURL(base, ...input) {
  let url = base || "";
  for (const segment of input.filter((url2) => isNonEmptyURL(url2))) {
    if (url) {
      const _segment = segment.replace(JOIN_LEADING_SLASH_RE, "");
      url = withTrailingSlash(url) + _segment;
    } else {
      url = segment;
    }
  }
  return url;
}
const headers = ((m) => function headersRouteRule(event) {
  for (const [key2, value] of Object.entries(m.options || {})) {
    event.res.headers.set(key2, value);
  }
});
const assets = {
  "/favicon.ico": {
    "type": "image/vnd.microsoft.icon",
    "etag": '"f1e-ESBTjHetHyiokkO0tT/irBbMO8Y"',
    "mtime": "2026-01-05T22:39:37.828Z",
    "size": 3870,
    "path": "../public/favicon.ico"
  },
  "/logo192.png": {
    "type": "image/png",
    "etag": '"14e3-f08taHgqf6/O2oRVTsq5tImHdQA"',
    "mtime": "2026-01-05T22:39:37.834Z",
    "size": 5347,
    "path": "../public/logo192.png"
  },
  "/logo512.png": {
    "type": "image/png",
    "etag": '"25c0-RpFfnQJpTtSb/HqVNJR2hBA9w/4"',
    "mtime": "2026-01-05T22:39:37.834Z",
    "size": 9664,
    "path": "../public/logo512.png"
  },
  "/manifest.json": {
    "type": "application/json",
    "etag": '"1f2-Oqn/x1R1hBTtEjA8nFhpBeFJJNg"',
    "mtime": "2026-01-05T22:39:37.834Z",
    "size": 498,
    "path": "../public/manifest.json"
  },
  "/robots.txt": {
    "type": "text/plain; charset=utf-8",
    "etag": '"43-BEzmj4PuhUNHX+oW9uOnPSihxtU"',
    "mtime": "2026-01-05T22:39:37.834Z",
    "size": 67,
    "path": "../public/robots.txt"
  },
  "/tanstack-circle-logo.png": {
    "type": "image/png",
    "etag": '"40cab-HZ1KcYPs7tRjLe4Sd4g6CwKW+W8"',
    "mtime": "2026-01-05T22:39:37.834Z",
    "size": 265387,
    "path": "../public/tanstack-circle-logo.png"
  },
  "/tanstack-word-logo-white.svg": {
    "type": "image/svg+xml",
    "etag": '"3a9a-9TQFm/pN8AZe1ZK0G1KyCEojnYg"',
    "mtime": "2026-01-05T22:39:37.834Z",
    "size": 15002,
    "path": "../public/tanstack-word-logo-white.svg"
  },
  "/assets/_collectionId-BzICLh1F.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"1a201-D0WZyHVrrRe98pIopQgeZAQn8qk"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 107009,
    "path": "../public/assets/_collectionId-BzICLh1F.js"
  },
  "/assets/add-new-source-C7YdYOoL.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"2da0-ZRjZNZS2p8bZlW19P6btQAGBako"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 11680,
    "path": "../public/assets/add-new-source-C7YdYOoL.js"
  },
  "/assets/api-form-CPp1CwpP.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"1ec3-6TlFS1P5/Sy2sbzJX5O4CbXye/w"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 7875,
    "path": "../public/assets/api-form-CPp1CwpP.js"
  },
  "/assets/api-keys-CDc8ip8A.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"330-7APSUQde9Zb6RVz8VK+wIPxTeBY"',
    "mtime": "2026-01-05T22:39:38.059Z",
    "size": 816,
    "path": "../public/assets/api-keys-CDc8ip8A.js"
  },
  "/assets/api-keys-Cv1Cc2xh.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"315d-niG8rVwL/NvNykyAjK+VXOJl6hE"',
    "mtime": "2026-01-05T22:39:38.059Z",
    "size": 12637,
    "path": "../public/assets/api-keys-Cv1Cc2xh.js"
  },
  "/assets/arrow-right-CWnj4Tjf.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"a5-MBSjrdHoV5xa64xALz8tVlnYY0E"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 165,
    "path": "../public/assets/arrow-right-CWnj4Tjf.js"
  },
  "/assets/auth-providers-Bc9ymBaZ.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"610-qh5uF0gAFwzxJ6yX1h0otQeFf1o"',
    "mtime": "2026-01-05T22:39:38.059Z",
    "size": 1552,
    "path": "../public/assets/auth-providers-Bc9ymBaZ.js"
  },
  "/assets/auth-providers-CudllOQV.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"6d38-Dpq5vCdSJfAXhK7sAVyLQzGDhAg"',
    "mtime": "2026-01-05T22:39:38.059Z",
    "size": 27960,
    "path": "../public/assets/auth-providers-CudllOQV.js"
  },
  "/assets/badge-CC5o5dUU.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"47c-HhoQUtAWVR3/vgwNFiIvpgrWlCU"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 1148,
    "path": "../public/assets/badge-CC5o5dUU.js"
  },
  "/assets/card-B5HDbqx5.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"4b9-I+0bAmTlbPx0d/dULLD4AxEwHXM"',
    "mtime": "2026-01-05T22:39:38.059Z",
    "size": 1209,
    "path": "../public/assets/card-B5HDbqx5.js"
  },
  "/assets/checkbox-CmSojv_w.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"165e-rxlMy+RS3JiZMaDnle52ShOPaag"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 5726,
    "path": "../public/assets/checkbox-CmSojv_w.js"
  },
  "/assets/collections-Yw3Eirdu.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"ebe-Sl1v6lYnkKCMScEpcaCF4JjluTI"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 3774,
    "path": "../public/assets/collections-Yw3Eirdu.js"
  },
  "/assets/components-BsJGWw2u.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"7cb-kRIIZFM+gwX0E/O5yf43Lr9R+NE"',
    "mtime": "2026-01-05T22:39:38.058Z",
    "size": 1995,
    "path": "../public/assets/components-BsJGWw2u.js"
  },
  "/assets/components._componentName-Cjy5RaLb.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"d156-KAECVLKSWLFB7Uw5HsxxLSw64l8"',
    "mtime": "2026-01-05T22:39:38.059Z",
    "size": 53590,
    "path": "../public/assets/components._componentName-Cjy5RaLb.js"
  },
  "/assets/components.gen-B6SRBd62.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"10f0-I44CqNuLviNw4uRT62GUc23en94"',
    "mtime": "2026-01-05T22:39:38.059Z",
    "size": 4336,
    "path": "../public/assets/components.gen-B6SRBd62.js"
  },
  "/assets/components.index-CvoB_vEk.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"8ad-ybfAP3NrWIkiDuczOmTnaY/ovOI"',
    "mtime": "2026-01-05T22:39:38.059Z",
    "size": 2221,
    "path": "../public/assets/components.index-CvoB_vEk.js"
  },
  "/assets/composio-D_j15Cmg.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"27f8-+eQJoq20z5jms0MMH4PCtJJQ19Q"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 10232,
    "path": "../public/assets/composio-D_j15Cmg.js"
  },
  "/assets/concepts-DyXBKb5r.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"f69-zsY/B35lqh2X5zZc0zfYT6vUifU"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 3945,
    "path": "../public/assets/concepts-DyXBKb5r.js"
  },
  "/assets/concepts-gNIvJYCA.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"213a-YMszs/TGY6LUVe75td982jfsEzw"',
    "mtime": "2026-01-05T22:39:38.063Z",
    "size": 8506,
    "path": "../public/assets/concepts-gNIvJYCA.js"
  },
  "/assets/data-table-floating-toolbar-BMmz4eaj.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"e032-Xw6uqhhF+/fZLUZIZYy6NQDu4w4"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 57394,
    "path": "../public/assets/data-table-floating-toolbar-BMmz4eaj.js"
  },
  "/assets/direct-oauth-CKXxJrB2.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"344d-IQtzK24c0/ZQRp3qSXKHooGtig4"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 13389,
    "path": "../public/assets/direct-oauth-CKXxJrB2.js"
  },
  "/assets/direct-token-injection-CSRKsCaZ.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"15c1-KJUdUVFoJwRceGNpBUMhwc8xQ9o"',
    "mtime": "2026-01-05T22:39:38.063Z",
    "size": 5569,
    "path": "../public/assets/direct-token-injection-CSRKsCaZ.js"
  },
  "/assets/empty-state-DKSl-bi2.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"290-+0mqKF29RXH8CYYU03ZRu5orFLA"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 656,
    "path": "../public/assets/empty-state-DKSl-bi2.js"
  },
  "/assets/error-state-DJ8okmbQ.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"16bc-lBGdbCc6yJxsNq3bBr+QFMZlZuM"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 5820,
    "path": "../public/assets/error-state-DJ8okmbQ.js"
  },
  "/assets/examples-DpA1FH5M.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"183e-WqgNVsXf0H0RokbzIyNicGEdznM"',
    "mtime": "2026-01-05T22:39:38.063Z",
    "size": 6206,
    "path": "../public/assets/examples-DpA1FH5M.js"
  },
  "/assets/filters-DjcxsPCV.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"24f5-/ZbtzbX4r5tCD38hPRzbfFcqldw"',
    "mtime": "2026-01-05T22:39:38.063Z",
    "size": 9461,
    "path": "../public/assets/filters-DjcxsPCV.js"
  },
  "/assets/index-CDq7RN1u.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"24a0-VCsn06eekmobkh46wPR70sLbGos"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 9376,
    "path": "../public/assets/index-CDq7RN1u.js"
  },
  "/assets/index-DvFN5XTw.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"450-vvSoZsT+mCtDgeYORlXHQJ8MKiA"',
    "mtime": "2026-01-05T22:39:38.059Z",
    "size": 1104,
    "path": "../public/assets/index-DvFN5XTw.js"
  },
  "/assets/input-Dgezjod8.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"321-+BcmzThufdS1WpG0CssrwDoxpjc"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 801,
    "path": "../public/assets/input-Dgezjod8.js"
  },
  "/assets/layers-DhhXo1wF.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"1a5-4rCrgQzlzUACs9cIx3KegSPFpxs"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 421,
    "path": "../public/assets/layers-DhhXo1wF.js"
  },
  "/assets/llamaindex-B7B2x1g8.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"3057-sx8ciG/EVsDq3LSPh775k5t8R0Y"',
    "mtime": "2026-01-05T22:39:38.062Z",
    "size": 12375,
    "path": "../public/assets/llamaindex-B7B2x1g8.js"
  },
  "/assets/loading-state-DlUdFJYL.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"1e7-TEZpPlLufpeAfsVMTaqUPNfEiwk"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 487,
    "path": "../public/assets/loading-state-DlUdFJYL.js"
  },
  "/assets/logs-oW7HzLaj.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"9b4-1/Szs1OrYrb+0mAzdJp2FHxX2ko"',
    "mtime": "2026-01-05T22:39:38.059Z",
    "size": 2484,
    "path": "../public/assets/logs-oW7HzLaj.js"
  },
  "/assets/main-009I6u0H.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"2e4b-A7Saqjcxxx4Mq3EEOZi8O8wPbqg"',
    "mtime": "2026-01-05T22:39:38.061Z",
    "size": 11851,
    "path": "../public/assets/main-009I6u0H.js"
  },
  "/assets/main-1ekVKjLi.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"3195-kvTzeNiMSxC2gENIv1+hUBva7Ao"',
    "mtime": "2026-01-05T22:39:38.062Z",
    "size": 12693,
    "path": "../public/assets/main-1ekVKjLi.js"
  },
  "/assets/main-5FIaYKlU.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"11b7-lZgsU1SxEmGnMbte80NswUBW5lM"',
    "mtime": "2026-01-05T22:39:38.062Z",
    "size": 4535,
    "path": "../public/assets/main-5FIaYKlU.js"
  },
  "/assets/main-B461im-g.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"1314-Rfxwh3m4wnpOjpDcOiflHXoyxVg"',
    "mtime": "2026-01-05T22:39:38.061Z",
    "size": 4884,
    "path": "../public/assets/main-B461im-g.js"
  },
  "/assets/main-BCPanuaY.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"4514-TnIFmT7LMXGbo1XDLNepdun1qLQ"',
    "mtime": "2026-01-05T22:39:38.061Z",
    "size": 17684,
    "path": "../public/assets/main-BCPanuaY.js"
  },
  "/assets/main-BDM2ePvB.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"27c6-Ccx/XGtCahnYmY7lI/WB/x7TJOg"',
    "mtime": "2026-01-05T22:39:38.061Z",
    "size": 10182,
    "path": "../public/assets/main-BDM2ePvB.js"
  },
  "/assets/main-BEToz-TC.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"a0c03-hDL9LDV4H770TmvtFEGmRW17+6M"',
    "mtime": "2026-01-05T22:39:38.063Z",
    "size": 658435,
    "path": "../public/assets/main-BEToz-TC.js"
  },
  "/assets/main-BGMjNY5P.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"243e-2GRL5GgTMzXY3U6rcDE9WfFIvpU"',
    "mtime": "2026-01-05T22:39:38.062Z",
    "size": 9278,
    "path": "../public/assets/main-BGMjNY5P.js"
  },
  "/assets/main-BH7pOKTy.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"41b6-VKDlcPpTJq2pIpEGx/u0dDfwHw0"',
    "mtime": "2026-01-05T22:39:38.062Z",
    "size": 16822,
    "path": "../public/assets/main-BH7pOKTy.js"
  },
  "/assets/main-BlPB4G6Y.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"2e6a-u+/HAsEbumMdCC1pD5EURmvLUUc"',
    "mtime": "2026-01-05T22:39:38.061Z",
    "size": 11882,
    "path": "../public/assets/main-BlPB4G6Y.js"
  },
  "/assets/main-Bz6W4r0L.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"c9a-5hmcp/Khc1qzdNLZtVRXTlNjMwk"',
    "mtime": "2026-01-05T22:39:38.062Z",
    "size": 3226,
    "path": "../public/assets/main-Bz6W4r0L.js"
  },
  "/assets/main-C7DLlqv1.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"2dc3-MdGC0o/2wqResjEXTzLrp+LlXPg"',
    "mtime": "2026-01-05T22:39:38.062Z",
    "size": 11715,
    "path": "../public/assets/main-C7DLlqv1.js"
  },
  "/assets/main-CA5bvmfO.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"c5b-HlmVVIFB5Z59UZzDJTlbabn13xw"',
    "mtime": "2026-01-05T22:39:38.062Z",
    "size": 3163,
    "path": "../public/assets/main-CA5bvmfO.js"
  },
  "/assets/main-CFt7QV77.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"56ac-xHDeC1VlwKUwifLRpUIK8jFOCnk"',
    "mtime": "2026-01-05T22:39:38.062Z",
    "size": 22188,
    "path": "../public/assets/main-CFt7QV77.js"
  },
  "/assets/main-CSw8an8W.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"3054-mxttSXrcE59l6616WDNjs1V7rig"',
    "mtime": "2026-01-05T22:39:38.062Z",
    "size": 12372,
    "path": "../public/assets/main-CSw8an8W.js"
  },
  "/assets/main-CZrN1qDz.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"1dcd-DUfDVaJeHRoQysv6gDGkENhJ8sQ"',
    "mtime": "2026-01-05T22:39:38.061Z",
    "size": 7629,
    "path": "../public/assets/main-CZrN1qDz.js"
  },
  "/assets/main-C_ahaJb8.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"407a-r6zuWCL9BNL7oZCrpRUV2bGJOVA"',
    "mtime": "2026-01-05T22:39:38.061Z",
    "size": 16506,
    "path": "../public/assets/main-C_ahaJb8.js"
  },
  "/assets/main-CbYNRVMC.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"b7d-PTJBcOpO+vgZ3WId7c+30uqa3SM"',
    "mtime": "2026-01-05T22:39:38.062Z",
    "size": 2941,
    "path": "../public/assets/main-CbYNRVMC.js"
  },
  "/assets/main-CeMYm_E4.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"5803-9s5ozHR7B3tfjANoqoeAhp3mWRA"',
    "mtime": "2026-01-05T22:39:38.062Z",
    "size": 22531,
    "path": "../public/assets/main-CeMYm_E4.js"
  },
  "/assets/main-Cm3dTIyd.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"3c01-e18cQycJn3MZz79TlQTkU7F1KBo"',
    "mtime": "2026-01-05T22:39:38.061Z",
    "size": 15361,
    "path": "../public/assets/main-Cm3dTIyd.js"
  },
  "/assets/main-CmbCGaeR.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"26b2-aBfqIRlM8aNUBkP+C+qOSzn110c"',
    "mtime": "2026-01-05T22:39:38.062Z",
    "size": 9906,
    "path": "../public/assets/main-CmbCGaeR.js"
  },
  "/assets/main-CqIPsBxP.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"2862-htIfzGFbxAoiu7g9rHUGUzlQN5c"',
    "mtime": "2026-01-05T22:39:38.062Z",
    "size": 10338,
    "path": "../public/assets/main-CqIPsBxP.js"
  },
  "/assets/main-Ctb5Tb9j.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"c48-pIX5QTDUT1G/Py6WxZvMilLolPc"',
    "mtime": "2026-01-05T22:39:38.062Z",
    "size": 3144,
    "path": "../public/assets/main-Ctb5Tb9j.js"
  },
  "/assets/main-CvADMPC-.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"4305-HgFI3tsbF2Z7cQh7+/ekLtCQjHE"',
    "mtime": "2026-01-05T22:39:38.062Z",
    "size": 17157,
    "path": "../public/assets/main-CvADMPC-.js"
  },
  "/assets/main-Cx_AW7oO.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"5477-msaND9oRNwLJmDGbBc8SzK3njv4"',
    "mtime": "2026-01-05T22:39:38.062Z",
    "size": 21623,
    "path": "../public/assets/main-Cx_AW7oO.js"
  },
  "/assets/main-D08jfcwF.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"3532-PXGI/IDJ0OkftnAskNbItSGKJJw"',
    "mtime": "2026-01-05T22:39:38.062Z",
    "size": 13618,
    "path": "../public/assets/main-D08jfcwF.js"
  },
  "/assets/main-D3CS9oAP.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"24f6-uH15COiPJ6q3subgax6h9NQ+0Ss"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 9462,
    "path": "../public/assets/main-D3CS9oAP.js"
  },
  "/assets/main-DFTVpaZO.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"30e2-OeiYqCWrqzDmP/ZcuIPEi8YQFME"',
    "mtime": "2026-01-05T22:39:38.062Z",
    "size": 12514,
    "path": "../public/assets/main-DFTVpaZO.js"
  },
  "/assets/main-DYLY4cgX.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"c41-BCzH7/dOZSi5bzKiybDy5F5kbb0"',
    "mtime": "2026-01-05T22:39:38.062Z",
    "size": 3137,
    "path": "../public/assets/main-DYLY4cgX.js"
  },
  "/assets/main-DtiEyXkw.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"1afb-8dDZOLrIjR73aSj5ju4BKrfHTok"',
    "mtime": "2026-01-05T22:39:38.061Z",
    "size": 6907,
    "path": "../public/assets/main-DtiEyXkw.js"
  },
  "/assets/main-Du-HsGXB.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"2576-eAm4vyV9D75ZYRKIH5noFGTya0U"',
    "mtime": "2026-01-05T22:39:38.061Z",
    "size": 9590,
    "path": "../public/assets/main-Du-HsGXB.js"
  },
  "/assets/main-DvT-hCgN.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"273a-Rga+d0RPPES7Uegq3Vgt4x+vEWo"',
    "mtime": "2026-01-05T22:39:38.062Z",
    "size": 10042,
    "path": "../public/assets/main-DvT-hCgN.js"
  },
  "/assets/main-DzrvwimM.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"20f4-eBGbp7wMgx0+c6wLnRSv6MgJ5TE"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 8436,
    "path": "../public/assets/main-DzrvwimM.js"
  },
  "/assets/main-FK3pvk1h.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"38e9-skOBoZhL3BFLsiozhIWVdB0KOsM"',
    "mtime": "2026-01-05T22:39:38.061Z",
    "size": 14569,
    "path": "../public/assets/main-FK3pvk1h.js"
  },
  "/assets/main-JenmnmA4.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"3fa5-/D6ehjP/SBRdk/GKaLIZxJtnG34"',
    "mtime": "2026-01-05T22:39:38.061Z",
    "size": 16293,
    "path": "../public/assets/main-JenmnmA4.js"
  },
  "/assets/main-KeXdB7f1.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"2025-/wsbUau/BPrGU1eEx7UNdfGS66w"',
    "mtime": "2026-01-05T22:39:38.061Z",
    "size": 8229,
    "path": "../public/assets/main-KeXdB7f1.js"
  },
  "/assets/main-S9lrTfNQ.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"1120-s/lnkKQGTyNphG6F9PWEdmRz9Xw"',
    "mtime": "2026-01-05T22:39:38.061Z",
    "size": 4384,
    "path": "../public/assets/main-S9lrTfNQ.js"
  },
  "/assets/main-_O2DUkL3.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"42d9-BENImFt9dgcQ9f0/6xJ36mC0mbE"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 17113,
    "path": "../public/assets/main-_O2DUkL3.js"
  },
  "/assets/main-gzrQPCfF.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"15a6-L9HiOUHboFEgvDijDmzrfsGOvDM"',
    "mtime": "2026-01-05T22:39:38.062Z",
    "size": 5542,
    "path": "../public/assets/main-gzrQPCfF.js"
  },
  "/assets/main-h2_bVpmL.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"2906-H7rtX5v1OlVJfrQsKedSAwIcEbg"',
    "mtime": "2026-01-05T22:39:38.062Z",
    "size": 10502,
    "path": "../public/assets/main-h2_bVpmL.js"
  },
  "/assets/main-hbWLYpgH.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"14e5-tUXj6mQebIOPp+vkLS4SpKFMhR0"',
    "mtime": "2026-01-05T22:39:38.062Z",
    "size": 5349,
    "path": "../public/assets/main-hbWLYpgH.js"
  },
  "/assets/main-igRATYFj.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"378a-Upxzudz1W5Z/e1P6Fa6f0DoitWw"',
    "mtime": "2026-01-05T22:39:38.061Z",
    "size": 14218,
    "path": "../public/assets/main-igRATYFj.js"
  },
  "/assets/main-zwr5vLMv.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"2da9-rqXixTylczohZ2yyeQluVnnoSro"',
    "mtime": "2026-01-05T22:39:38.062Z",
    "size": 11689,
    "path": "../public/assets/main-zwr5vLMv.js"
  },
  "/assets/mcp-server-LgMP40FG.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"1c65-6Lz914eAzZChgjhg1FJW8hQQucY"',
    "mtime": "2026-01-05T22:39:38.063Z",
    "size": 7269,
    "path": "../public/assets/mcp-server-LgMP40FG.js"
  },
  "/assets/onboarding-DddSo_Dh.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"5a51-LFGNTbdp9sdhC6eibFhpkZ7Z0Vo"',
    "mtime": "2026-01-05T22:39:38.059Z",
    "size": 23121,
    "path": "../public/assets/onboarding-DddSo_Dh.js"
  },
  "/assets/org-context-QNZ_DRQw.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"435-5VIUHQ5HX7HCdftItTnOn6axBLg"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 1077,
    "path": "../public/assets/org-context-QNZ_DRQw.js"
  },
  "/assets/overview-DrVbWT_p.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"664-xekrvCj2Zp7csgLNCctwTnRzotI"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 1636,
    "path": "../public/assets/overview-DrVbWT_p.js"
  },
  "/assets/pipedream-BgesWAg-.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"553a-/VZ42Ktt+OVXKFoONMG0rno1qh4"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 21818,
    "path": "../public/assets/pipedream-BgesWAg-.js"
  },
  "/assets/quickstart-BTYtCVL0.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"1b5a-+maNN2D9vERTc3x0EZCGJGb5exI"',
    "mtime": "2026-01-05T22:39:38.063Z",
    "size": 7002,
    "path": "../public/assets/quickstart-BTYtCVL0.js"
  },
  "/assets/rate-limits-CfG2sjGp.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"8ab-Ysbrj4578AKgc3b8wgxxaiyYW8o"',
    "mtime": "2026-01-05T22:39:38.063Z",
    "size": 2219,
    "path": "../public/assets/rate-limits-CfG2sjGp.js"
  },
  "/assets/route-8HFFBpA4.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"16ee-Zx+i3BKfqP5R02Eayx7IE4D3VOM"',
    "mtime": "2026-01-05T22:39:38.059Z",
    "size": 5870,
    "path": "../public/assets/route-8HFFBpA4.js"
  },
  "/assets/search-DweEE3Cc.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"871a-lBWLoZEowlapLFIcUNrB8sNvBuo"',
    "mtime": "2026-01-05T22:39:38.063Z",
    "size": 34586,
    "path": "../public/assets/search-DweEE3Cc.js"
  },
  "/assets/settings-CTXMjwWH.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"466-4eHrv2jKKtV5mQpafCdmFh246io"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 1126,
    "path": "../public/assets/settings-CTXMjwWH.js"
  },
  "/assets/sidebar-content-BALcDoUB.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"12c6-KTbtxdnsPbiUQLl4uAugL/2lB7o"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 4806,
    "path": "../public/assets/sidebar-content-BALcDoUB.js"
  },
  "/assets/styles-D-7nFG_c.css": {
    "type": "text/css; charset=utf-8",
    "etag": '"19e3d-zVTYUnHWwOsoY1B8wqSKyd5WYwQ"',
    "mtime": "2026-01-05T22:39:38.059Z",
    "size": 106045,
    "path": "../public/assets/styles-D-7nFG_c.css"
  },
  "/assets/tabs-DYoc-HWa.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"d6e-DBm4ODJBGxK8jRVHjIhht/JwRg0"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 3438,
    "path": "../public/assets/tabs-DYoc-HWa.js"
  },
  "/assets/trash-2-DNkcOHO8.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"148-SQGLgSyW9A34ak15aRNazbBHfiI"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 328,
    "path": "../public/assets/trash-2-DNkcOHO8.js"
  },
  "/assets/trash-DC_b27ub.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"37b-ZXv4t+hw1Tx0VuED9PPlIexfSmo"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 891,
    "path": "../public/assets/trash-DC_b27ub.js"
  },
  "/assets/use-docs-content-ogu5VP42.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"44ef-6UPsUzqGAZkrSCO/cMK31zojl20"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 17647,
    "path": "../public/assets/use-docs-content-ogu5VP42.js"
  },
  "/assets/use-is-dark-pSwRFwVX.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"189-nv1WpsttgkfDqFmggVl42XUKuMU"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 393,
    "path": "../public/assets/use-is-dark-pSwRFwVX.js"
  },
  "/assets/use-keyboard-shortcut-DSl5K4r7.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"214-UeTavagmNhh+gZ1P6iT8hKrB91w"',
    "mtime": "2026-01-05T22:39:38.060Z",
    "size": 532,
    "path": "../public/assets/use-keyboard-shortcut-DSl5K4r7.js"
  },
  "/assets/useForm-Cs18dAFp.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"a20c-N/PkTCxeUcw+SmRcraXSmNjHKIg"',
    "mtime": "2026-01-05T22:39:38.059Z",
    "size": 41484,
    "path": "../public/assets/useForm-Cs18dAFp.js"
  },
  "/assets/users-Dehov89l.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"19d-S3dej/i9IwlP5Mqwxh1a3c0rkRE"',
    "mtime": "2026-01-05T22:39:38.059Z",
    "size": 413,
    "path": "../public/assets/users-Dehov89l.js"
  },
  "/assets/vercel-ai-sdk-CBBeW5dD.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"1919-+LMiVQvPLackfqKAzwdHROnsvaw"',
    "mtime": "2026-01-05T22:39:38.063Z",
    "size": 6425,
    "path": "../public/assets/vercel-ai-sdk-CBBeW5dD.js"
  },
  "/assets/webhooks-BTapsLJ5.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"a11-SdcmCWSs/tejUqkLHhLU/wxaV58"',
    "mtime": "2026-01-05T22:39:38.059Z",
    "size": 2577,
    "path": "../public/assets/webhooks-BTapsLJ5.js"
  },
  "/assets/welcome-BunOneyi.js": {
    "type": "text/javascript; charset=utf-8",
    "etag": '"f6d-LfSeto4T3kAhvDpzEg4YGFTyoZA"',
    "mtime": "2026-01-05T22:39:38.063Z",
    "size": 3949,
    "path": "../public/assets/welcome-BunOneyi.js"
  },
  "/icons/connectors/airtable.svg": {
    "type": "image/svg+xml",
    "etag": '"4ea-Mra2L8gAVO8usMGZfcd4BP9lybM"',
    "mtime": "2026-01-05T22:39:37.828Z",
    "size": 1258,
    "path": "../public/icons/connectors/airtable.svg"
  },
  "/icons/connectors/asana.svg": {
    "type": "image/svg+xml",
    "etag": '"2c6-jRaBjGPGbAOQnvx3VC/TV5Q6J8U"',
    "mtime": "2026-01-05T22:39:37.828Z",
    "size": 710,
    "path": "../public/icons/connectors/asana.svg"
  },
  "/icons/connectors/attio-light.svg": {
    "type": "image/svg+xml",
    "etag": '"69a-VWU4VoclzIWbxRAx7lhu8D0Xpuk"',
    "mtime": "2026-01-05T22:39:37.828Z",
    "size": 1690,
    "path": "../public/icons/connectors/attio-light.svg"
  },
  "/icons/connectors/attio.svg": {
    "type": "image/svg+xml",
    "etag": '"649-D6QfuDt9x+cQFciiDJwlz0uquig"',
    "mtime": "2026-01-05T22:39:37.829Z",
    "size": 1609,
    "path": "../public/icons/connectors/attio.svg"
  },
  "/icons/connectors/bitbucket.svg": {
    "type": "image/svg+xml",
    "etag": '"324-/d3jKmBArN6NDaHyJVrVRJOE700"',
    "mtime": "2026-01-05T22:39:37.829Z",
    "size": 804,
    "path": "../public/icons/connectors/bitbucket.svg"
  },
  "/icons/connectors/box.svg": {
    "type": "image/svg+xml",
    "etag": '"568-A5S+Uz7eoz5EnutV2Eugk4tXu4U"',
    "mtime": "2026-01-05T22:39:37.829Z",
    "size": 1384,
    "path": "../public/icons/connectors/box.svg"
  },
  "/icons/connectors/clickup-light.svg": {
    "type": "image/svg+xml",
    "etag": '"5f1-It1Bd0iFn04GL9EbLsed2KywTAQ"',
    "mtime": "2026-01-05T22:39:37.829Z",
    "size": 1521,
    "path": "../public/icons/connectors/clickup-light.svg"
  },
  "/icons/connectors/clickup.svg": {
    "type": "image/svg+xml",
    "etag": '"5f1-It1Bd0iFn04GL9EbLsed2KywTAQ"',
    "mtime": "2026-01-05T22:39:37.829Z",
    "size": 1521,
    "path": "../public/icons/connectors/clickup.svg"
  },
  "/icons/connectors/confluence.svg": {
    "type": "image/svg+xml",
    "etag": '"a13-3JYpHm0fG/hB3N/RYwG169wiuPM"',
    "mtime": "2026-01-05T22:39:37.829Z",
    "size": 2579,
    "path": "../public/icons/connectors/confluence.svg"
  },
  "/icons/connectors/ctti.svg": {
    "type": "image/svg+xml",
    "etag": '"33f-WVavSrd4T2BWJYiAX+ir8VtrsMc"',
    "mtime": "2026-01-05T22:39:37.829Z",
    "size": 831,
    "path": "../public/icons/connectors/ctti.svg"
  },
  "/icons/connectors/dropbox.svg": {
    "type": "image/svg+xml",
    "etag": '"277-G4kS9ITw3fTQPPTFA3pZDTsDMio"',
    "mtime": "2026-01-05T22:39:37.829Z",
    "size": 631,
    "path": "../public/icons/connectors/dropbox.svg"
  },
  "/icons/connectors/elasticsearch.svg": {
    "type": "image/svg+xml",
    "etag": '"47c-LmnyiBD/2Z049gXgc0IifVfss/M"',
    "mtime": "2026-01-05T22:39:37.829Z",
    "size": 1148,
    "path": "../public/icons/connectors/elasticsearch.svg"
  },
  "/icons/connectors/excel.svg": {
    "type": "image/svg+xml",
    "etag": '"1822-5AWJV7fJtBv3zZT1WsrN8BSC7RM"',
    "mtime": "2026-01-05T22:39:37.829Z",
    "size": 6178,
    "path": "../public/icons/connectors/excel.svg"
  },
  "/icons/connectors/github-light.svg": {
    "type": "image/svg+xml",
    "etag": '"3f5-Xzlnmt8uhckj38y53gD8gwJbarU"',
    "mtime": "2026-01-05T22:39:37.829Z",
    "size": 1013,
    "path": "../public/icons/connectors/github-light.svg"
  },
  "/icons/connectors/github.svg": {
    "type": "image/svg+xml",
    "etag": '"3f7-mCReC8HQPeF04EkAYQ3UpDhP2yU"',
    "mtime": "2026-01-05T22:39:37.830Z",
    "size": 1015,
    "path": "../public/icons/connectors/github.svg"
  },
  "/icons/connectors/gitlab.svg": {
    "type": "image/svg+xml",
    "etag": '"8f6-p+IFAZlLLR65llEUcA09tumknLM"',
    "mtime": "2026-01-05T22:39:37.830Z",
    "size": 2294,
    "path": "../public/icons/connectors/gitlab.svg"
  },
  "/icons/connectors/gmail.svg": {
    "type": "image/svg+xml",
    "etag": '"346-fsVAgP8mIUBTQ2T9o2KZerM8Pwo"',
    "mtime": "2026-01-05T22:39:37.830Z",
    "size": 838,
    "path": "../public/icons/connectors/gmail.svg"
  },
  "/icons/connectors/google_calendar.svg": {
    "type": "image/svg+xml",
    "etag": '"935-Ux1WasdWPIpgm0seuyc+1tAp5BY"',
    "mtime": "2026-01-05T22:39:37.830Z",
    "size": 2357,
    "path": "../public/icons/connectors/google_calendar.svg"
  },
  "/icons/connectors/google_docs.svg": {
    "type": "image/svg+xml",
    "etag": '"2bc-NAgQ1IwQAz78U6lCxrZNd7PdsEw"',
    "mtime": "2026-01-05T22:39:37.830Z",
    "size": 700,
    "path": "../public/icons/connectors/google_docs.svg"
  },
  "/icons/connectors/google_drive.svg": {
    "type": "image/svg+xml",
    "etag": '"50d-ESS4n6gf97SiEmmuBncwi7lWRqs"',
    "mtime": "2026-01-05T22:39:37.830Z",
    "size": 1293,
    "path": "../public/icons/connectors/google_drive.svg"
  },
  "/icons/connectors/google_slides.svg": {
    "type": "image/svg+xml",
    "etag": '"2b2-qb688hjG5fHXCSCbL0baTRp6+B0"',
    "mtime": "2026-01-05T22:39:37.830Z",
    "size": 690,
    "path": "../public/icons/connectors/google_slides.svg"
  },
  "/icons/connectors/hubspot.svg": {
    "type": "image/svg+xml",
    "etag": '"5bd-RNPfluqVI648YstvWG0KPq6TT5I"',
    "mtime": "2026-01-05T22:39:37.830Z",
    "size": 1469,
    "path": "../public/icons/connectors/hubspot.svg"
  },
  "/icons/connectors/intercom.svg": {
    "type": "image/svg+xml",
    "etag": '"42a-l+ZgNynmI2HMyIJPvnjj1jo2av8"',
    "mtime": "2026-01-05T22:39:37.830Z",
    "size": 1066,
    "path": "../public/icons/connectors/intercom.svg"
  },
  "/icons/connectors/jira.svg": {
    "type": "image/svg+xml",
    "etag": '"443-eIyhIrC3n4o6Awf7a+S9269NxXc"',
    "mtime": "2026-01-05T22:39:37.830Z",
    "size": 1091,
    "path": "../public/icons/connectors/jira.svg"
  },
  "/icons/connectors/linear-light.svg": {
    "type": "image/svg+xml",
    "etag": '"364-+0jG3andIxUBPRuwjzF6uFNAsv8"',
    "mtime": "2026-01-05T22:39:37.830Z",
    "size": 868,
    "path": "../public/icons/connectors/linear-light.svg"
  },
  "/icons/connectors/linear.svg": {
    "type": "image/svg+xml",
    "etag": '"364-Sa+iDGnoAN0lCh0DOqipWvtvIz8"',
    "mtime": "2026-01-05T22:39:37.831Z",
    "size": 868,
    "path": "../public/icons/connectors/linear.svg"
  },
  "/icons/connectors/monday.svg": {
    "type": "image/svg+xml",
    "etag": '"5d6-elkSX5PtL/Ta/rlT8e5cJuu37uo"',
    "mtime": "2026-01-05T22:39:37.831Z",
    "size": 1494,
    "path": "../public/icons/connectors/monday.svg"
  },
  "/icons/connectors/mysql.svg": {
    "type": "image/svg+xml",
    "etag": '"13cc-XeXqHWDt+6pqVVaL5bPJ7+DymG8"',
    "mtime": "2026-01-05T22:39:37.831Z",
    "size": 5068,
    "path": "../public/icons/connectors/mysql.svg"
  },
  "/icons/connectors/notion-light.svg": {
    "type": "image/svg+xml",
    "etag": '"3dd-VdU+00azo3CnlASmtnfLKEWfLH4"',
    "mtime": "2026-01-05T22:39:37.831Z",
    "size": 989,
    "path": "../public/icons/connectors/notion-light.svg"
  },
  "/icons/connectors/notion.svg": {
    "type": "image/svg+xml",
    "etag": '"3e4-NbUvt8jqcIRzkUzdGg9/vnBiKME"',
    "mtime": "2026-01-05T22:39:37.831Z",
    "size": 996,
    "path": "../public/icons/connectors/notion.svg"
  },
  "/icons/connectors/onedrive.svg": {
    "type": "image/svg+xml",
    "etag": '"200f-ReEk3XRY2ujG4ueDVM/UNK5UQNs"',
    "mtime": "2026-01-05T22:39:37.831Z",
    "size": 8207,
    "path": "../public/icons/connectors/onedrive.svg"
  },
  "/icons/connectors/onenote.svg": {
    "type": "image/svg+xml",
    "etag": '"154d-Z1nh6l5ZTLUFooeuEkFO0YEATcY"',
    "mtime": "2026-01-05T22:39:37.831Z",
    "size": 5453,
    "path": "../public/icons/connectors/onenote.svg"
  },
  "/icons/connectors/oracle.svg": {
    "type": "image/svg+xml",
    "etag": '"91ec-IDNlPYSdEUGSck3KYGI6UPlP9Ow"',
    "mtime": "2026-01-05T22:39:37.832Z",
    "size": 37356,
    "path": "../public/icons/connectors/oracle.svg"
  },
  "/icons/connectors/outlook_calendar.svg": {
    "type": "image/svg+xml",
    "etag": '"230-LwhISle7OSjaISA5ZSuajaxyHvE"',
    "mtime": "2026-01-05T22:39:37.832Z",
    "size": 560,
    "path": "../public/icons/connectors/outlook_calendar.svg"
  },
  "/icons/connectors/outlook_mail.svg": {
    "type": "image/svg+xml",
    "etag": '"333c-DProSWNVAI5tCVNmpTWCjeygqkg"',
    "mtime": "2026-01-05T22:39:37.832Z",
    "size": 13116,
    "path": "../public/icons/connectors/outlook_mail.svg"
  },
  "/icons/connectors/postgresql.svg": {
    "type": "image/svg+xml",
    "etag": '"116e-tmdQO7AjJ2bvzDiH+h8B6BeagYU"',
    "mtime": "2026-01-05T22:39:37.832Z",
    "size": 4462,
    "path": "../public/icons/connectors/postgresql.svg"
  },
  "/icons/connectors/salesforce.svg": {
    "type": "image/svg+xml",
    "etag": '"25ea-H1GnHKVXrXTwkIaXHZ3pI7C0XoA"',
    "mtime": "2026-01-05T22:39:37.832Z",
    "size": 9706,
    "path": "../public/icons/connectors/salesforce.svg"
  },
  "/icons/connectors/sharepoint.svg": {
    "type": "image/svg+xml",
    "etag": '"1d95-ZOW59cvinE8TbxMd9g7BD05Qdd4"',
    "mtime": "2026-01-05T22:39:37.832Z",
    "size": 7573,
    "path": "../public/icons/connectors/sharepoint.svg"
  },
  "/icons/connectors/slack.svg": {
    "type": "image/svg+xml",
    "etag": '"5e8-ZxG1aZhgBJA4yZW4tZB9lmgcpKU"',
    "mtime": "2026-01-05T22:39:37.832Z",
    "size": 1512,
    "path": "../public/icons/connectors/slack.svg"
  },
  "/icons/connectors/sql_server.svg": {
    "type": "image/svg+xml",
    "etag": '"60b0-8Wxeypamma8bKRofkAxqJp/zWQw"',
    "mtime": "2026-01-05T22:39:37.832Z",
    "size": 24752,
    "path": "../public/icons/connectors/sql_server.svg"
  },
  "/icons/connectors/sqlite.svg": {
    "type": "image/svg+xml",
    "etag": '"2dc9-hpW1yfMJuP6CiaXlvJV9mLLaajk"',
    "mtime": "2026-01-05T22:39:37.833Z",
    "size": 11721,
    "path": "../public/icons/connectors/sqlite.svg"
  },
  "/icons/connectors/stripe.svg": {
    "type": "image/svg+xml",
    "etag": '"644-f1RjZNWWNhEsO6u505i7o9Y/cFE"',
    "mtime": "2026-01-05T22:39:37.833Z",
    "size": 1604,
    "path": "../public/icons/connectors/stripe.svg"
  },
  "/icons/connectors/teams.svg": {
    "type": "image/svg+xml",
    "etag": '"190d-kwcixFbbUyk41Mp6NNGkYj6ERpg"',
    "mtime": "2026-01-05T22:39:37.833Z",
    "size": 6413,
    "path": "../public/icons/connectors/teams.svg"
  },
  "/icons/connectors/todoist.svg": {
    "type": "image/svg+xml",
    "etag": '"78e-A27RhKj619ERklOWJF0WU8Rkjms"',
    "mtime": "2026-01-05T22:39:37.833Z",
    "size": 1934,
    "path": "../public/icons/connectors/todoist.svg"
  },
  "/icons/connectors/trello.svg": {
    "type": "image/svg+xml",
    "etag": '"1c0-rXwXaCTqtJw0cpmKvEGkzZe3M+U"',
    "mtime": "2026-01-05T22:39:37.833Z",
    "size": 448,
    "path": "../public/icons/connectors/trello.svg"
  },
  "/icons/connectors/word.svg": {
    "type": "image/svg+xml",
    "etag": '"13b3-lVUUe7WtIisRa3VI0SageosC/FA"',
    "mtime": "2026-01-05T22:39:37.833Z",
    "size": 5043,
    "path": "../public/icons/connectors/word.svg"
  },
  "/icons/connectors/zendesk-light.svg": {
    "type": "image/svg+xml",
    "etag": '"130-GtiHH0F27K/SUjN3ndJiiqChB5I"',
    "mtime": "2026-01-05T22:39:37.833Z",
    "size": 304,
    "path": "../public/icons/connectors/zendesk-light.svg"
  },
  "/icons/connectors/zendesk.svg": {
    "type": "image/svg+xml",
    "etag": '"130-hzzy7+75XSmTD7InsDVBsQAUq48"',
    "mtime": "2026-01-05T22:39:37.833Z",
    "size": 304,
    "path": "../public/icons/connectors/zendesk.svg"
  },
  "/icons/connectors/zoho_crm.svg": {
    "type": "image/svg+xml",
    "etag": '"b94-BzgUuPFrltfkyZ5LAo6CUvzdzu4"',
    "mtime": "2026-01-05T22:39:37.833Z",
    "size": 2964,
    "path": "../public/icons/connectors/zoho_crm.svg"
  }
};
function readAsset(id) {
  const serverDir = dirname(fileURLToPath(globalThis.__nitro_main__));
  return promises.readFile(resolve(serverDir, assets[id].path));
}
const publicAssetBases = {};
function isPublicAssetURL(id = "") {
  if (assets[id]) {
    return true;
  }
  for (const base in publicAssetBases) {
    if (id.startsWith(base)) {
      return true;
    }
  }
  return false;
}
function getAsset(id) {
  return assets[id];
}
const METHODS = /* @__PURE__ */ new Set(["HEAD", "GET"]);
const EncodingMap = {
  gzip: ".gz",
  br: ".br"
};
const _fq2foc = defineHandler((event) => {
  if (event.req.method && !METHODS.has(event.req.method)) {
    return;
  }
  let id = decodePath(withLeadingSlash(withoutTrailingSlash(event.url.pathname)));
  let asset;
  const encodingHeader = event.req.headers.get("accept-encoding") || "";
  const encodings = [...encodingHeader.split(",").map((e) => EncodingMap[e.trim()]).filter(Boolean).sort(), ""];
  if (encodings.length > 1) {
    event.res.headers.append("Vary", "Accept-Encoding");
  }
  for (const encoding of encodings) {
    for (const _id of [id + encoding, joinURL(id, "index.html" + encoding)]) {
      const _asset = getAsset(_id);
      if (_asset) {
        asset = _asset;
        id = _id;
        break;
      }
    }
  }
  if (!asset) {
    if (isPublicAssetURL(id)) {
      event.res.headers.delete("Cache-Control");
      throw new HTTPError({ status: 404 });
    }
    return;
  }
  const ifNotMatch = event.req.headers.get("if-none-match") === asset.etag;
  if (ifNotMatch) {
    event.res.status = 304;
    event.res.statusText = "Not Modified";
    return "";
  }
  const ifModifiedSinceH = event.req.headers.get("if-modified-since");
  const mtimeDate = new Date(asset.mtime);
  if (ifModifiedSinceH && asset.mtime && new Date(ifModifiedSinceH) >= mtimeDate) {
    event.res.status = 304;
    event.res.statusText = "Not Modified";
    return "";
  }
  if (asset.type) {
    event.res.headers.set("Content-Type", asset.type);
  }
  if (asset.etag && !event.res.headers.has("ETag")) {
    event.res.headers.set("ETag", asset.etag);
  }
  if (asset.mtime && !event.res.headers.has("Last-Modified")) {
    event.res.headers.set("Last-Modified", mtimeDate.toUTCString());
  }
  if (asset.encoding && !event.res.headers.has("Content-Encoding")) {
    event.res.headers.set("Content-Encoding", asset.encoding);
  }
  if (asset.size > 0 && !event.res.headers.has("Content-Length")) {
    event.res.headers.set("Content-Length", asset.size.toString());
  }
  return readAsset(id);
});
const findRouteRules = /* @__PURE__ */ (() => {
  const $0 = [{ name: "headers", route: "/assets/**", handler: headers, options: { "cache-control": "public, max-age=31536000, immutable" } }];
  return (m, p) => {
    let r = [];
    if (p.charCodeAt(p.length - 1) === 47) p = p.slice(0, -1) || "/";
    let s = p.split("/");
    s.length - 1;
    if (s[1] === "assets") {
      r.unshift({ data: $0, params: { "_": s.slice(2).join("/") } });
    }
    return r;
  };
})();
const _lazy_CWDL_C = defineLazyEventHandler(() => Promise.resolve().then(function() {
  return ssrRenderer$1;
}));
const findRoute = /* @__PURE__ */ (() => {
  const data = { route: "/**", handler: _lazy_CWDL_C };
  return ((_m, p) => {
    return { data, params: { "_": p.slice(1) } };
  });
})();
const globalMiddleware = [
  toEventHandler(_fq2foc)
].filter(Boolean);
function useNitroApp() {
  return useNitroApp.__instance__ ??= initNitroApp();
}
function initNitroApp() {
  const nitroApp2 = createNitroApp();
  globalThis.__nitro__ = nitroApp2;
  return nitroApp2;
}
function createNitroApp() {
  const hooks = void 0;
  const captureError = (error, errorCtx) => {
    if (errorCtx?.event) {
      const errors = errorCtx.event.req.context?.nitro?.errors;
      if (errors) {
        errors.push({
          error,
          context: errorCtx
        });
      }
    }
  };
  const h3App = createH3App({ onError(error, event) {
    return errorHandler(error, event);
  } });
  let appHandler = (req) => {
    req.context ||= {};
    req.context.nitro = req.context.nitro || { errors: [] };
    return h3App.fetch(req);
  };
  const app = {
    fetch: appHandler,
    h3: h3App,
    hooks,
    captureError
  };
  return app;
}
function createH3App(config) {
  const h3App = new H3Core(config);
  h3App["~findRoute"] = (event) => findRoute(event.req.method, event.url.pathname);
  h3App["~middleware"].push(...globalMiddleware);
  {
    h3App["~getMiddleware"] = (event, route) => {
      const pathname = event.url.pathname;
      const method = event.req.method;
      const middleware = [];
      {
        const routeRules = getRouteRules(method, pathname);
        event.context.routeRules = routeRules?.routeRules;
        if (routeRules?.routeRuleMiddleware.length) {
          middleware.push(...routeRules.routeRuleMiddleware);
        }
      }
      middleware.push(...h3App["~middleware"]);
      if (route?.data?.middleware?.length) {
        middleware.push(...route.data.middleware);
      }
      return middleware;
    };
  }
  return h3App;
}
function getRouteRules(method, pathname) {
  const m = findRouteRules(method, pathname);
  if (!m?.length) {
    return { routeRuleMiddleware: [] };
  }
  const routeRules = {};
  for (const layer of m) {
    for (const rule of layer.data) {
      const currentRule = routeRules[rule.name];
      if (currentRule) {
        if (rule.options === false) {
          delete routeRules[rule.name];
          continue;
        }
        if (typeof currentRule.options === "object" && typeof rule.options === "object") {
          currentRule.options = {
            ...currentRule.options,
            ...rule.options
          };
        } else {
          currentRule.options = rule.options;
        }
        currentRule.route = rule.route;
        currentRule.params = {
          ...currentRule.params,
          ...layer.params
        };
      } else if (rule.options !== false) {
        routeRules[rule.name] = {
          ...rule,
          params: layer.params
        };
      }
    }
  }
  const middleware = [];
  for (const rule of Object.values(routeRules)) {
    if (rule.options === false || !rule.handler) {
      continue;
    }
    middleware.push(rule.handler(rule));
  }
  return {
    routeRules,
    routeRuleMiddleware: middleware
  };
}
function _captureError(error, type) {
  console.error(`[${type}]`, error);
  useNitroApp().captureError?.(error, { tags: [type] });
}
function trapUnhandledErrors() {
  process.on("unhandledRejection", (error) => _captureError(error, "unhandledRejection"));
  process.on("uncaughtException", (error) => _captureError(error, "uncaughtException"));
}
const port = Number.parseInt(process.env.NITRO_PORT || process.env.PORT || "") || 3e3;
const host = process.env.NITRO_HOST || process.env.HOST;
const cert = process.env.NITRO_SSL_CERT;
const key = process.env.NITRO_SSL_KEY;
const nitroApp = useNitroApp();
serve({
  port,
  hostname: host,
  tls: cert && key ? {
    cert,
    key
  } : void 0,
  fetch: nitroApp.fetch
});
trapUnhandledErrors();
const nodeServer = {};
function fetchViteEnv(viteEnvName, input, init) {
  const envs = globalThis.__nitro_vite_envs__ || {};
  const viteEnv = envs[viteEnvName];
  if (!viteEnv) {
    throw HTTPError.status(404);
  }
  return Promise.resolve(viteEnv.fetch(toRequest(input, init)));
}
function ssrRenderer({ req }) {
  return fetchViteEnv("ssr", req);
}
const ssrRenderer$1 = /* @__PURE__ */ Object.freeze({
  __proto__: null,
  default: ssrRenderer
});
export {
  NullProtoObj as N,
  nodeServer as default
};
