// The few Node modules the build plugin (pdfjs-assets.ts) uses; the console has no @types/node.
declare module "node:fs" {
  export function readdirSync(path: string, opts: { withFileTypes: true }): { name: string; isDirectory(): boolean }[];
  export function readFileSync(path: string): Uint8Array;
  export function existsSync(path: string): boolean;
}
declare module "node:path" {
  export function join(...parts: string[]): string;
  export function resolve(...parts: string[]): string;
}
