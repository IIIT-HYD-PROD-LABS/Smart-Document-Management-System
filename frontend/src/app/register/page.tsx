"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import toast from "react-hot-toast";
import Link from "next/link";

export default function RegisterPage() {
    const [form, setForm] = useState({ email: "", username: "", password: "", full_name: "" });
    const [loading, setLoading] = useState(false);
    const { register } = useAuth();
    const router = useRouter();

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) =>
        setForm({ ...form, [e.target.name]: e.target.value });

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (form.password.length < 6) { toast.error("Password must be at least 6 characters"); return; }
        setLoading(true);
        try {
            await register(form);
            toast.success("Account created");
            router.push("/dashboard");
        } catch (err: any) {
            toast.error(err.response?.data?.detail || "Registration failed");
        } finally {
            setLoading(false);
        }
    };

    const fields = [
        { name: "full_name", label: "Full name", type: "text", placeholder: "John Doe", required: false },
        { name: "username", label: "Username", type: "text", placeholder: "johndoe", required: true },
        { name: "email", label: "Email", type: "email", placeholder: "you@example.com", required: true },
        { name: "password", label: "Password", type: "password", placeholder: "Min 6 characters", required: true },
    ];

    return (
        <div className="min-h-screen bg-[#09090b] flex items-center justify-center px-6">
            <div className="w-full max-w-sm">
                <div className="text-center mb-8">
                    <Link href="/" className="text-sm font-semibold text-white tracking-tight">SmartDocs</Link>
                    <h1 className="text-xl font-semibold text-white mt-6">Create account</h1>
                    <p className="text-sm text-[#71717a] mt-1">Start organizing documents with AI</p>
                </div>
                <div className="bg-[#111113] border border-[#27272a] rounded-lg p-6">
                    <form onSubmit={handleSubmit} className="space-y-4">
                        {fields.map((f) => (
                            <div key={f.name}>
                                <label className="text-xs font-medium text-[#a1a1aa] mb-1.5 block">{f.label}</label>
                                <input type={f.type} name={f.name} value={form[f.name as keyof typeof form]} onChange={handleChange} className="w-full px-3 py-2 bg-[#09090b] border border-[#27272a] rounded-md text-sm text-white placeholder:text-[#52525b] focus:outline-none focus:border-[#3f3f46] transition-colors" placeholder={f.placeholder} required={f.required} />
                            </div>
                        ))}
                        <button type="submit" disabled={loading} className="w-full py-2 text-sm font-medium bg-white text-black rounded-md hover:bg-[#e4e4e7] transition-colors disabled:opacity-50 cursor-pointer mt-2">
                            {loading ? "Creating..." : "Create account"}
                        </button>
                    </form>
                </div>
                <p className="text-center text-xs text-[#52525b] mt-5">
                    Have an account?{" "}<Link href="/login" className="text-[#a1a1aa] hover:text-white transition-colors">Sign in</Link>
                </p>
            </div>
        </div>
    );
}
