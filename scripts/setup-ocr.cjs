'use strict';

const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const modules = path.join(root, 'node_modules');
const output = path.join(root, 'static', 'assets', 'ocr');
const languages = ['eng', 'vie', 'khm'];

function metadata(name, version) {
  const value = JSON.parse(fs.readFileSync(path.join(modules, name, 'package.json'), 'utf8'));
  if (value.version !== version) throw new Error(`Expected ${name}@${version}; run npm ci first.`);
  return value;
}

metadata('tesseract.js', '7.0.0');
metadata('tesseract.js-core', '7.0.0');
for (const lang of languages) metadata(`@tesseract.js-data/${lang}`, '1.0.0');

// No build-time download, patched engine, source maps, legacy engine, or Node code.
const files = [
  ['tesseract.js/dist/tesseract.min.js', 'tesseract.min.js'],
  ['tesseract.js/dist/worker.min.js', 'worker.min.js'],
  ['tesseract.js/LICENSE.md', 'tesseract.LICENSE.txt'],
  ['tesseract.js/dist/tesseract.min.js.LICENSE.txt', 'tesseract.min.js.LICENSE.txt'],
  ['tesseract.js/dist/worker.min.js.LICENSE.txt', 'worker.min.js.LICENSE.txt'],
  ['tesseract.js-core/LICENSE', 'tesseract-core.LICENSE.txt'],
];
for (const variant of ['lstm', 'simd-lstm', 'relaxedsimd-lstm']) {
  // The worker selects *.wasm.js. Use the byte-identical separate-WASM loader
  // under that name, avoiding the larger base64-embedded WASM distribution.
  const stem = `tesseract-core-${variant}`;
  files.push([`tesseract.js-core/${stem}.js`, `${stem}.wasm.js`]);
  files.push([`tesseract.js-core/${stem}.wasm`, `${stem}.wasm`]);
}
for (const lang of languages) {
  files.push([`@tesseract.js-data/${lang}/4.0.0_best_int/${lang}.traineddata.gz`, `${lang}.traineddata.gz`]);
  // These npm packages declare MIT but ship no standalone LICENSE. Preserve
  // their complete license/author/repository metadata rather than inventing it.
  files.push([`@tesseract.js-data/${lang}/package.json`, `${lang}.LICENSE.json`]);
}

// Fail before copying anything when the installation is incomplete.
for (const [source] of files) {
  if (!fs.statSync(path.join(modules, source)).isFile()) throw new Error(`Missing OCR asset: ${source}`);
}
fs.mkdirSync(output, { recursive: true });
if (fs.lstatSync(output).isSymbolicLink()) throw new Error('OCR output must not be a symlink.');
let size = 0;
for (const [source, name] of files) {
  const destination = path.join(output, name);
  if (fs.existsSync(destination) && fs.lstatSync(destination).isSymbolicLink()) {
    throw new Error(`Refusing symlink: ${name}`);
  }
  fs.copyFileSync(path.join(modules, source), destination);
  size += fs.statSync(destination).size;
}
console.log(`Provisioned ${files.length} local OCR assets/licenses: ${size} bytes (${(size / 1024 / 1024).toFixed(2)} MiB).`);
console.log('OCR uses only /ocr.js and /assets/ocr/ on this origin; npm is not needed at runtime.');
