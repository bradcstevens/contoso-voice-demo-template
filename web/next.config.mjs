import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  devIndicators: false,
  output: "standalone",
  outputFileTracingRoot: resolve(__dirname, ".."),
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "mm.digikey.com",
        pathname: "/**",
      },
    ],
  },
};
 
export default nextConfig;

