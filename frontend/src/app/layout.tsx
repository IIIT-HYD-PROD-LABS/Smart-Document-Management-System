import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Toaster } from "react-hot-toast";
import { AuthProvider } from "@/context/AuthContext";
import "./globals.css";

const inter = Inter({
    subsets: ["latin"],
    display: "swap",
    variable: "--font-inter",
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
        <html lang="en">
            <body className={inter.className}>
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
