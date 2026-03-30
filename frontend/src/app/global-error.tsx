"use client";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
    return (
        <html lang="en">
            <body style={{ backgroundColor: "#09090b", margin: 0 }}>
                <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: "24px" }}>
                    <div style={{ maxWidth: "400px", width: "100%", textAlign: "center" }}>
                        <h2 style={{ fontSize: "18px", fontWeight: 600, color: "#fafafa", marginBottom: "8px" }}>Something went wrong</h2>
                        <p style={{ fontSize: "14px", color: "#71717a", marginBottom: "24px" }}>A critical error occurred. Please refresh the page.</p>
                        <button onClick={reset} style={{ padding: "8px 16px", fontSize: "14px", fontWeight: 500, backgroundColor: "#fafafa", color: "#09090b", border: "none", borderRadius: "6px", cursor: "pointer" }}>
                            Try again
                        </button>
                    </div>
                </div>
            </body>
        </html>
    );
}
