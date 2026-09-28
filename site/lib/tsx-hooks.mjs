// Module hooks for `npm test`: node strips types from .ts itself but can't compile JSX or follow the bundler's
// extensionless imports. https://nodejs.org/api/module.html#customization-hooks
import { existsSync, readFileSync, statSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import ts from "typescript";

const EXTENSIONS = [".ts", ".tsx"];
const COMPILER_OPTIONS = {
  jsx: ts.JsxEmit.ReactJSX,
  module: ts.ModuleKind.ESNext,
  target: ts.ScriptTarget.ES2022,
};

const isFile = (path) => existsSync(path) && statSync(path).isFile();

function sourceFile(url) {
  const path = fileURLToPath(url);
  if (isFile(path)) return url.href;
  const found = EXTENSIONS.map((extension) => path + extension).find(isFile);
  return found ? pathToFileURL(found).href : null;
}

function localUrl(specifier, parentURL) {
  return specifier.startsWith(".") && parentURL ? new URL(specifier, parentURL) : null;
}

export async function resolve(specifier, context, nextResolve) {
  const local = localUrl(specifier, context.parentURL);
  const url = local && sourceFile(local);
  return url ? { url, shortCircuit: true } : nextResolve(specifier, context);
}

export async function load(url, context, nextLoad) {
  if (!url.endsWith(".tsx")) return nextLoad(url, context);
  const fileName = fileURLToPath(url);
  const { outputText } = ts.transpileModule(readFileSync(fileName, "utf8"), { compilerOptions: COMPILER_OPTIONS, fileName });
  return { format: "module", source: outputText, shortCircuit: true };
}
