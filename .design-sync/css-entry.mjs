// Builds ui/dist-lib/design-sync.css, the stylesheet design-sync ships (cfg.cssEntry).
//
// The components rely on the global ui/src/styles.css and on rules in ui/src/styles/*.css. Some of those
// files are imported by a component (the library build emits them into ui/dist-lib/index.css) and some only
// by a view (the library build leaves them out), but a component such as RunRow uses the classes of work.css
// either way. So the shipped stylesheet is: the global rules first (the Google Fonts @import must stay at the
// top), then every ui/src/styles/*.css in name order, then the library build's own CSS (identical rules where it
// repeats a file, so the repetition changes nothing). Run it after `npm run build:lib` (cfg.buildCmd).
import { readFileSync, writeFileSync, existsSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ui = join(dirname(fileURLToPath(import.meta.url)), '..', 'ui');
const global = join(ui, 'src', 'styles.css');
const dir = join(ui, 'src', 'styles');
const lib = join(ui, 'dist-lib', 'index.css');
if (!existsSync(lib)) {
  console.error(`design-sync css: ${lib} is missing; run "npm run build:lib" in ui/ first`);
  process.exit(1);
}
const parts = [readFileSync(global, 'utf8')];
for (const name of readdirSync(dir).filter((n) => n.endsWith('.css')).sort()) {
  parts.push(`/* ui/src/styles/${name} */\n${readFileSync(join(dir, name), 'utf8')}`);
}
parts.push(`/* per-component rules from the library build (dist-lib/index.css) */\n${readFileSync(lib, 'utf8')}`);
const out = join(ui, 'dist-lib', 'design-sync.css');
writeFileSync(out, parts.join('\n\n') + '\n');
console.log(`wrote ${out} (${parts.length - 2} files from ui/src/styles)`);
