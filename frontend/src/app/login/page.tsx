"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import toast from "react-hot-toast";
import Link from "next/link";

export default function LoginPage() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [loading, setLoading] = useState(false);
    const { login } = useAuth();
    const router = useRouter();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        try {
            await login(email, password);
            toast.success("Welcome back");
            router.push("/dashboard");
        } catch (err: any) {
            toast.error(err.response?.data?.detail || "Login failed");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-[#09090b] flex items-center justify-center px-6">
            <div className="w-full max-w-sm">
                <div className="text-center mb-8">
                    <Link href="/" className="text-sm font-semibold text-white tracking-tight">SmartDocs</Link>
                    <h1 className="text-xl font-semibold text-white mt-6">Sign in</h1>
                    <p className="text-sm text-[#71717a] mt-1">Welcome back to your account</p>
                </div>
                <div className="bg-[#111113] border border-[#27272a] rounded-lg p-6">
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div>
                            <label className="text-xs font-medium text-[#a1a1aa] mb-1.5 block">Email</label>
                            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full px-3 py-2 bg-[#09090b] border border-[#27272a] rounded-md text-sm text-white placeholder:text-[#52525b] focus:outline-none focus:border-[#3f3f46] transition-colors" placeholder="you@example.com" required />
                        </div>
                        <div>
                            <label className="text-xs font-medium text-[#a1a1aa] mb-1.5 block">Password</label>
                            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full px-3 py-2 bg-[#09090b] border border-[#27272a] rounded-md text-sm text-white placeholder:text-[#52525b] focus:outline-none focus:border-[#3f3f46] transition-colors" placeholder="Enter your password" required />
                        </div>
                        <button type="submit" disabled={loading} className="w-full py-2 text-sm font-medium bg-white text-black rounded-md hover:bg-[#e4e4e7] transition-colors disabled:opacity-50 cursor-pointer mt-2">
                            {loading ? "Signing in..." : "Sign in"}
                        </button>
                    </form>
                </div>
                <p className="text-center text-xs text-[#52525b] mt-5">
                    No account?{" "}<Link href="/register" className="text-[#a1a1aa] hover:text-white transition-colors">Create one</Link>
                </p>
            </div>
        </div>
    );
}
