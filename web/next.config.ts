import type { NextConfig } from "next";

const nextConfig: NextConfig = {
    reactStrictMode: true,
    output: "export",
    // serverExternalPackages: ["pdfjs-dist"],
    // webpack: (config) => {
    //   config.resolve.alias.canvas = false;
    //   config.resolve.alias.encoding = false;
    //   return config;
    // },
};

export default nextConfig;
