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

function resolveStandaloneRoot() {
  const direct = path.join(__dirname, "server.js");
  if (fs.existsSync(direct)) return __dirname;

  const nested = path.join(
    __dirname,
    "Desktop",
    "Smart_Docs_Prod_Labs",
    "taxsync-frontend",
  );
  if (fs.existsSync(path.join(nested, "server.js"))) {
    console.warn(
      "[entry] nested standalone detected — rebuild with outputFileTracingRoot",
    );
    return nested;
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

proxy.listen(PUBLIC_PORT, "0.0.0.0", () => {
  console.log(
    `[entry] prefix proxy :${PUBLIC_PORT} -> 127.0.0.1:${INTERNAL_PORT} (prefix ${PREFIX})`,
  );
});
