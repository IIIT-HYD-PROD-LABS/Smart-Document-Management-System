"use client";

import { useAuth } from "@/context/AuthContext";
import { useRouter, usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";
import { FiHome, FiUpload, FiSearch, FiBarChart2, FiLogOut, FiFileText, FiShield, FiShare2, FiMenu, FiX } from "react-icons/fi";

const allNavItems = [
    { href: "/dashboard", icon: FiHome, label: "Overview", roles: ["admin", "editor", "viewer"] },
    { href: "/dashboard/upload", icon: FiUpload, label: "Upload", roles: ["admin", "editor"] },
    { href: "/dashboard/documents", icon: FiFileText, label: "Documents", roles: ["admin", "editor", "viewer"] },
    { href: "/dashboard/shared", icon: FiShare2, label: "Shared with me", roles: ["admin", "editor", "viewer"] },
    { href: "/dashboard/search", icon: FiSearch, label: "Search", roles: ["admin", "editor", "viewer"] },
    { href: "/dashboard/analytics", icon: FiBarChart2, label: "Analytics", roles: ["admin", "editor", "viewer"] },
    { href: "/dashboard/admin", icon: FiShield, label: "Admin", roles: ["admin"] },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
    const { user, isLoading, logout } = useAuth();
    const router = useRouter();
    const pathname = usePathname();
    const [sidebarOpen, setSidebarOpen] = useState(false);

    useEffect(() => {
        if (!isLoading && !user) router.push("/login");
    }, [user, isLoading, router]);

    // Close sidebar on route change (mobile)
    useEffect(() => {
        setSidebarOpen(false);
    }, [pathname]);

    if (isLoading) {
        return (
            <div className="min-h-screen bg-[#09090b] flex items-center justify-center">
                <div className="w-5 h-5 border-2 border-[#27272a] border-t-[#a1a1aa] rounded-full animate-spin" />
            </div>
        );
    }

    if (!user) {
        return null;
    }

    const navItems = allNavItems.filter(item => item.roles.includes(user.role || "viewer"));

    return (
        <div className="min-h-screen bg-[#09090b] flex">
            {/* Mobile top bar */}
            <div className="fixed top-0 left-0 right-0 h-14 bg-[#09090b] border-b border-[#1f1f23] flex items-center px-4 z-50 md:hidden">
                <button onClick={() => setSidebarOpen(true)} className="text-[#a1a1aa] hover:text-white p-1">
                    <FiMenu className="w-5 h-5" />
                </button>
                <span className="ml-3 text-sm font-semibold text-white tracking-tight">SmartDocs</span>
            </div>

            {/* Sidebar backdrop (mobile) */}
            {sidebarOpen && (
                <div
                    className="fixed inset-0 bg-black/60 z-40 md:hidden"
                    onClick={() => setSidebarOpen(false)}
                />
            )}

            {/* Sidebar */}
            <aside className={`
                w-56 fixed left-0 top-0 h-full bg-[#09090b] border-r border-[#1f1f23] flex flex-col z-50
                transition-transform duration-200 ease-in-out
                ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
                md:translate-x-0
            `}>
                <div className="px-5 h-14 flex items-center justify-between border-b border-[#1f1f23]">
                    <Link href="/dashboard" className="text-sm font-semibold text-white tracking-tight">
                        SmartDocs
                    </Link>
                    <button onClick={() => setSidebarOpen(false)} className="text-[#71717a] hover:text-white md:hidden">
                        <FiX className="w-4 h-4" />
                    </button>
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
                            <p className="text-[11px] text-[#52525b] truncate">
                                {user.email}
                                {user.role && (
                                    <span className="ml-1 px-1.5 py-0.5 rounded text-[9px] bg-[#27272a] text-[#71717a] uppercase">
                                        {user.role}
                                    </span>
                                )}
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={async () => { await logout(); router.push("/login"); }}
                        className="w-full flex items-center gap-2 px-3 py-1.5 text-[13px] text-[#52525b] hover:text-[#ef4444] rounded-md hover:bg-[#111113] transition-colors cursor-pointer"
                    >
                        <FiLogOut className="w-3.5 h-3.5" />
                        Sign out
                    </button>
                </div>
            </aside>

            <main className="flex-1 md:ml-56 ml-0 p-6 md:p-8 mt-14 md:mt-0">
                <div className="max-w-5xl">
                    {children}
                </div>
            </main>
        </div>
    );
}
