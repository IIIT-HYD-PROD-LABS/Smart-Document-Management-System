// Container entrypoint.
//
// The app is served under https://canvas.iiit.ac.in/taxsyncfestage, and the
// campus nginx strips exactly one "/taxsyncfestage" before forwarding to this
// container (verified: /taxsyncfestage/taxsyncfestage/login -> 200,
// /taxsyncfestage/login -> 404). But the Next build has
// basePath:"/taxsyncfestage", so Next only serves routes UNDER that prefix and
// 404s on the stripped paths.
//
// nginx cannot be changed (campus standard), so we compensate in-code: run the
// standalone Next server on an internal loopback port and put a tiny
// prefix-restoring proxy in front on the public port. Every stripped request
// (/login, /_next/..., /dashboard) gets the "/taxsyncfestage" re-added before
// Next sees it, so basePath matches. This keeps ALL browser-visible URLs
// (client-side router.push/replace, <Link>, middleware redirects, assets)
// prefixed automatically via basePath, with zero nginx changes.
const fs = require("fs");
const http = require("http");
const path = require("path");

const PREFIX = process.env.APP_BASE_PATH || "/taxsyncfestage";
const PUBLIC_PORT = Number(process.env.PORT) || 8026;
const INTERNAL_PORT = Number(process.env.UPSTREAM_PORT) || 8027;

function findStandaloneRoot(dir, depth = 0) {
  const serverFile = path.join(dir, "server.js");
  if (fs.existsSync(serverFile)) {
    try {
      if (fs.statSync(serverFile).size > 1500) return dir;
    } catch {
      /* ignore */
    }
  }
  if (depth >= 5) return null;
  let entries;
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return null;
  }
  for (const ent of entries) {
    if (!ent.isDirectory() || ent.name === "node_modules") continue;
    const found = findStandaloneRoot(path.join(dir, ent.name), depth + 1);
    if (found) return found;
  }
  return null;
}

function resolveStandaloneRoot() {
  const direct = findStandaloneRoot(__dirname);
  if (direct) {
    if (direct !== __dirname) {
      console.warn(
        "[entry] nested standalone at",
        direct,
        "— rebuild with outputFileTracingRoot for a flat image",
      );
    }
    return direct;
  }

  console.error(
    "[entry] standalone server.js not found under",
    __dirname,
  );
  process.exit(1);
}

const appRoot = resolveStandaloneRoot();
process.chdir(appRoot);

// Start the standalone Next server bound to loopback on the internal port.
// server.js reads PORT/HOSTNAME from env at require time.
process.env.PORT = String(INTERNAL_PORT);
process.env.HOSTNAME = "127.0.0.1";
require(path.join(appRoot, "server.js"));

function waitForUpstream(attempts = 60, intervalMs = 500) {
  return new Promise((resolve, reject) => {
    let n = 0;
    const tick = () => {
      n += 1;
      const req = http.request(
        {
          host: "127.0.0.1",
          port: INTERNAL_PORT,
          path: PREFIX + "/login",
          method: "GET",
          timeout: 2000,
        },
        (res) => {
          res.resume();
          resolve();
        },
      );
      req.on("timeout", () => req.destroy());
      req.on("error", () => {
        if (n >= attempts) {
          reject(new Error("Next standalone did not become ready"));
          return;
        }
        setTimeout(tick, intervalMs);
      });
      req.end();
    };
    tick();
  });
}

// Re-add the prefix nginx stripped, unless it is somehow already present.
function withPrefix(url) {
  if (
    url === PREFIX ||
    url.startsWith(PREFIX + "/") ||
    url.startsWith(PREFIX + "?")
  ) {
    return url;
  }
  return PREFIX + url;
}

const proxy = http.createServer((cReq, cRes) => {
  const upstream = http.request(
    {
      host: "127.0.0.1",
      port: INTERNAL_PORT,
      path: withPrefix(cReq.url),
      method: cReq.method,
      headers: cReq.headers,
    },
    (uRes) => {
      cRes.writeHead(uRes.statusCode || 502, uRes.headers);
      uRes.pipe(cRes);
    },
  );
  upstream.on("error", (err) => {
    console.error("[entry] upstream error:", err.message);
    if (!cRes.headersSent) cRes.writeHead(502);
    cRes.end("bad gateway");
  });
  cReq.pipe(upstream);
});

waitForUpstream()
  .then(() => {
    proxy.listen(PUBLIC_PORT, "0.0.0.0", () => {
      console.log(
        `[entry] prefix proxy :${PUBLIC_PORT} -> 127.0.0.1:${INTERNAL_PORT} (prefix ${PREFIX})`,
      );
    });
  })
  .catch((err) => {
    console.error("[entry] startup failed:", err.message);
    process.exit(1);
  });
