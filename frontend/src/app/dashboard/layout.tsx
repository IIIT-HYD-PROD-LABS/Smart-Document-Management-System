"use client";

import { useAuth } from "@/context/AuthContext";
import { useRouter, usePathname } from "next/navigation";
import { useEffect } from "react";
import Link from "next/link";
import { FiHome, FiUpload, FiSearch, FiBarChart2, FiLogOut, FiFileText } from "react-icons/fi";

const navItems = [
    { href: "/dashboard", icon: FiHome, label: "Overview" },
    { href: "/dashboard/upload", icon: FiUpload, label: "Upload" },
    { href: "/dashboard/documents", icon: FiFileText, label: "Documents" },
    { href: "/dashboard/search", icon: FiSearch, label: "Search" },
    { href: "/dashboard/analytics", icon: FiBarChart2, label: "Analytics" },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
    const { user, isLoading, logout } = useAuth();
    const router = useRouter();
    const pathname = usePathname();

    useEffect(() => {
        if (!isLoading && !user) router.push("/login");
    }, [user, isLoading, router]);

    if (isLoading || !user) {
        return (
            <div className="min-h-screen bg-[#09090b] flex items-center justify-center">
                <div className="w-5 h-5 border-2 border-[#27272a] border-t-[#a1a1aa] rounded-full animate-spin" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-[#09090b] flex">
            <aside className="w-56 fixed left-0 top-0 h-full bg-[#09090b] border-r border-[#1f1f23] flex flex-col z-40">
                <div className="px-5 h-14 flex items-center border-b border-[#1f1f23]">
                    <Link href="/dashboard" className="text-sm font-semibold text-white tracking-tight">
                        SmartDocs
                    </Link>
                </div>

                <nav className="flex-1 py-3 px-2">
                    {navItems.map((item) => {
                        const isActive = pathname === item.href;
                        return (
                            <Link
                                key={item.href}
                                href={item.href}
                                className={`flex items-center gap-2.5 px-3 py-2 rounded-md text-[13px] transition-colors cursor-pointer mb-0.5 ${
                                    isActive
                                        ? "bg-[#18181b] text-white font-medium"
                                        : "text-[#71717a] hover:text-[#a1a1aa] hover:bg-[#111113]"
                                }`}
                            >
                                <item.icon className="w-4 h-4" />
                                {item.label}
                            </Link>
                        );
                    })}
                </nav>

                <div className="border-t border-[#1f1f23] p-3">
                    <div className="flex items-center gap-2.5 px-2 mb-3">
                        <div className="w-7 h-7 rounded-full bg-[#18181b] border border-[#27272a] flex items-center justify-center text-[11px] font-medium text-[#a1a1aa]">
                            {user.username?.[0]?.toUpperCase() || "U"}
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="text-[13px] font-medium text-white truncate">{user.username}</p>
                            <p className="text-[11px] text-[#52525b] truncate">{user.email}</p>
                        </div>
                    </div>
                    <button
                        onClick={() => { logout(); router.push("/login"); }}
                        className="w-full flex items-center gap-2 px-3 py-1.5 text-[13px] text-[#52525b] hover:text-[#ef4444] rounded-md hover:bg-[#111113] transition-colors cursor-pointer"
                    >
                        <FiLogOut className="w-3.5 h-3.5" />
                        Sign out
                    </button>
                </div>
            </aside>

            <main className="flex-1 ml-56 p-8">
                <div className="max-w-5xl">
                    {children}
                </div>
            </main>
        </div>
    );
}
