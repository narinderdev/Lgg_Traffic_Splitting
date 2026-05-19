var __defProp = Object.defineProperty;
var __name = (target, value) => __defProp(target, "name", { value, configurable: true });

// src/index.ts
var DEFAULT_ASSIGNMENT_TTL = 60 * 60 * 24 * 30;
var TRACKING_PARAM_KEYS = ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid", "msclkid"];
var src_default = {
  async fetch(request, env) {
    try {
      const url = new URL(request.url);
      const slug = extractSlug(url.pathname);
      if (!slug) {
        return new Response("Missing experiment slug.", { status: 404 });
      }
      const config = await env.EXPERIMENTS_KV.get(`experiment:${slug}`, "json");
      if (!config) {
        return new Response(`Experiment "${slug}" was not found in KV.`, { status: 404 });
      }
      if (config.status !== "active") {
        return redirect(config.entry_url);
      }
      const deviceType = detectDeviceType(request.headers.get("user-agent") || "");
      const trafficSource = detectTrafficSource(request);
      if (!passesSegmentation(config.segments, deviceType, trafficSource)) {
        return redirect(config.entry_url);
      }
      if (Math.random() * 100 > config.traffic_pct) {
        return redirect(config.entry_url);
      }
      const visitorId = readCookie(request.headers.get("cookie"), "lgg_uid") || crypto.randomUUID();
      const assignmentKey = `assignment:${visitorId}:${config.id}`;
      const assignedVariantId = await env.EXPERIMENTS_KV.get(assignmentKey);
      const assignedVariant = config.variants.find((variant2) => variant2.id === assignedVariantId);
      const variant = assignedVariant ?? selectVariant(config.variants);
      try {
        await env.EXPERIMENTS_KV.put(assignmentKey, variant.id, {
          expirationTtl: Number(env.ASSIGNMENT_TTL_SECONDS || DEFAULT_ASSIGNMENT_TTL)
        });
      } catch (error) {
        console.warn("KV assignment write failed; continuing redirect.", error);
      }
      const destination = buildDestinationUrl(variant.destination_url, url, variant.hyros_tag);
      const country = typeof request.cf?.country === "string" ? request.cf.country : null;
      const impressionEvent = {
        experiment_id: config.id,
        variant_id: variant.id,
        device_type: deviceType,
        traffic_source: trafficSource,
        country,
        ts: (/* @__PURE__ */ new Date()).toISOString()
      };
      try {
        if (env.IMPRESSIONS_QUEUE) {
          await env.IMPRESSIONS_QUEUE.send(impressionEvent);
        } else {
          await ingestDirect(env, impressionEvent);
        }
      } catch (error) {
        console.warn("Impression delivery failed; continuing redirect.", error);
      }
      return new Response(null, {
        status: 302,
        headers: {
          Location: destination,
          "Set-Cookie": `lgg_uid=${visitorId}; Path=/; Max-Age=${env.ASSIGNMENT_TTL_SECONDS || DEFAULT_ASSIGNMENT_TTL}; HttpOnly; Secure; SameSite=Lax`
        }
      });
    } catch (error) {
      const detail = error instanceof Error ? `${error.name}: ${error.message}` : String(error);
      return new Response(`Worker execution failed: ${detail}`, { status: 500 });
    }
  },
  async queue(batch, env) {
    const events = batch.messages.map((message) => message.body);
    const response = await fetch(`${env.BACKEND_BASE_URL}/ingest/impressions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${env.INGEST_API_KEY}`
      },
      body: JSON.stringify({ events })
    });
    if (!response.ok) {
      throw new Error(`Impression ingest failed with ${response.status}`);
    }
    batch.ackAll();
  }
};
async function ingestDirect(env, event) {
  const response = await fetch(`${env.BACKEND_BASE_URL}/ingest/impressions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${env.INGEST_API_KEY}`
    },
    body: JSON.stringify({ events: [event] })
  });
  if (!response.ok) {
    throw new Error(`Direct impression ingest failed with ${response.status}`);
  }
}
__name(ingestDirect, "ingestDirect");
function extractSlug(pathname) {
  return pathname.replace(/^\/+/, "").split("/")[0] || "";
}
__name(extractSlug, "extractSlug");
function detectDeviceType(userAgent) {
  const ua = userAgent.toLowerCase();
  if (/ipad|tablet/.test(ua)) return "tablet";
  if (/mobi|iphone|android/.test(ua)) return "mobile";
  return "desktop";
}
__name(detectDeviceType, "detectDeviceType");
function detectTrafficSource(request) {
  const url = new URL(request.url);
  const medium = url.searchParams.get("utm_medium")?.toLowerCase();
  const source = url.searchParams.get("utm_source")?.toLowerCase();
  const referer = request.headers.get("referer")?.toLowerCase() || "";
  const hasPaidClickId = Boolean(url.searchParams.get("gclid") || url.searchParams.get("msclkid"));
  if (medium === "cpc" || medium === "ppc" || source === "googleads" || hasPaidClickId) {
    return "paid_search";
  }
  if (isSocialReferer(referer) || ["facebook", "instagram", "tiktok", "linkedin", "x"].includes(source || "")) {
    return "social";
  }
  if (!referer) {
    return "direct";
  }
  if (isSearchEngine(referer)) {
    return "organic";
  }
  return "unknown";
}
__name(detectTrafficSource, "detectTrafficSource");
function isSearchEngine(referer) {
  return /(google\.[a-z.]+\/search|bing\.com|yahoo\.com|duckduckgo\.com)/.test(referer);
}
__name(isSearchEngine, "isSearchEngine");
function isSocialReferer(referer) {
  return /(facebook\.com|instagram\.com|tiktok\.com|linkedin\.com|x\.com|l\.facebook\.com)/.test(referer);
}
__name(isSocialReferer, "isSocialReferer");
function passesSegmentation(segments, deviceType, trafficSource) {
  if (!segments) return true;
  if (segments.device_types && segments.device_types.length > 0 && !segments.device_types.includes(deviceType)) {
    return false;
  }
  if (segments.traffic_sources && segments.traffic_sources.length > 0 && !segments.traffic_sources.includes(trafficSource)) {
    return false;
  }
  return true;
}
__name(passesSegmentation, "passesSegmentation");
function selectVariant(variants) {
  const random = Math.floor(Math.random() * 100);
  let cursor = 0;
  for (const variant of variants) {
    cursor += variant.weight;
    if (random < cursor) {
      return variant;
    }
  }
  return variants[0];
}
__name(selectVariant, "selectVariant");
function buildDestinationUrl(destinationUrl, entryUrl, hyrosTag) {
  const destination = new URL(destinationUrl);
  TRACKING_PARAM_KEYS.forEach((key) => {
    const incomingValue = entryUrl.searchParams.get(key);
    if (incomingValue) {
      destination.searchParams.set(key, incomingValue);
    }
  });
  entryUrl.searchParams.forEach((value, key) => {
    if (key.startsWith("utm_") && value) {
      destination.searchParams.set(key, value);
    }
  });
  if (hyrosTag) {
    destination.searchParams.set("test_tag", hyrosTag);
  }
  return destination.toString();
}
__name(buildDestinationUrl, "buildDestinationUrl");
function redirect(destination) {
  return Response.redirect(destination, 302);
}
__name(redirect, "redirect");
function readCookie(cookieHeader, name) {
  if (!cookieHeader) return null;
  const cookie = cookieHeader.split(";").map((part) => part.trim()).find((part) => part.startsWith(`${name}=`));
  return cookie ? cookie.slice(name.length + 1) : null;
}
__name(readCookie, "readCookie");

