"use client";

import { useState, useEffect } from "react";
import { settingsApi } from "@/lib/api";
import toast from "react-hot-toast";

interface LLMSettings {
    llm_provider: string;
    model_name: string | null;
    api_key_set: boolean;
    api_key_last4: string | null;
    ollama_base_url: string | null;
}

const PROVIDERS = [
    {
        id: "gemini",
        name: "Google Gemini",
        badge: "Free tier",
        description: "Google's multimodal AI. Free tier available with generous limits.",
        defaultModel: "gemini-2.0-flash",
    },
    {
        id: "openai",
        name: "OpenAI",
        badge: "Paid",
        description: "GPT models with strong document understanding capabilities.",
        defaultModel: "gpt-4o-mini",
    },
    {
        id: "anthropic",
        name: "Anthropic",
        badge: "Paid",
        description: "Claude models known for careful, detailed extraction.",
        defaultModel: "claude-sonnet-4-20250514",
    },
    {
        id: "local",
        name: "Local Only",
        badge: "Free",
        description: "Run models locally via Ollama. No API key needed.",
        defaultModel: "llama3",
    },
];

export default function SettingsPage() {
    const [settings, setSettings] = useState<LLMSettings | null>(null);
    const [selectedProvider, setSelectedProvider] = useState("gemini");
    const [modelName, setModelName] = useState("");
    const [apiKey, setApiKey] = useState("");
    const [ollamaUrl, setOllamaUrl] = useState("");
    const [saving, setSaving] = useState(false);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        settingsApi
            .getLLMSettings()
            .then(({ data }) => {
                setSettings(data);
                setSelectedProvider(data.llm_provider || "gemini");
                setModelName(data.model_name || "");
                setOllamaUrl(data.ollama_base_url || "");
            })
            .catch(() => {
                // Use defaults on error (new user with no settings)
            })
            .finally(() => setLoading(false));
    }, []);

    const currentProviderConfig = PROVIDERS.find((p) => p.id === selectedProvider);

    const handleSave = async () => {
        setSaving(true);
        try {
            const payload: {
                llm_provider: string;
                model_name?: string | null;
                api_key?: string | null;
                ollama_base_url?: string | null;
            } = {
                llm_provider: selectedProvider,
                model_name: modelName || null,
                ollama_base_url: selectedProvider === "local" ? ollamaUrl || null : null,
            };

            // Only send api_key if user typed a new one
            if (apiKey.trim()) {
                payload.api_key = apiKey;
            }

            const { data } = await settingsApi.updateLLMSettings(payload);
            setSettings(data);
            setApiKey(""); // Clear the input after save
            toast.success("Settings saved");
        } catch (err: any) {
            const detail = err?.response?.data?.detail;
            if (Array.isArray(detail)) {
                toast.error(detail.map((d: any) => d.msg).join(", "));
            } else {
                toast.error(detail || "Failed to save settings");
            }
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center py-24">
                <div className="w-5 h-5 border-2 border-[#27272a] border-t-[#a1a1aa] rounded-full animate-spin" />
            </div>
        );
    }

    return (
        <div>
            <div className="mb-8">
                <h1 className="text-lg font-semibold text-white">AI Provider Settings</h1>
                <p className="text-sm text-[#52525b] mt-1">
                    Configure which LLM provider to use for document extraction. Google Gemini has a free tier.
                </p>
            </div>

            {/* Provider Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-8">
                {PROVIDERS.map((provider) => {
                    const isActive = selectedProvider === provider.id;
                    return (
                        <button
                            key={provider.id}
                            onClick={() => setSelectedProvider(provider.id)}
                            className={`text-left p-4 rounded-lg border transition-colors cursor-pointer ${
                                isActive
                                    ? "bg-[#18181b] border-white"
                                    : "bg-[#18181b] border-[#27272a] hover:border-[#3f3f46]"
                            }`}
                        >
                            <div className="flex items-center gap-2 mb-1">
                                <span className="text-sm font-medium text-white">{provider.name}</span>
                                <span
                                    className={`text-[10px] px-1.5 py-0.5 rounded ${
                                        provider.badge === "Free tier" || provider.badge === "Free"
                                            ? "bg-[#10b981]/10 text-[#10b981]"
                                            : "bg-[#f59e0b]/10 text-[#f59e0b]"
                                    }`}
                                >
                                    {provider.badge}
                                </span>
                            </div>
                            <p className="text-xs text-[#52525b] mb-2">{provider.description}</p>
                            <p className="text-[11px] text-[#3f3f46]">Default: {provider.defaultModel}</p>
                        </button>
                    );
                })}
            </div>

            {/* Configuration Form */}
            <div className="bg-[#18181b] border border-[#27272a] rounded-lg p-6 space-y-5">
                <h2 className="text-sm font-medium text-white">Configuration</h2>

                {/* Model Name */}
                <div>
                    <label className="block text-xs text-[#a1a1aa] mb-1.5">Model name</label>
                    <input
                        type="text"
                        value={modelName}
                        onChange={(e) => setModelName(e.target.value)}
                        placeholder={currentProviderConfig?.defaultModel || "model name"}
                        className="bg-[#09090b] border border-[#27272a] rounded-md px-3 py-2 text-sm text-white w-full placeholder:text-[#3f3f46] focus:outline-none focus:border-[#52525b] transition-colors"
                    />
                    <p className="text-[11px] text-[#3f3f46] mt-1">
                        Leave blank to use the default: {currentProviderConfig?.defaultModel}
                    </p>
                </div>

                {/* API Key or Ollama URL */}
                {selectedProvider === "local" ? (
                    <div>
                        <label className="block text-xs text-[#a1a1aa] mb-1.5">Ollama base URL</label>
                        <input
                            type="text"
                            value={ollamaUrl}
                            onChange={(e) => setOllamaUrl(e.target.value)}
                            placeholder="http://localhost:11434"
                            className="bg-[#09090b] border border-[#27272a] rounded-md px-3 py-2 text-sm text-white w-full placeholder:text-[#3f3f46] focus:outline-none focus:border-[#52525b] transition-colors"
                        />
                    </div>
                ) : (
                    <div>
                        <label className="block text-xs text-[#a1a1aa] mb-1.5">API key</label>
                        <input
                            type="password"
                            value={apiKey}
                            onChange={(e) => setApiKey(e.target.value)}
                            placeholder={
                                settings?.api_key_set && settings?.api_key_last4
                                    ? `API key stored (ends in ****${settings.api_key_last4})`
                                    : "Enter your API key"
                            }
                            className="bg-[#09090b] border border-[#27272a] rounded-md px-3 py-2 text-sm text-white w-full placeholder:text-[#3f3f46] focus:outline-none focus:border-[#52525b] transition-colors"
                        />
                        {settings?.api_key_set && (
                            <p className="text-[11px] text-[#10b981] mt-1">
                                Key is stored (ends in ****{settings.api_key_last4}). Leave blank to keep current key.
                            </p>
                        )}
                    </div>
                )}

                {/* Save Button */}
                <div className="pt-2">
                    <button
                        onClick={handleSave}
                        disabled={saving}
                        className="bg-white text-black hover:bg-[#e4e4e7] rounded-md px-4 py-2 text-sm font-medium disabled:opacity-50 transition-colors cursor-pointer"
                    >
                        {saving ? "Saving..." : "Save settings"}
                    </button>
                </div>
            </div>
        </div>
    );
}
