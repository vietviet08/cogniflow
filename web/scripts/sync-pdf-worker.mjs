import fs from "node:fs";
import path from "node:path";

const rootDir = process.cwd();
const packageJsonPath = path.join(
  rootDir,
  "node_modules",
  "pdfjs-dist",
  "package.json",
);
const source = path.join(
  rootDir,
  "node_modules",
  "pdfjs-dist",
  "build",
  "pdf.worker.min.mjs",
);
const destinationDir = path.join(rootDir, "public");
const destination = path.join(destinationDir, "pdf.worker.mjs");

if (!fs.existsSync(packageJsonPath) || !fs.existsSync(source)) {
  console.error("pdfjs-dist is not installed. Unable to sync pdf.worker.mjs.");
  process.exit(1);
}

const { version } = JSON.parse(fs.readFileSync(packageJsonPath, "utf8"));

fs.mkdirSync(destinationDir, { recursive: true });
fs.copyFileSync(source, destination);
console.log(`Synced pdf.worker.mjs from pdfjs-dist@${version}`);
