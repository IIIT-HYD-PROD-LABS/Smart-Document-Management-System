"use client";

import { useEffect, useRef, useState } from "react";
import { FiSun, FiMoon, FiMonitor, FiChevronDown } from "react-icons/fi";
import { useTheme, type ThemePreference } from "@/context/ThemeContext";

const OPTIONS: Array<{
    value: ThemePreference;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
}> = [
    { value: "light", label: "Light", icon: FiSun },
    { value: "dark", label: "Dark", icon: FiMoon },
    { value: "system", label: "System", icon: FiMonitor },
];

/**
 * Header dropdown for Light / Dark / System theme. Used in the dashboard
 * topbar. Keyboard navigable, click-outside to close.
 */
export function ThemeToggle() {
    const { preference, setPreference } = useTheme();
    const [open, setOpen] = useState(false);
    const ref = useRef<HTMLDivElement>(null);

    const current = OPTIONS.find((o) => o.value === preference) ?? OPTIONS[0];
    const CurrentIcon = current.icon;

    useEffect(() => {
        if (!open) return;
        const onClick = (e: MouseEvent) => {
            if (ref.current && !ref.current.contains(e.target as Node)) {
                setOpen(false);
            }
        };
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "Escape") setOpen(false);
        };
        document.addEventListener("mousedown", onClick);
        document.addEventListener("keydown", onKey);
        return () => {
            document.removeEventListener("mousedown", onClick);
            document.removeEventListener("keydown", onKey);
        };
    }, [open]);

    return (
        <div className="relative" ref={ref}>
            <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                aria-haspopup="menu"
                aria-expanded={open}
                aria-label={`Theme: ${current.label}. Click to change.`}
                className="
                    inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md
                    border border-[var(--border-default)]
                    bg-[var(--bg-elevated)]
                    text-[13px] text-[var(--text-secondary)]
                    hover:bg-[var(--bg-hover)] hover:border-[var(--border-emphasis)]
                    transition-colors duration-150 cursor-pointer
                "
            >
                <CurrentIcon className="w-3.5 h-3.5" aria-hidden />
                <span className="hidden sm:inline">{current.label}</span>
                <FiChevronDown className="w-3 h-3 opacity-70" aria-hidden />
            </button>

            {open && (
                <div
                    role="menu"
                    className="
                        absolute right-0 mt-1.5 w-40 rounded-md py-1
                        bg-[var(--bg-elevated)] border border-[var(--border-default)]
                        shadow-[var(--shadow-lg)] z-50
                    "
                >
                    {OPTIONS.map((opt) => {
                        const Icon = opt.icon;
                        const active = opt.value === preference;
                        return (
                            <button
                                key={opt.value}
                                role="menuitemradio"
                                aria-checked={active}
                                onClick={() => {
                                    setPreference(opt.value);
                                    setOpen(false);
                                }}
                                className={`
                                    w-full flex items-center gap-2.5 px-3 py-1.5
                                    text-[13px] text-left cursor-pointer
                                    transition-colors duration-100
                                    ${
                                        active
                                            ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                                            : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
                                    }
                                `}
                            >
                                <Icon className="w-3.5 h-3.5" aria-hidden />
                                <span className="flex-1">{opt.label}</span>
                                {active && (
                                    <span
                                        className="w-1.5 h-1.5 rounded-full bg-[var(--accent)]"
                                        aria-hidden
                                    />
                                )}
                            </button>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
