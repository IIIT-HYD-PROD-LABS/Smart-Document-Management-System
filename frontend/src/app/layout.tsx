import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import { Toaster } from "react-hot-toast";
import { AuthProvider } from "@/context/AuthContext";
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
            <body className={plexSans.className}>
                <AuthProvider>
                    {children}
                    <Toaster
                        position="bottom-right"
                        toastOptions={{
                            duration: 3000,
                            style: {
                                background: "#18181b",
                                color: "#fafafa",
                                border: "1px solid #27272a",
                                borderRadius: "8px",
                                fontSize: "13px",
                            },
                            success: { iconTheme: { primary: "#10b981", secondary: "#fafafa" } },
                            error: { iconTheme: { primary: "#ef4444", secondary: "#fafafa" } },
                        }}
                    />
                </AuthProvider>
            </body>
        </html>
    );
}
