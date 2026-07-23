import nextEnv from "@next/env";

const { loadEnvConfig } = nextEnv;
loadEnvConfig(process.cwd());

const required = [
  "NEXT_PUBLIC_API_URL",
  "NEXT_PUBLIC_SUPABASE_URL",
  "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
];
const forbiddenPublicNames = /(SECRET|SERVICE|OPENAI|GEMINI|SERPAPI)/i;

const missing = required.filter((name) => !process.env[name]?.trim());
const exposedSecrets = Object.keys(process.env).filter(
  (name) => name.startsWith("NEXT_PUBLIC_") && forbiddenPublicNames.test(name),
);

if (missing.length > 0 || exposedSecrets.length > 0) {
  if (missing.length > 0) {
    console.error(`Hiányzó frontend környezeti változók: ${missing.join(", ")}`);
  }
  if (exposedSecrets.length > 0) {
    console.error(
      `Tiltott publikus titoknév: ${exposedSecrets.join(", ")}`,
    );
  }
  process.exit(1);
}

for (const name of ["NEXT_PUBLIC_API_URL", "NEXT_PUBLIC_SUPABASE_URL"]) {
  try {
    new URL(process.env[name]);
  } catch {
    console.error(`A(z) ${name} nem érvényes URL.`);
    process.exit(1);
  }
}

console.log("A frontend környezeti változói rendben vannak.");
