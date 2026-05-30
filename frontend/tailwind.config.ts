import type { Config } from "tailwindcss";

const config: Config = {
    content: [
        "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
        "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
        "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    ],
    theme: {
        extend: {
            fontFamily: {
                sans: ["var(--font-plex-sans)", "IBM Plex Sans", "system-ui", "-apple-system", "sans-serif"],
                mono: ["var(--font-plex-mono)", "IBM Plex Mono", "ui-monospace", "monospace"],
            },
        },
    },
    plugins: [],
};

export default config;
