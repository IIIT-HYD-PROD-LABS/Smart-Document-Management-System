"use client";

import { useState } from "react";
import { FiX, FiCheck, FiMail } from "react-icons/fi";
import { earlyAccessApi, extractErrorMessage } from "@/lib/api";
import toast from "react-hot-toast";

interface Props {
    open: boolean;
    onClose: () => void;
}

export default function EarlyAccessModal({ open, onClose }: Props) {
    const [form, setForm] = useState({ full_name: "", email: "", company: "", reason: "" });
    const [submitting, setSubmitting] = useState(false);
    const [submitted, setSubmitted] = useState(false);

    if (!open) return null;

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
        setForm({ ...form, [e.target.name]: e.target.value });

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSubmitting(true);
        try {
            await earlyAccessApi.submit({
                full_name: form.full_name,
                email: form.email,
                company: form.company || undefined,
                reason: form.reason || undefined,
            });
            setSubmitted(true);
        } catch (err) {
            toast.error(extractErrorMessage(err, "Failed to submit request"));
        } finally {
            setSubmitting(false);
        }
    };

    const handleClose = () => {
        setSubmitted(false);
        setForm({ full_name: "", email: "", company: "", reason: "" });
        onClose();
    };

    return (
        <div className="fixed inset-0 z-[60] flex items-center justify-center px-4">
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={handleClose} aria-hidden />

            <div className="relative w-full max-w-md bg-[#111113] border border-[#27272a] rounded-lg shadow-2xl">
                <div className="flex items-center justify-between px-6 pt-5 pb-0">
                    <h2 className="text-base font-semibold text-white">
                        {submitted ? "Request Submitted" : "Join Early Access"}
                    </h2>
                    <button onClick={handleClose} className="text-[#52525b] hover:text-white transition-colors cursor-pointer" aria-label="Close">
                        <FiX className="w-4 h-4" />
                    </button>
                </div>

                {submitted ? (
                    <div className="px-6 py-8 text-center">
                        <div className="w-12 h-12 rounded-full bg-[#10b981]/10 flex items-center justify-center mx-auto mb-4">
                            <FiCheck className="w-6 h-6 text-[#10b981]" />
                        </div>
                        <p className="text-sm text-white font-medium mb-2">We&apos;ve received your request</p>
                        <p className="text-xs text-[#71717a] leading-relaxed max-w-xs mx-auto">
                            Our team will review your application and send you an email with access instructions once approved.
                        </p>
                        <button
                            onClick={handleClose}
                            className="mt-6 px-6 py-2 text-sm font-medium bg-white text-black rounded-md hover:bg-[#e4e4e7] transition-colors cursor-pointer"
                        >
                            Got it
                        </button>
                    </div>
                ) : (
                    <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
                        <p className="text-xs text-[#71717a] -mt-1 mb-2">
                            Fill in your details and we&apos;ll get back to you once your access is approved.
                        </p>
                        <div>
                            <label htmlFor="ea-name" className="text-xs font-medium text-[#a1a1aa] mb-1.5 block">Full name *</label>
                            <input
                                id="ea-name" name="full_name" type="text" required minLength={2}
                                value={form.full_name} onChange={handleChange}
                                placeholder="John Doe"
                                className="w-full px-3 py-2 bg-[#09090b] border border-[#27272a] rounded-md text-sm text-white placeholder:text-[#52525b] focus:outline-none focus:border-[#3f3f46] transition-colors"
                            />
                        </div>
                        <div>
                            <label htmlFor="ea-email" className="text-xs font-medium text-[#a1a1aa] mb-1.5 block">Work email *</label>
                            <div className="relative">
                                <FiMail className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#52525b]" />
                                <input
                                    id="ea-email" name="email" type="email" required
                                    value={form.email} onChange={handleChange}
                                    placeholder="you@company.com"
                                    className="w-full pl-9 pr-3 py-2 bg-[#09090b] border border-[#27272a] rounded-md text-sm text-white placeholder:text-[#52525b] focus:outline-none focus:border-[#3f3f46] transition-colors"
                                />
                            </div>
                        </div>
                        <div>
                            <label htmlFor="ea-company" className="text-xs font-medium text-[#a1a1aa] mb-1.5 block">Company</label>
                            <input
                                id="ea-company" name="company" type="text"
                                value={form.company} onChange={handleChange}
                                placeholder="Acme Corp"
                                className="w-full px-3 py-2 bg-[#09090b] border border-[#27272a] rounded-md text-sm text-white placeholder:text-[#52525b] focus:outline-none focus:border-[#3f3f46] transition-colors"
                            />
                        </div>
                        <div>
                            <label htmlFor="ea-reason" className="text-xs font-medium text-[#a1a1aa] mb-1.5 block">Why are you interested?</label>
                            <textarea
                                id="ea-reason" name="reason"
                                value={form.reason} onChange={handleChange}
                                placeholder="Tell us about your compliance challenges..."
                                rows={3}
                                className="w-full px-3 py-2 bg-[#09090b] border border-[#27272a] rounded-md text-sm text-white placeholder:text-[#52525b] focus:outline-none focus:border-[#3f3f46] transition-colors resize-none"
                            />
                        </div>
                        <button
                            type="submit"
                            disabled={submitting}
                            className="w-full py-2.5 text-sm font-medium bg-white text-black rounded-md hover:bg-[#e4e4e7] transition-colors disabled:opacity-50 cursor-pointer"
                        >
                            {submitting ? "Submitting..." : "Request Early Access"}
                        </button>
                        <p className="text-[11px] text-[#3f3f46] text-center">
                            No credit card required. Free during beta.
                        </p>
                    </form>
                )}
            </div>
        </div>
    );
}
