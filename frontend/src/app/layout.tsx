import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import { Toaster } from "react-hot-toast";
import { AuthProvider } from "@/context/AuthContext";
import { ThemeProvider, THEME_BOOTSTRAP_SCRIPT } from "@/context/ThemeContext";
import "./globals.css";

// Compliance Noir — IBM Plex pairing
// Plex Sans: humanist grotesque with institutional gravitas (Big-4-grade)
// Plex Mono: precision tabular numerics for risk scores, penalty amounts,
// confidence percentages, and date ranges throughout the dashboard.
const plexSans = IBM_Plex_Sans({
    subsets: ["latin"],
    weight: ["300", "400", "500", "600", "700"],
    display: "swap",
    variable: "--font-plex-sans",
});

const plexMono = IBM_Plex_Mono({
    subsets: ["latin"],
    weight: ["400", "500", "600"],
    display: "swap",
    variable: "--font-plex-mono",
});

export const metadata: Metadata = {
    title: "TaxSync",
    description: "AI-powered tax compliance intelligence — classify notices, track deadlines, draft responses",
    icons: {
        icon: "/favicon.svg",
    },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en" className={`${plexSans.variable} ${plexMono.variable}`}>
            <head>
                {/* Sync theme bootstrap — runs before paint to apply the
                    persisted (or default Light) theme to <html>. Static
                    constant; no user input. */}
                <script
                    // eslint-disable-next-line react/no-danger
                    dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP_SCRIPT }}
                />
            </head>
            <body className={plexSans.className}>
                <ThemeProvider>
                    <AuthProvider>
                        {children}
                        <Toaster
                            position="bottom-right"
                            toastOptions={{
                                duration: 3000,
                                style: {
                                    background: "var(--bg-elevated)",
                                    color: "var(--text-primary)",
                                    border: "1px solid var(--border-default)",
                                    borderRadius: "8px",
                                    fontSize: "13px",
                                    boxShadow: "var(--shadow-lg)",
                                },
                                success: { iconTheme: { primary: "var(--success)", secondary: "var(--bg-elevated)" } },
                                error: { iconTheme: { primary: "var(--danger)", secondary: "var(--bg-elevated)" } },
                            }}
                        />
                    </AuthProvider>
                </ThemeProvider>
            </body>
        </html>
    );
}
