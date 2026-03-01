import type { Metadata } from "next";
import { Toaster } from "react-hot-toast";
import { AuthProvider } from "@/context/AuthContext";
import "./globals.css";

export const metadata: Metadata = {
    title: "SmartDocs",
    description: "AI-powered document management with intelligent classification, OCR, and search",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en">
            <body>
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
