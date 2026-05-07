"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

/**
 * ThemeContext — owns the data-theme attribute on <html> and persists the
 * user's preference to localStorage. Defaults to "light" per stakeholder
 * feedback that the dark Compliance Noir aesthetic feels too minimalist
 * for an enterprise audience.
 *
 * Resolves "system" by listening to (prefers-color-scheme: dark).
 */
export type ThemePreference = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

interface ThemeContextValue {
    /** What the user picked: light/dark/system */
    preference: ThemePreference;
    /** What's actually on the DOM right now (system resolved) */
    resolved: ResolvedTheme;
    /** Set the preference (persists to localStorage) */
    setPreference: (p: ThemePreference) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

const STORAGE_KEY = "taxsync.theme";

function resolveSystem(): ResolvedTheme {
    if (typeof window === "undefined") return "light";
    return window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light";
}

function applyTheme(resolved: ResolvedTheme) {
    if (typeof document === "undefined") return;
    document.documentElement.setAttribute("data-theme", resolved);
    document.documentElement.style.colorScheme = resolved;
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
    // We initialize to "light" so the SSR markup always matches the
    // ThemeBootstrap inline script (which also defaults to light when no
    // localStorage value exists).
    const [preference, setPreferenceState] = useState<ThemePreference>("light");
    const [resolved, setResolved] = useState<ResolvedTheme>("light");

    // Hydrate from localStorage on mount
    useEffect(() => {
        let stored: ThemePreference = "light";
        try {
            const v = localStorage.getItem(STORAGE_KEY);
            if (v === "light" || v === "dark" || v === "system") stored = v;
        } catch {
            // localStorage unavailable (private mode etc) — silently default
        }
        setPreferenceState(stored);
        const initial = stored === "system" ? resolveSystem() : stored;
        setResolved(initial);
        applyTheme(initial);
    }, []);

    // Listen for system theme changes when preference is "system"
    useEffect(() => {
        if (preference !== "system" || typeof window === "undefined") return;
        const mq = window.matchMedia("(prefers-color-scheme: dark)");
        const handler = () => {
            const next: ResolvedTheme = mq.matches ? "dark" : "light";
            setResolved(next);
            applyTheme(next);
        };
        mq.addEventListener("change", handler);
        return () => mq.removeEventListener("change", handler);
    }, [preference]);

    const setPreference = (next: ThemePreference) => {
        setPreferenceState(next);
        try {
            localStorage.setItem(STORAGE_KEY, next);
        } catch {
            // ignore
        }
        const r = next === "system" ? resolveSystem() : next;
        setResolved(r);
        applyTheme(r);
    };

    const value = useMemo<ThemeContextValue>(
        () => ({ preference, resolved, setPreference }),
        [preference, resolved]
    );

    return (
        <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
    );
}

export function useTheme(): ThemeContextValue {
    const ctx = useContext(ThemeContext);
    if (!ctx) {
        throw new Error("useTheme must be used inside <ThemeProvider>");
    }
    return ctx;
}

/**
 * Inline script string — runs BEFORE React hydrates, in <head>, to apply
 * the persisted theme synchronously. Prevents the dreaded flash-of-wrong-
 * theme on first paint.
 */
export const THEME_BOOTSTRAP_SCRIPT = `
(function(){
  try {
    var k = "${STORAGE_KEY}";
    var p = localStorage.getItem(k);
    if (p !== "light" && p !== "dark" && p !== "system") p = "light";
    var r = p === "system"
      ? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
      : p;
    document.documentElement.setAttribute("data-theme", r);
    document.documentElement.style.colorScheme = r;
  } catch(e) {
    document.documentElement.setAttribute("data-theme", "light");
  }
})();
`;