// node_modules/wrangler/templates/middleware/middleware-ensure-req-body-drained.ts
var drainBody = /* @__PURE__ */ __name(async (request, env, _ctx, middlewareCtx) => {
  try {
    return await middlewareCtx.next(request, env);
  } finally {
    try {
      if (request.body !== null && !request.bodyUsed) {
        const reader = request.body.getReader();
        while (!(await reader.read()).done) {
        }
      }
    } catch (e) {
      console.error("Failed to drain the unused request body.", e);
    }
  }
}, "drainBody");
var middleware_ensure_req_body_drained_default = drainBody;

// .wrangler/tmp/bundle-X6S08v/middleware-insertion-facade.js
var __INTERNAL_WRANGLER_MIDDLEWARE__ = [
  middleware_ensure_req_body_drained_default
];
var middleware_insertion_facade_default = src_default;

// node_modules/wrangler/templates/middleware/common.ts
var __facade_middleware__ = [];
function __facade_register__(...args) {
  __facade_middleware__.push(...args.flat());
}
__name(__facade_register__, "__facade_register__");
function __facade_invokeChain__(request, env, ctx, dispatch, middlewareChain) {
  const [head, ...tail] = middlewareChain;
  const middlewareCtx = {
    dispatch,
    next(newRequest, newEnv) {
      return __facade_invokeChain__(newRequest, newEnv, ctx, dispatch, tail);
    }
  };
  return head(request, env, ctx, middlewareCtx);
}
__name(__facade_invokeChain__, "__facade_invokeChain__");
function __facade_invoke__(request, env, ctx, dispatch, finalMiddleware) {
  return __facade_invokeChain__(request, env, ctx, dispatch, [
    ...__facade_middleware__,
    finalMiddleware
  ]);
}
__name(__facade_invoke__, "__facade_invoke__");

