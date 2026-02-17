import type { Metadata } from "next";
import { Toaster } from "react-hot-toast";
import { AuthProvider } from "@/context/AuthContext";
import "./globals.css";

export const metadata: Metadata = {
    title: "SmartDocs — AI Document Management",
    description: "AI-powered document management system with intelligent classification, OCR, and search",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en" className="dark">
            <body className="bg-surface-900 min-h-screen bg-mesh">
                <AuthProvider>
                    {children}
                    <Toaster
                        position="bottom-right"
                        toastOptions={{
                            duration: 4000,
                            style: {
                                background: "#1e293b",
                                color: "#f8fafc",
                                border: "1px solid #334155",
                                borderRadius: "12px",
                                fontSize: "14px",
                            },
                            success: {
                                iconTheme: { primary: "#22c55e", secondary: "#f8fafc" },
                            },
                            error: {
                                iconTheme: { primary: "#ef4444", secondary: "#f8fafc" },
                            },
                        }}
                    />
                </AuthProvider>
            </body>
        </html>
    );
}
