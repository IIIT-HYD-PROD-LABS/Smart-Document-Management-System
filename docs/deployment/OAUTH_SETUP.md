# OAuth Setup — TaxSync

TaxSync uses OAuth for two distinct flows that share the **same Google Cloud Console OAuth client**:

| Flow | What it does | Redirect URI sent to Google |
|---|---|---|
| Sign in with Google | Login button on `/login` | `{BACKEND_URL}/api/auth/callback/google` |
| Connect Gmail | "Connect Gmail" on the Email page → scans the inbox for compliance notices and vendor invoices | `{BACKEND_URL}/api/email/gmail/oauth/callback` |

Both URIs **must** be registered in the OAuth client's "Authorized redirect URIs" list. Otherwise Google rejects the request with `Error 400: redirect_uri_mismatch`.

A separate Microsoft OAuth client (Entra ID / Azure AD) is used for "Sign in with Microsoft" — same setup pattern, different console.

## Quick check — what is my backend sending?

The backend exposes a diagnostic endpoint that prints the exact URIs it will send and the providers it has configured. **No authentication required** — the redirect URIs are public anyway (they appear in every OAuth request).

```bash
curl -s http://localhost:8000/api/auth/oauth/diag | jq
```

Or open `http://localhost:3000/oauth-setup` in the browser for a click-to-copy view.

Sample output:

```json
{
  "backend_url": "http://localhost:8000",
  "frontend_url": "http://localhost:3000",
  "providers": {
    "google": {
      "configured": true,
      "client_id_hint": "764178367858…",
      "redirect_uris": [
        "http://localhost:8000/api/auth/callback/google",
        "http://localhost:8000/api/email/gmail/oauth/callback"
      ],
      "console_url": "https://console.cloud.google.com/apis/credentials"
    },
    "microsoft": {
      "configured": false,
      "client_id_hint": null,
      "redirect_uris": [
        "http://localhost:8000/api/auth/callback/microsoft"
      ],
      "console_url": "https://entra.microsoft.com/..."
    }
  },
  "javascript_origins": [
    "http://localhost:3000",
    "http://localhost:8000"
  ]
}
```

## Google Cloud Console — register the URIs

1. Open https://console.cloud.google.com/apis/credentials.
2. Pick the right Google Cloud **project** (top bar). Project must match the one whose `GOOGLE_CLIENT_ID` is in your backend `.env`.
3. Click into the **OAuth 2.0 Client ID** whose ID starts with the `client_id_hint` from the diag endpoint.
4. Under **Authorized redirect URIs**, click **+ ADD URI** for every redirect URI from the diag output. For local dev that's:
   ```
   http://localhost:8000/api/auth/callback/google
   http://localhost:8000/api/email/gmail/oauth/callback
   ```
5. Under **Authorized JavaScript origins**, add (these are the values from `javascript_origins` in the diag):
   ```
   http://localhost:3000
   http://localhost:8000
   ```
6. Click **SAVE**.
7. Google takes ~30 seconds to propagate. Wait, then retry the login or Gmail connect.

## Microsoft (Entra ID) — register the URIs

1. Open https://entra.microsoft.com → **Applications** → **App registrations**.
2. Click into the app whose Application (client) ID matches your `MICROSOFT_CLIENT_ID` env var.
3. Under **Authentication** → **Platform configurations** → **Web**, add the redirect URI from the diag (default local: `http://localhost:8000/api/auth/callback/microsoft`).
4. Under **Implicit grant and hybrid flows**, leave both checkboxes off — TaxSync uses authorization code flow.
5. Click **Save**.

## Production deployment

When you deploy on Vercel, Render, etc., the backend URL changes — and so do the redirect URIs. Set:

```bash
# backend .env (or Vercel env)
BACKEND_URL=https://api.your-company.com
FRONTEND_URL=https://app.your-company.com
```

Then hit `https://api.your-company.com/api/auth/oauth/diag` and add the new URIs to the OAuth client. You can keep both localhost AND production URIs registered at the same time — Google honours all listed entries.

## Troubleshooting

### `Error 400: redirect_uri_mismatch`
**Cause:** The redirect URI the backend is sending is not in the OAuth client's authorized list.
**Fix:** Run the diag, copy the `redirect_uris` for the affected provider, paste them into the Google / Microsoft console.

### `Error 400: invalid_client`
**Cause:** `GOOGLE_CLIENT_ID` or `GOOGLE_CLIENT_SECRET` env var doesn't match a real client.
**Fix:** Verify the values in your backend `.env` against the OAuth client in Google Cloud Console. The diag endpoint shows the first 12 chars of the configured client ID for sanity-checking.

### `Google sign-in not yet configured` toast on login
**Cause:** The backend started without `GOOGLE_CLIENT_ID` set.
**Fix:** Add it to `.env`, restart the backend container (`docker compose up -d --build backend`).

### Provider buttons missing on login page
**Cause:** `/api/auth/providers` returns only `["local"]` — neither `GOOGLE_CLIENT_ID` nor `MICROSOFT_CLIENT_ID` is set.
**Fix:** Set whichever you want enabled in `.env`, rebuild backend.

### Gmail connect works, but login doesn't (or vice versa)
**Cause:** Only ONE of the two redirect URIs is registered with Google. They share a client but each callback path needs its own entry.
**Fix:** Make sure BOTH are present in "Authorized redirect URIs":
- `{BACKEND_URL}/api/auth/callback/google` (login)
- `{BACKEND_URL}/api/email/gmail/oauth/callback` (Gmail integration)
