const colors = require("tailwindcss/colors");
/** @type {import('tailwindcss').Config} */
module.exports = {
    theme: {
        extend: {
            colors: {
                neutral: colors.neutral,
                "base-warning": "#fef08a",
            },
            typography: {
                DEFAULT: {
                    css: {
                        p: {
                            marginTop: "1em",
                            marginBottom: ".8em",
                        },
                        li: {
                            marginTop: ".25em",
                            marginBottom: ".25em",
                        },
                        "code::before": {content: ""},
                        "code::after": {content: ""},
                    },
                },
            },
        },
        screens: {
            sm: "640px",
            md: "768px",
            lg: "1024px",
            xl: "1280px",
            "2xl": "1536px",
        },
    },
    variants: {
        extend: {
            backgroundColor: ["odd", "even"],
        },
    },
    darkMode: "media",
    plugins: [
        require("@tailwindcss/forms"),
        require("@tailwindcss/line-clamp"),
        require("@tailwindcss/aspect-ratio"),
        require("@tailwindcss/typography"),
        require("daisyui"),
    ],
    daisyui: {
        styled: true,
        themes: [
            {
                light: {

                    "base-100": "#ffffff",
                    "base-200": "#F9F9F9",
                    "base-300": "#E5E6E6",
                },
            },
            "wireframe",
            {
                darkff: {
                    ...require("daisyui/src/theming/themes")["dark"],
                    "color-scheme": "dark",
                    primary: "#4F46E5",
                    "primary-content": "#ffffff",
                    secondary: "#f000b8",
                    "secondary-content": "#ffffff",
                    accent: "#37cdbe",
                    "accent-content": "#163835",
                    neutral: "#1b1d1d",
                    "base-100": "#1b1d1d",
                    "base-200": "#212121",
                    "base-300": "#2c2c2c",
                    "base-content": "#E5E5E5",
                    info: "#2563eb",
                    success: "#16a34a",
                    warning: "#d97706",
                    "base-warning": "#fcd34d",
                    error: "#dc2626",
                },
            },
            "dark",
        ],
        base: true,
        utils: true,
        logs: true,
        rtl: false,
        prefix: "",
        darkTheme: "darkff",
    },

    content: [
        // Ignore some dirs
        "!.idea",
        "!.vscode",
        "!**/migrations/*",
        "!dist",
        "!.git",
        // Ignore all minified files
        "!./**/*.min.js",
        "!./**/*.min.css",
        // Ignore files in node_modules
        "!node_modules",
        // Templates within theme app (e.g. base.html)
        "./**/templates/**/*.html",
        "./**/components/**/*.html",
        // Include Python files that might contain Tailwind CSS classes
        "./**/*.py",
        // Include JavaScript files that might contain Tailwind CSS classes
        // './**/*.js',
    ],
};
