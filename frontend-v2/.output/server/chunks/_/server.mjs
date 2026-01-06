import { createMemoryHistory } from "@tanstack/history";
import { mergeHeaders } from "@tanstack/router-core/ssr/client";
import { createSerializationAdapter, createRawStreamRPCPlugin, isNotFound, isRedirect, isResolvedRedirect, executeRewriteInput, defaultSerovalPlugins, makeSerovalPlugin, rootRouteId } from "@tanstack/router-core";
import { getOrigin, attachRouterServerSsrUtils } from "@tanstack/router-core/ssr/server";
import { AsyncLocalStorage } from "node:async_hooks";
import { N as NullProtoObj } from "../../index.mjs";
import invariant from "tiny-invariant";
import { toCrossJSONStream, fromJSON, toCrossJSONAsync } from "seroval";
import { jsx } from "react/jsx-runtime";
import { defineHandlerCallback, renderRouterToStream } from "@tanstack/react-router/ssr/server";
import { RouterProvider } from "@tanstack/react-router";
import "node:http";
import "node:stream";
import "node:https";
import "node:http2";
import "node:fs";
import "node:url";
import "node:path";
function lazyInherit(target, source, sourceKey) {
  for (const key of [...Object.getOwnPropertyNames(source), ...Object.getOwnPropertySymbols(source)]) {
    if (key === "constructor") continue;
    const targetDesc = Object.getOwnPropertyDescriptor(target, key);
    const desc = Object.getOwnPropertyDescriptor(source, key);
    let modified = false;
    if (desc.get) {
      modified = true;
      desc.get = targetDesc?.get || function() {
        return this[sourceKey][key];
      };
    }
    if (desc.set) {
      modified = true;
      desc.set = targetDesc?.set || function(value) {
        this[sourceKey][key] = value;
      };
    }
    if (!targetDesc?.value && typeof desc.value === "function") {
      modified = true;
      desc.value = function(...args) {
        return this[sourceKey][key](...args);
      };
    }
    if (modified) Object.defineProperty(target, key, desc);
  }
}
const FastURL = /* @__PURE__ */ (() => {
  const NativeURL = globalThis.URL;
  const FastURL$1 = class URL {
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
  lazyInherit(FastURL$1.prototype, NativeURL.prototype, "_url");
  Object.setPrototypeOf(FastURL$1.prototype, NativeURL.prototype);
  Object.setPrototypeOf(FastURL$1, NativeURL);
  return FastURL$1;
})();
const NodeResponse = /* @__PURE__ */ (() => {
  const NativeResponse = globalThis.Response;
  const STATUS_CODES = globalThis.process?.getBuiltinModule?.("node:http")?.STATUS_CODES || {};
  class NodeResponse$1 {
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
      const headers = [];
      const initHeaders = this.#init?.headers;
      const headerEntries = this.#response?.headers || this.#headers || (initHeaders ? Array.isArray(initHeaders) ? initHeaders : initHeaders?.entries ? initHeaders.entries() : Object.entries(initHeaders).map(([k, v]) => [k.toLowerCase(), v]) : void 0);
      let hasContentTypeHeader;
      let hasContentLength;
      if (headerEntries) for (const [key, value] of headerEntries) {
        if (Array.isArray(value)) for (const v of value) headers.push([key, v]);
        else headers.push([key, value]);
        if (key === "content-type") hasContentTypeHeader = true;
        else if (key === "content-length") hasContentLength = true;
      }
      if (contentType && !hasContentTypeHeader) headers.push(["content-type", contentType]);
      if (contentLength && !hasContentLength) headers.push(["content-length", String(contentLength)]);
      this.#init = void 0;
      this.#headers = void 0;
      this.#response = void 0;
      this.#body = void 0;
      return {
        status,
        statusText,
        headers,
        body
      };
    }
  }
  lazyInherit(NodeResponse$1.prototype, NativeResponse.prototype, "_response");
  Object.setPrototypeOf(NodeResponse$1, NativeResponse);
  Object.setPrototypeOf(NodeResponse$1.prototype, NativeResponse.prototype);
  return NodeResponse$1;
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
  event[kEventRes] = void 0;
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
    const headers = new Headers({
      "content-type": val.type,
      "content-length": val.size.toString()
    });
    let filename = val.name;
    if (filename) {
      filename = encodeURIComponent(filename);
      headers.set("content-disposition", `filename="${filename}"; filename*=UTF-8''${filename}`);
    }
    return {
      body: val.stream(),
      headers
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
function StartServer(props) {
  return /* @__PURE__ */ jsx(RouterProvider, { router: props.router });
}
const defaultStreamHandler = defineHandlerCallback(
  ({ request, router, responseHeaders }) => renderRouterToStream({
    request,
    router,
    responseHeaders,
    children: /* @__PURE__ */ jsx(StartServer, { router })
  })
);
const TSS_FORMDATA_CONTEXT = "__TSS_CONTEXT";
const TSS_SERVER_FUNCTION = /* @__PURE__ */ Symbol.for("TSS_SERVER_FUNCTION");
const X_TSS_SERIALIZED = "x-tss-serialized";
const X_TSS_RAW_RESPONSE = "x-tss-raw";
const TSS_CONTENT_TYPE_FRAMED = "application/x-tss-framed";
const FrameType = {
  /** Seroval JSON chunk (NDJSON line) */
  JSON: 0,
  /** Raw stream data chunk */
  CHUNK: 1,
  /** Raw stream end (EOF) */
  END: 2,
  /** Raw stream error */
  ERROR: 3
};
const FRAME_HEADER_SIZE = 9;
const TSS_FRAMED_PROTOCOL_VERSION = 1;
const TSS_CONTENT_TYPE_FRAMED_VERSIONED = `${TSS_CONTENT_TYPE_FRAMED}; v=${TSS_FRAMED_PROTOCOL_VERSION}`;
const GLOBAL_STORAGE_KEY = /* @__PURE__ */ Symbol.for("tanstack-start:start-storage-context");
const globalObj$1 = globalThis;
if (!globalObj$1[GLOBAL_STORAGE_KEY]) {
  globalObj$1[GLOBAL_STORAGE_KEY] = new AsyncLocalStorage();
}
const startStorage = globalObj$1[GLOBAL_STORAGE_KEY];
async function runWithStartContext(context, fn) {
  return startStorage.run(context, fn);
}
function getStartContext(opts) {
  const context = startStorage.getStore();
  if (!context && opts?.throwIfNotFound !== false) {
    throw new Error(
      `No Start context found in AsyncLocalStorage. Make sure you are using the function within the server runtime.`
    );
  }
  return context;
}
const getStartOptions = () => getStartContext().startOptions;
function isSafeKey(key) {
  return key !== "__proto__" && key !== "constructor" && key !== "prototype";
}
function safeObjectMerge(target, source) {
  const result = /* @__PURE__ */ Object.create(null);
  if (target) {
    for (const key of Object.keys(target)) {
      if (isSafeKey(key)) result[key] = target[key];
    }
  }
  if (source && typeof source === "object") {
    for (const key of Object.keys(source)) {
      if (isSafeKey(key)) result[key] = source[key];
    }
  }
  return result;
}
function createNullProtoObject(source) {
  if (!source) return /* @__PURE__ */ Object.create(null);
  const obj = /* @__PURE__ */ Object.create(null);
  for (const key of Object.keys(source)) {
    if (isSafeKey(key)) obj[key] = source[key];
  }
  return obj;
}
function flattenMiddlewares(middlewares, maxDepth = 100) {
  const seen = /* @__PURE__ */ new Set();
  const flattened = [];
  const recurse = (middleware, depth) => {
    if (depth > maxDepth) {
      throw new Error(
        `Middleware nesting depth exceeded maximum of ${maxDepth}. Check for circular references.`
      );
    }
    middleware.forEach((m) => {
      if (m.options.middleware) {
        recurse(m.options.middleware, depth + 1);
      }
      if (!seen.has(m)) {
        seen.add(m);
        flattened.push(m);
      }
    });
  };
  recurse(middlewares, 0);
  return flattened;
}
function getDefaultSerovalPlugins() {
  const start = getStartOptions();
  const adapters = start?.serializationAdapters;
  return [
    ...adapters?.map(makeSerovalPlugin) ?? [],
    ...defaultSerovalPlugins
  ];
}
const GLOBAL_EVENT_STORAGE_KEY = /* @__PURE__ */ Symbol.for("tanstack-start:event-storage");
const globalObj = globalThis;
if (!globalObj[GLOBAL_EVENT_STORAGE_KEY]) {
  globalObj[GLOBAL_EVENT_STORAGE_KEY] = new AsyncLocalStorage();
}
const eventStorage = globalObj[GLOBAL_EVENT_STORAGE_KEY];
function isPromiseLike(value) {
  return typeof value.then === "function";
}
function getSetCookieValues(headers) {
  const headersWithSetCookie = headers;
  if (typeof headersWithSetCookie.getSetCookie === "function") {
    return headersWithSetCookie.getSetCookie();
  }
  const value = headers.get("set-cookie");
  return value ? [value] : [];
}
function mergeEventResponseHeaders(response, event) {
  if (response.ok) {
    return;
  }
  const eventSetCookies = getSetCookieValues(event.res.headers);
  if (eventSetCookies.length === 0) {
    return;
  }
  const responseSetCookies = getSetCookieValues(response.headers);
  response.headers.delete("set-cookie");
  for (const cookie of responseSetCookies) {
    response.headers.append("set-cookie", cookie);
  }
  for (const cookie of eventSetCookies) {
    response.headers.append("set-cookie", cookie);
  }
}
function attachResponseHeaders(value, event) {
  if (isPromiseLike(value)) {
    return value.then((resolved) => {
      if (resolved instanceof Response) {
        mergeEventResponseHeaders(resolved, event);
      }
      return resolved;
    });
  }
  if (value instanceof Response) {
    mergeEventResponseHeaders(value, event);
  }
  return value;
}
function requestHandler(handler) {
  return (request, requestOpts) => {
    const h3Event = new H3Event(request);
    const response = eventStorage.run(
      { h3Event },
      () => handler(request, requestOpts)
    );
    return toResponse(attachResponseHeaders(response, h3Event), h3Event);
  };
}
function getH3Event() {
  const event = eventStorage.getStore();
  if (!event) {
    throw new Error(
      `No StartEvent found in AsyncLocalStorage. Make sure you are using the function within the server runtime.`
    );
  }
  return event.h3Event;
}
function getResponse() {
  const event = getH3Event();
  return event.res;
}
async function getStartManifest() {
  const { tsrStartManifest } = await import("./_tanstack-start-manifest_v-BZNpCRAK.mjs");
  const startManifest = tsrStartManifest();
  const rootRoute = startManifest.routes[rootRouteId] = startManifest.routes[rootRouteId] || {};
  rootRoute.assets = rootRoute.assets || [];
  let script = `import('${startManifest.clientEntry}')`;
  rootRoute.assets.push({
    tag: "script",
    attrs: {
      type: "module",
      async: true
    },
    children: script
  });
  const manifest2 = {
    routes: Object.fromEntries(
      Object.entries(startManifest.routes).flatMap(([k, v]) => {
        const result = {};
        let hasData = false;
        if (v.preloads && v.preloads.length > 0) {
          result["preloads"] = v.preloads;
          hasData = true;
        }
        if (v.assets && v.assets.length > 0) {
          result["assets"] = v.assets;
          hasData = true;
        }
        if (!hasData) {
          return [];
        }
        return [[k, result]];
      })
    )
  };
  return manifest2;
}
const textEncoder$1 = new TextEncoder();
const EMPTY_PAYLOAD = new Uint8Array(0);
function encodeFrame(type, streamId, payload) {
  const frame = new Uint8Array(FRAME_HEADER_SIZE + payload.length);
  frame[0] = type;
  frame[1] = streamId >>> 24 & 255;
  frame[2] = streamId >>> 16 & 255;
  frame[3] = streamId >>> 8 & 255;
  frame[4] = streamId & 255;
  frame[5] = payload.length >>> 24 & 255;
  frame[6] = payload.length >>> 16 & 255;
  frame[7] = payload.length >>> 8 & 255;
  frame[8] = payload.length & 255;
  frame.set(payload, FRAME_HEADER_SIZE);
  return frame;
}
function encodeJSONFrame(json) {
  return encodeFrame(FrameType.JSON, 0, textEncoder$1.encode(json));
}
function encodeChunkFrame(streamId, chunk) {
  return encodeFrame(FrameType.CHUNK, streamId, chunk);
}
function encodeEndFrame(streamId) {
  return encodeFrame(FrameType.END, streamId, EMPTY_PAYLOAD);
}
function encodeErrorFrame(streamId, error) {
  const message = error instanceof Error ? error.message : String(error ?? "Unknown error");
  return encodeFrame(FrameType.ERROR, streamId, textEncoder$1.encode(message));
}
function createMultiplexedStream(jsonStream, rawStreams) {
  let activePumps = 1 + rawStreams.size;
  let controllerRef = null;
  let cancelled = false;
  const cancelReaders = [];
  const safeEnqueue = (chunk) => {
    if (cancelled || !controllerRef) return;
    try {
      controllerRef.enqueue(chunk);
    } catch {
    }
  };
  const safeError = (err) => {
    if (cancelled || !controllerRef) return;
    try {
      controllerRef.error(err);
    } catch {
    }
  };
  const safeClose = () => {
    if (cancelled || !controllerRef) return;
    try {
      controllerRef.close();
    } catch {
    }
  };
  const checkComplete = () => {
    activePumps--;
    if (activePumps === 0) {
      safeClose();
    }
  };
  return new ReadableStream({
    start(controller) {
      controllerRef = controller;
      cancelReaders.length = 0;
      const pumpJSON = async () => {
        const reader = jsonStream.getReader();
        cancelReaders.push(() => {
          reader.cancel().catch(() => {
          });
        });
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (cancelled) break;
            if (done) break;
            safeEnqueue(encodeJSONFrame(value));
          }
        } catch (error) {
          safeError(error);
        } finally {
          reader.releaseLock();
          checkComplete();
        }
      };
      const pumpRawStream = async (streamId, stream) => {
        const reader = stream.getReader();
        cancelReaders.push(() => {
          reader.cancel().catch(() => {
          });
        });
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (cancelled) break;
            if (done) {
              safeEnqueue(encodeEndFrame(streamId));
              break;
            }
            safeEnqueue(encodeChunkFrame(streamId, value));
          }
        } catch (error) {
          safeEnqueue(encodeErrorFrame(streamId, error));
        } finally {
          reader.releaseLock();
          checkComplete();
        }
      };
      pumpJSON();
      for (const [streamId, stream] of rawStreams) {
        pumpRawStream(streamId, stream);
      }
    },
    cancel() {
      cancelled = true;
      controllerRef = null;
      for (const cancelReader of cancelReaders) {
        cancelReader();
      }
      cancelReaders.length = 0;
    }
  });
}
const manifest = {};
async function getServerFnById(id) {
  const serverFnInfo = manifest[id];
  if (!serverFnInfo) {
    throw new Error("Server function info not found for " + id);
  }
  const fnModule = await serverFnInfo.importer();
  if (!fnModule) {
    console.info("serverFnInfo", serverFnInfo);
    throw new Error("Server function module not resolved for " + id);
  }
  const action = fnModule[serverFnInfo.functionName];
  if (!action) {
    console.info("serverFnInfo", serverFnInfo);
    console.info("fnModule", fnModule);
    throw new Error(
      `Server function module export not resolved for serverFn ID: ${id}`
    );
  }
  return action;
}
let serovalPlugins = void 0;
const textEncoder = new TextEncoder();
const FORM_DATA_CONTENT_TYPES = [
  "multipart/form-data",
  "application/x-www-form-urlencoded"
];
const MAX_PAYLOAD_SIZE = 1e6;
const handleServerAction = async ({
  request,
  context,
  serverFnId
}) => {
  const controller = new AbortController();
  const signal = controller.signal;
  const abort = () => controller.abort();
  request.signal.addEventListener("abort", abort);
  const method = request.method;
  const methodLower = method.toLowerCase();
  const url = new URL(request.url);
  const action = await getServerFnById(serverFnId);
  const isServerFn = request.headers.get("x-tsr-serverFn") === "true";
  if (!serovalPlugins) {
    serovalPlugins = getDefaultSerovalPlugins();
  }
  const contentType = request.headers.get("Content-Type");
  function parsePayload(payload) {
    const parsedPayload = fromJSON(payload, { plugins: serovalPlugins });
    return parsedPayload;
  }
  const response = await (async () => {
    try {
      let serializeResult = function(res2) {
        let nonStreamingBody = void 0;
        const alsResponse = getResponse();
        if (res2 !== void 0) {
          const rawStreams = /* @__PURE__ */ new Map();
          const rawStreamPlugin = createRawStreamRPCPlugin(
            (id, stream2) => {
              rawStreams.set(id, stream2);
            }
          );
          const plugins = [rawStreamPlugin, ...serovalPlugins || []];
          let done = false;
          const callbacks = {
            onParse: (value) => {
              nonStreamingBody = value;
            },
            onDone: () => {
              done = true;
            },
            onError: (error) => {
              throw error;
            }
          };
          toCrossJSONStream(res2, {
            refs: /* @__PURE__ */ new Map(),
            plugins,
            onParse(value) {
              callbacks.onParse(value);
            },
            onDone() {
              callbacks.onDone();
            },
            onError: (error) => {
              callbacks.onError(error);
            }
          });
          if (done && rawStreams.size === 0) {
            return new Response(
              nonStreamingBody ? JSON.stringify(nonStreamingBody) : void 0,
              {
                status: alsResponse.status,
                statusText: alsResponse.statusText,
                headers: {
                  "Content-Type": "application/json",
                  [X_TSS_SERIALIZED]: "true"
                }
              }
            );
          }
          if (rawStreams.size > 0) {
            const jsonStream = new ReadableStream({
              start(controller2) {
                callbacks.onParse = (value) => {
                  controller2.enqueue(JSON.stringify(value) + "\n");
                };
                callbacks.onDone = () => {
                  try {
                    controller2.close();
                  } catch {
                  }
                };
                callbacks.onError = (error) => controller2.error(error);
                if (nonStreamingBody !== void 0) {
                  callbacks.onParse(nonStreamingBody);
                }
              }
            });
            const multiplexedStream = createMultiplexedStream(
              jsonStream,
              rawStreams
            );
            return new Response(multiplexedStream, {
              status: alsResponse.status,
              statusText: alsResponse.statusText,
              headers: {
                "Content-Type": TSS_CONTENT_TYPE_FRAMED_VERSIONED,
                [X_TSS_SERIALIZED]: "true"
              }
            });
          }
          const stream = new ReadableStream({
            start(controller2) {
              callbacks.onParse = (value) => controller2.enqueue(
                textEncoder.encode(JSON.stringify(value) + "\n")
              );
              callbacks.onDone = () => {
                try {
                  controller2.close();
                } catch (error) {
                  controller2.error(error);
                }
              };
              callbacks.onError = (error) => controller2.error(error);
              if (nonStreamingBody !== void 0) {
                callbacks.onParse(nonStreamingBody);
              }
            }
          });
          return new Response(stream, {
            status: alsResponse.status,
            statusText: alsResponse.statusText,
            headers: {
              "Content-Type": "application/x-ndjson",
              [X_TSS_SERIALIZED]: "true"
            }
          });
        }
        return new Response(void 0, {
          status: alsResponse.status,
          statusText: alsResponse.statusText
        });
      };
      let res = await (async () => {
        if (FORM_DATA_CONTENT_TYPES.some(
          (type) => contentType && contentType.includes(type)
        )) {
          invariant(
            methodLower !== "get",
            "GET requests with FormData payloads are not supported"
          );
          const formData = await request.formData();
          const serializedContext = formData.get(TSS_FORMDATA_CONTEXT);
          formData.delete(TSS_FORMDATA_CONTEXT);
          const params = {
            context,
            data: formData
          };
          if (typeof serializedContext === "string") {
            try {
              const parsedContext = JSON.parse(serializedContext);
              const deserializedContext = fromJSON(parsedContext, {
                plugins: serovalPlugins
              });
              if (typeof deserializedContext === "object" && deserializedContext) {
                params.context = safeObjectMerge(
                  context,
                  deserializedContext
                );
              }
            } catch (e) {
              if (process.env.NODE_ENV === "development") {
                console.warn("Failed to parse FormData context:", e);
              }
            }
          }
          return await action(params, signal);
        }
        if (methodLower === "get") {
          const payloadParam = url.searchParams.get("payload");
          if (payloadParam && payloadParam.length > MAX_PAYLOAD_SIZE) {
            throw new Error("Payload too large");
          }
          const payload2 = payloadParam ? parsePayload(JSON.parse(payloadParam)) : {};
          payload2.context = safeObjectMerge(context, payload2.context);
          return await action(payload2, signal);
        }
        if (methodLower !== "post") {
          throw new Error("expected POST method");
        }
        let jsonPayload;
        if (contentType?.includes("application/json")) {
          jsonPayload = await request.json();
        }
        const payload = jsonPayload ? parsePayload(jsonPayload) : {};
        payload.context = safeObjectMerge(payload.context, context);
        return await action(payload, signal);
      })();
      const unwrapped = res.result || res.error;
      if (isNotFound(res)) {
        res = isNotFoundResponse(res);
      }
      if (!isServerFn) {
        return unwrapped;
      }
      if (unwrapped instanceof Response) {
        if (isRedirect(unwrapped)) {
          return unwrapped;
        }
        unwrapped.headers.set(X_TSS_RAW_RESPONSE, "true");
        return unwrapped;
      }
      return serializeResult(res);
    } catch (error) {
      if (error instanceof Response) {
        return error;
      }
      if (isNotFound(error)) {
        return isNotFoundResponse(error);
      }
      console.info();
      console.info("Server Fn Error!");
      console.info();
      console.error(error);
      console.info();
      const serializedError = JSON.stringify(
        await Promise.resolve(
          toCrossJSONAsync(error, {
            refs: /* @__PURE__ */ new Map(),
            plugins: serovalPlugins
          })
        )
      );
      const response2 = getResponse();
      return new Response(serializedError, {
        status: response2.status ?? 500,
        statusText: response2.statusText,
        headers: {
          "Content-Type": "application/json",
          [X_TSS_SERIALIZED]: "true"
        }
      });
    }
  })();
  request.signal.removeEventListener("abort", abort);
  return response;
};
function isNotFoundResponse(error) {
  const { headers, ...rest } = error;
  return new Response(JSON.stringify(rest), {
    status: 404,
    headers: {
      "Content-Type": "application/json",
      ...headers || {}
    }
  });
}
const HEADERS = {
  TSS_SHELL: "X-TSS_SHELL"
};
const createServerRpc = (functionId, splitImportFn) => {
  return Object.assign(splitImportFn, {
    functionId,
    [TSS_SERVER_FUNCTION]: true
  });
};
const ServerFunctionSerializationAdapter = createSerializationAdapter({
  key: "$TSS/serverfn",
  test: (v) => {
    if (typeof v !== "function") return false;
    if (!(TSS_SERVER_FUNCTION in v)) return false;
    return !!v[TSS_SERVER_FUNCTION];
  },
  toSerializable: ({ functionId }) => ({ functionId }),
  fromSerializable: ({ functionId }) => {
    const fn = async (opts, signal) => {
      const serverFn = await getServerFnById(functionId);
      const result = await serverFn(opts ?? {}, signal);
      return result.result;
    };
    return createServerRpc(functionId, fn);
  }
});
function getStartResponseHeaders(opts) {
  const headers = mergeHeaders(
    {
      "Content-Type": "text/html; charset=utf-8"
    },
    ...opts.router.state.matches.map((match) => {
      return match.headers;
    })
  );
  return headers;
}
let cachedStartEntry = null;
let cachedRouterEntry = null;
let cachedManifest = null;
async function getEntries() {
  if (cachedRouterEntry === null) {
    cachedRouterEntry = await import("./router-BGxBdlkD.mjs").then(function(n) {
      return n.at;
    }).then((n) => n.ab);
  }
  if (cachedStartEntry === null) {
    cachedStartEntry = await import("./start-HYkvq4Ni.mjs");
  }
  return {
    startEntry: cachedStartEntry,
    routerEntry: cachedRouterEntry
  };
}
async function getManifest() {
  if (cachedManifest === null) {
    cachedManifest = await getStartManifest();
  }
  return cachedManifest;
}
const ROUTER_BASEPATH = "/";
const SERVER_FN_BASE = "/_serverFn/";
const IS_PRERENDERING = process.env.TSS_PRERENDERING === "true";
const IS_SHELL_ENV = process.env.TSS_SHELL === "true";
const IS_DEV = process.env.NODE_ENV === "development";
const ERR_NO_RESPONSE = IS_DEV ? `It looks like you forgot to return a response from your server route handler. If you want to defer to the app router, make sure to have a component set in this route.` : "Internal Server Error";
const ERR_NO_DEFER = IS_DEV ? `You cannot defer to the app router if there is no component defined on this route.` : "Internal Server Error";
function throwRouteHandlerError() {
  throw new Error(ERR_NO_RESPONSE);
}
function throwIfMayNotDefer() {
  throw new Error(ERR_NO_DEFER);
}
function isSpecialResponse(value) {
  return value instanceof Response || isRedirect(value);
}
function handleCtxResult(result) {
  if (isSpecialResponse(result)) {
    return { response: result };
  }
  return result;
}
function executeMiddleware(middlewares, ctx) {
  let index = -1;
  const next = async (nextCtx) => {
    if (nextCtx) {
      if (nextCtx.context) {
        ctx.context = safeObjectMerge(ctx.context, nextCtx.context);
      }
      for (const key of Object.keys(nextCtx)) {
        if (key !== "context") {
          ctx[key] = nextCtx[key];
        }
      }
    }
    index++;
    const middleware = middlewares[index];
    if (!middleware) return ctx;
    let result;
    try {
      result = await middleware({ ...ctx, next });
    } catch (err) {
      if (isSpecialResponse(err)) {
        ctx.response = err;
        return ctx;
      }
      throw err;
    }
    const normalized = handleCtxResult(result);
    if (normalized) {
      if (normalized.response !== void 0) {
        ctx.response = normalized.response;
      }
      if (normalized.context) {
        ctx.context = safeObjectMerge(ctx.context, normalized.context);
      }
    }
    return ctx;
  };
  return next();
}
function handlerToMiddleware(handler, mayDefer = false) {
  if (mayDefer) {
    return handler;
  }
  return async (ctx) => {
    const response = await handler({ ...ctx, next: throwIfMayNotDefer });
    if (!response) {
      throwRouteHandlerError();
    }
    return response;
  };
}
function createStartHandler(cb) {
  const startRequestResolver = async (request, requestOpts) => {
    let router = null;
    let cbWillCleanup = false;
    try {
      const url = new URL(request.url);
      const href = url.href.replace(url.origin, "");
      const origin = getOrigin(request);
      const entries = await getEntries();
      const startOptions = await entries.startEntry.startInstance?.getOptions() || {};
      const serializationAdapters = [
        ...startOptions.serializationAdapters || [],
        ServerFunctionSerializationAdapter
      ];
      const requestStartOptions = {
        ...startOptions,
        serializationAdapters
      };
      const flattenedRequestMiddlewares = startOptions.requestMiddleware ? flattenMiddlewares(startOptions.requestMiddleware) : [];
      const executedRequestMiddlewares = new Set(
        flattenedRequestMiddlewares
      );
      const getRouter = async () => {
        if (router) return router;
        router = await entries.routerEntry.getRouter();
        let isShell = IS_SHELL_ENV;
        if (IS_PRERENDERING && !isShell) {
          isShell = request.headers.get(HEADERS.TSS_SHELL) === "true";
        }
        const history = createMemoryHistory({
          initialEntries: [href]
        });
        router.update({
          history,
          isShell,
          isPrerendering: IS_PRERENDERING,
          origin: router.options.origin ?? origin,
          ...{
            defaultSsr: requestStartOptions.defaultSsr,
            serializationAdapters: [
              ...requestStartOptions.serializationAdapters,
              ...router.options.serializationAdapters || []
            ]
          },
          basepath: ROUTER_BASEPATH
        });
        return router;
      };
      if (SERVER_FN_BASE && url.pathname.startsWith(SERVER_FN_BASE)) {
        const serverFnId = url.pathname.slice(SERVER_FN_BASE.length).split("/")[0];
        if (!serverFnId) {
          throw new Error("Invalid server action param for serverFnId");
        }
        const serverFnHandler = async ({ context }) => {
          return runWithStartContext(
            {
              getRouter,
              startOptions: requestStartOptions,
              contextAfterGlobalMiddlewares: context,
              request,
              executedRequestMiddlewares
            },
            () => handleServerAction({
              request,
              context: requestOpts?.context,
              serverFnId
            })
          );
        };
        const middlewares2 = flattenedRequestMiddlewares.map(
          (d) => d.options.server
        );
        const ctx2 = await executeMiddleware([...middlewares2, serverFnHandler], {
          request,
          context: createNullProtoObject(requestOpts?.context)
        });
        return handleRedirectResponse(ctx2.response, request, getRouter);
      }
      const executeRouter = async (serverContext) => {
        const acceptHeader = request.headers.get("Accept") || "*/*";
        const acceptParts = acceptHeader.split(",");
        const supportedMimeTypes = ["*/*", "text/html"];
        const isSupported = supportedMimeTypes.some(
          (mimeType) => acceptParts.some((part) => part.trim().startsWith(mimeType))
        );
        if (!isSupported) {
          return Response.json(
            { error: "Only HTML requests are supported here" },
            { status: 500 }
          );
        }
        const manifest2 = await getManifest();
        const routerInstance = await getRouter();
        attachRouterServerSsrUtils({
          router: routerInstance,
          manifest: manifest2
        });
        routerInstance.update({ additionalContext: { serverContext } });
        await routerInstance.load();
        if (routerInstance.state.redirect) {
          return routerInstance.state.redirect;
        }
        await routerInstance.serverSsr.dehydrate();
        const responseHeaders = getStartResponseHeaders({
          router: routerInstance
        });
        cbWillCleanup = true;
        return cb({
          request,
          router: routerInstance,
          responseHeaders
        });
      };
      const requestHandlerMiddleware = async ({ context }) => {
        return runWithStartContext(
          {
            getRouter,
            startOptions: requestStartOptions,
            contextAfterGlobalMiddlewares: context,
            request,
            executedRequestMiddlewares
          },
          async () => {
            try {
              return await handleServerRoutes({
                getRouter,
                request,
                url,
                executeRouter,
                context,
                executedRequestMiddlewares
              });
            } catch (err) {
              if (err instanceof Response) {
                return err;
              }
              throw err;
            }
          }
        );
      };
      const middlewares = flattenedRequestMiddlewares.map(
        (d) => d.options.server
      );
      const ctx = await executeMiddleware(
        [...middlewares, requestHandlerMiddleware],
        { request, context: createNullProtoObject(requestOpts?.context) }
      );
      return handleRedirectResponse(ctx.response, request, getRouter);
    } finally {
      if (router && !cbWillCleanup) {
        router.serverSsr?.cleanup();
      }
      router = null;
    }
  };
  return requestHandler(startRequestResolver);
}
async function handleRedirectResponse(response, request, getRouter) {
  if (!isRedirect(response)) {
    return response;
  }
  if (isResolvedRedirect(response)) {
    if (request.headers.get("x-tsr-serverFn") === "true") {
      return Response.json(
        { ...response.options, isSerializedRedirect: true },
        { headers: response.headers }
      );
    }
    return response;
  }
  const opts = response.options;
  if (opts.to && typeof opts.to === "string" && !opts.to.startsWith("/")) {
    throw new Error(
      `Server side redirects must use absolute paths via the 'href' or 'to' options. The redirect() method's "to" property accepts an internal path only. Use the "href" property to provide an external URL. Received: ${JSON.stringify(opts)}`
    );
  }
  if (["params", "search", "hash"].some(
    (d) => typeof opts[d] === "function"
  )) {
    throw new Error(
      `Server side redirects must use static search, params, and hash values and do not support functional values. Received functional values for: ${Object.keys(
        opts
      ).filter((d) => typeof opts[d] === "function").map((d) => `"${d}"`).join(", ")}`
    );
  }
  const router = await getRouter();
  const redirect = router.resolveRedirect(response);
  if (request.headers.get("x-tsr-serverFn") === "true") {
    return Response.json(
      { ...response.options, isSerializedRedirect: true },
      { headers: response.headers }
    );
  }
  return redirect;
}
async function handleServerRoutes({
  getRouter,
  request,
  url,
  executeRouter,
  context,
  executedRequestMiddlewares
}) {
  const router = await getRouter();
  const rewrittenUrl = executeRewriteInput(router.rewrite, url);
  const pathname = rewrittenUrl.pathname;
  const { matchedRoutes, foundRoute, routeParams } = router.getMatchedRoutes(pathname);
  const isExactMatch = foundRoute && routeParams["**"] === void 0;
  const routeMiddlewares = [];
  for (const route of matchedRoutes) {
    const serverMiddleware = route.options.server?.middleware;
    if (serverMiddleware) {
      const flattened = flattenMiddlewares(serverMiddleware);
      for (const m of flattened) {
        if (!executedRequestMiddlewares.has(m)) {
          routeMiddlewares.push(m.options.server);
        }
      }
    }
  }
  const server2 = foundRoute?.options.server;
  if (server2?.handlers && isExactMatch) {
    const handlers = typeof server2.handlers === "function" ? server2.handlers({ createHandlers: (d) => d }) : server2.handlers;
    const requestMethod = request.method.toUpperCase();
    const handler = handlers[requestMethod] ?? handlers["ANY"];
    if (handler) {
      const mayDefer = !!foundRoute.options.component;
      if (typeof handler === "function") {
        routeMiddlewares.push(handlerToMiddleware(handler, mayDefer));
      } else {
        if (handler.middleware?.length) {
          const handlerMiddlewares = flattenMiddlewares(handler.middleware);
          for (const m of handlerMiddlewares) {
            routeMiddlewares.push(m.options.server);
          }
        }
        if (handler.handler) {
          routeMiddlewares.push(handlerToMiddleware(handler.handler, mayDefer));
        }
      }
    }
  }
  routeMiddlewares.push((ctx2) => executeRouter(ctx2.context));
  const ctx = await executeMiddleware(routeMiddlewares, {
    request,
    context,
    params: routeParams,
    pathname
  });
  return ctx.response;
}
const fetch$1 = createStartHandler(defaultStreamHandler);
function createServerEntry(entry) {
  return {
    async fetch(...args) {
      return await entry.fetch(...args);
    }
  };
}
const server = createServerEntry({ fetch: fetch$1 });
export {
  createServerEntry,
  server as default
};
