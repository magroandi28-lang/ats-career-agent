import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Kifejezetten megmondjuk a Next.js-nek, hogy EZ a projekt gyökere --
  // enelkul osszezavarodik, ha a gepen mashol is van package-lock.json.
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
