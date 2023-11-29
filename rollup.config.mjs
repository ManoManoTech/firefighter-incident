import { babel } from "@rollup/plugin-babel";
import commonjs from "@rollup/plugin-commonjs";
import { nodeResolve } from "@rollup/plugin-node-resolve";
import terser from "@rollup/plugin-terser";

/** @type {import('rollup').RollupOptions} */
export default {

    input: "src/incidents/static/js/main.js",
    output: {
        file: "src/incidents/static/js/main.min.js",
        format: "iife",
        entryFileNames: "[name].js", // currently does not work for the legacy bundle
        assetFileNames: "[name].[ext]", // currently does not work for images
    },
    plugins: [
        nodeResolve({
            browser: true,
            jsnext: true,
            main: true,
        }),
        commonjs(),
        babel({ babelHelpers: "bundled" }), // transpilation
        terser(), // minification
    ],
};
