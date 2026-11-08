// Local test: node cli.mjs examples/taxi.json out.mp4
import fs from "node:fs/promises";
import path from "node:path";
import { render } from "./render.mjs";

const [specFile, out = "out.mp4"] = process.argv.slice(2);
const spec = JSON.parse(await fs.readFile(specFile, "utf8"));
const workDir = path.resolve(".work", path.basename(out, ".mp4"));
const r = await render(spec, { workDir, outFile: path.resolve(out), log: (m) => console.log(m) });
console.log(JSON.stringify(r));