// .wrangler/tmp/bundle-X6S08v/middleware-loader.entry.ts
var __Facade_ScheduledController__ = class ___Facade_ScheduledController__ {
  constructor(scheduledTime, cron, noRetry) {
    this.scheduledTime = scheduledTime;
    this.cron = cron;
    this.#noRetry = noRetry;
  }
  static {
    __name(this, "__Facade_ScheduledController__");
  }
  #noRetry;
  noRetry() {
    if (!(this instanceof ___Facade_ScheduledController__)) {
      throw new TypeError("Illegal invocation");
    }
    this.#noRetry();
  }
};
function wrapExportedHandler(worker) {
  if (__INTERNAL_WRANGLER_MIDDLEWARE__ === void 0 || __INTERNAL_WRANGLER_MIDDLEWARE__.length === 0) {
    return worker;
  }
  for (const middleware of __INTERNAL_WRANGLER_MIDDLEWARE__) {
    __facade_register__(middleware);
  }
  const fetchDispatcher = /* @__PURE__ */ __name(function(request, env, ctx) {
    if (worker.fetch === void 0) {
      throw new Error("Handler does not export a fetch() function.");
    }
    return worker.fetch(request, env, ctx);
  }, "fetchDispatcher");
  return {
    ...worker,
    fetch(request, env, ctx) {
      const dispatcher = /* @__PURE__ */ __name(function(type, init) {
        if (type === "scheduled" && worker.scheduled !== void 0) {
          const controller = new __Facade_ScheduledController__(
            Date.now(),
            init.cron ?? "",
            () => {
            }
          );
          return worker.scheduled(controller, env, ctx);
        }
      }, "dispatcher");
      return __facade_invoke__(request, env, ctx, dispatcher, fetchDispatcher);
    }
  };
}
__name(wrapExportedHandler, "wrapExportedHandler");
function wrapWorkerEntrypoint(klass) {
  if (__INTERNAL_WRANGLER_MIDDLEWARE__ === void 0 || __INTERNAL_WRANGLER_MIDDLEWARE__.length === 0) {
    return klass;
  }
  for (const middleware of __INTERNAL_WRANGLER_MIDDLEWARE__) {
    __facade_register__(middleware);
  }
  return class extends klass {
    #fetchDispatcher = /* @__PURE__ */ __name((request, env, ctx) => {
      this.env = env;
      this.ctx = ctx;
      if (super.fetch === void 0) {
        throw new Error("Entrypoint class does not define a fetch() function.");
      }
      return super.fetch(request);
    }, "#fetchDispatcher");
    #dispatcher = /* @__PURE__ */ __name((type, init) => {
      if (type === "scheduled" && super.scheduled !== void 0) {
        const controller = new __Facade_ScheduledController__(
          Date.now(),
          init.cron ?? "",
          () => {
          }
        );
        return super.scheduled(controller);
      }
    }, "#dispatcher");
    fetch(request) {
      return __facade_invoke__(
        request,
        this.env,
        this.ctx,
        this.#dispatcher,
        this.#fetchDispatcher
      );
    }
  };
}
__name(wrapWorkerEntrypoint, "wrapWorkerEntrypoint");
var WRAPPED_ENTRY;
if (typeof middleware_insertion_facade_default === "object") {
  WRAPPED_ENTRY = wrapExportedHandler(middleware_insertion_facade_default);
} else if (typeof middleware_insertion_facade_default === "function") {
  WRAPPED_ENTRY = wrapWorkerEntrypoint(middleware_insertion_facade_default);
}
var middleware_loader_entry_default = WRAPPED_ENTRY;
export {
  __INTERNAL_WRANGLER_MIDDLEWARE__,
  middleware_loader_entry_default as default
};
//# sourceMappingURL=index.js.map
