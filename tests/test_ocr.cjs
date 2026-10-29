'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { spawnSync } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'static', 'ocr.js'), 'utf8');
const { parse } = require('../static/ocr.js');
const plain = value => JSON.parse(JSON.stringify(value));

// Every document string and image header in this suite is fictional/generated.
const golden = 'CMND: DEMO-OCR-0099\nHo va ten: NGUYEN VAN MAU\nNgay sinh: 12/05/1990\nGioi tinh: Nam\nNoi sinh: Tinh Mau\nDia chi: 12 Duong Minh Hoa, Xa Mau';
const expected = {
  cmnd: 'DEMO-OCR-0099', ten_that: 'NGUYEN VAN MAU', ngay_sinh: '1990-05-12',
  gioi_tinh: 'M', noi_sinh: 'Tinh Mau', dia_chi: '12 Duong Minh Hoa, Xa Mau',
};

test('Vietnamese synthetic golden labels populate only six document fields', () => {
  assert.deepEqual(parse(golden), expected);
  assert.deepEqual(parse(golden + '\nNhom mau: O\nRating: 5\nPhong o: A1'), expected);
});

test('accented Vietnamese, bilingual labels and immediate next-line values', () => {
  assert.deepEqual(parse('Số CCCD: DEMO-123\r\nHọ và tên / Full name:\r\nNGUYỄN VĂN MẪU\nNgày tháng năm sinh: 12/05/1990\nGiới tính / Sex: Nữ\nNơi thường trú: Số 5, Đường Mẫu'), {
    cmnd: 'DEMO-123', ten_that: 'NGUYỄN VĂN MẪU', ngay_sinh: '1990-05-12', gioi_tinh: 'F', dia_chi: 'Số 5, Đường Mẫu',
  });
  assert.deepEqual(parse('Họ và tên:\nNgày sinh: 12/05/1990'), { ngay_sinh: '1990-05-12' });
  assert.deepEqual(parse('Address:\nBlood group: O'), {});
});

test('English explicit labels, ISO and named-month dates', () => {
  assert.deepEqual(parse('ID number: DEMO-0099\nFull name: FICTIONAL PERSON\nDate of birth: 1990-05-12\nSex: Female\nPlace of birth: Example City\nPermanent address: 42 Example Road'), {
    cmnd: 'DEMO-0099', ten_that: 'FICTIONAL PERSON', ngay_sinh: '1990-05-12', gioi_tinh: 'F', noi_sinh: 'Example City', dia_chi: '42 Example Road',
  });
  assert.deepEqual(parse('DOB: 12 May 1990'), { ngay_sinh: '1990-05-12' });
  assert.deepEqual(parse('DOB: 21/05/1990'), { ngay_sinh: '1990-05-21' });
  assert.deepEqual(parse('DOB: 05/21/1990'), { ngay_sinh: '1990-05-21' });
  assert.deepEqual(parse('DOB: 12/05/1990'), {});
});

test('no guesses from unlabeled dates, country, home origin, blood or Khmer', () => {
  assert.deepEqual(parse('NGUYEN VAN MAU\n123456789\n12/05/1990\nNam\nQue quan: Tinh Mau\nNationality: Vietnam\nBlood group: O\nSkill: 5\nភាសាខ្មែរ'), {});
  assert.deepEqual(parse('Full name: សុខ'), { ten_that: 'សុខ' });
});

test('malformed, partial, impossible and future dates are omitted', () => {
  for (const value of ['31/04/1990', '29/02/1991', '00/05/1990', '12/00/1990', '12/13/1990', '1990', '12/05/90', '1899-05-12', '2990-05-12', '1990-02-30', '1990-5-12', '12/05-1990', '12/05/1990?', '12 Mayhem 1990']) {
    assert.deepEqual(parse(`Ngay sinh: ${value}`), {}, value);
  }
  assert.deepEqual(parse('Ngay sinh: 29/02/2000'), { ngay_sinh: '2000-02-29' });
  for (const value of ['unknown', 'X', 'Nam/Nu', 'Female?', 'constructor', '__proto__']) assert.deepEqual(parse(`Sex: ${value}`), {});
});

test('conflicting candidates are omitted instead of silently overwritten', () => {
  assert.deepEqual(parse('CMND: DEMO-001\nCMND: DEMO-002\nCMND: DEMO-001'), {});
  assert.deepEqual(parse('CMND: DEMO-001\nCMND: DEMO-001'), { cmnd: 'DEMO-001' });
});

test('phone-photo noise around labels still fills the six document fields', () => {
  const text = [
    'CONG HÒA XÃ HOI CHỦ NGHĨA VIỆT NAM',
    'CHUNG MINH NHAN DAN',
    '| Ngày sinh: 12/05/1990',
    ': | Giới tính: Nam',
    '| Nơi sinh: Tình Mẫu',
    '| Dia chỉ thường trú" Số 12, Đường Minh Hoa, Xã M',
    'sb: DEMO-123456789',
  ].join('\n');
  assert.deepEqual(parse(text), {
    ngay_sinh: '1990-05-12', gioi_tinh: 'M', noi_sinh: 'Tình Mẫu',
    dia_chi: 'Số 12, Đường Minh Hoa, Xã M', cmnd: 'DEMO-123456789',
  });
  assert.deepEqual(parse('Gi6i tinh: Nu\nS6: 123456789'), { gioi_tinh: 'F', cmnd: '123456789' });
});

test('bare So never turns an address or a phone-like line into a document number', () => {
  for (const line of ['Số 12, Đường Minh Hoa', 'So 12 Duong Minh Hoa, Xa Mau', 'Số 12 34 56 78', 'So 123/45 Duong 678, To 9', 'Số: 12345']) {
    assert.deepEqual(parse(line), {}, line);
  }
  assert.deepEqual(parse('Số: 123 456 789'), { cmnd: '123 456 789' });
});

test('bounded input and values, no truncation into plausible document fields', () => {
  assert.deepEqual(parse(null), {});
  assert.deepEqual(parse({ toString() { throw Error('not a string'); } }), {});
  assert.deepEqual(parse('x'.repeat(100001)), {});
  const limits = { CMND: 64, 'Ho va ten': 150, 'Noi sinh': 250, 'Dia chi': 500 };
  for (const [label, length] of Object.entries(limits)) {
    assert.equal(Object.values(parse(`${label}: ${'A'.repeat(length)}`))[0].length, length);
    assert.deepEqual(parse(`${label}: ${'A'.repeat(length + 1)}`), {});
  }
});

test('markup, bidi/control characters and prototype-like keys cannot become fields', () => {
  for (const value of ['<script>alert(1)</script>', '<img src=x onerror=alert(1)>', 'A\u202eB', 'A\u0000B', 'A\u200bB', 'javascript:alert(1)']) {
    assert.deepEqual(parse(`CMND: ${value}\nHo va ten: ${value}`), {});
  }
  assert.deepEqual(parse('__proto__: polluted\nconstructor: bad\nAddress: <script>x</script>'), {});
  assert.equal({}.polluted, undefined);
});

function digit(value) {
  return String([...value].reduce((sum, char, index) => sum + (char === '<' ? 0 : /[0-9]/.test(char) ? Number(char) : char.charCodeAt(0) - 55) * [7, 3, 1][index % 3], 0) % 10);
}
function td3(birth = '900512', sex = 'M') {
  const a = 'P<UTO' + 'NGUYEN<<VAN<MAU'.padEnd(39, '<');
  const number = 'DEMO00099', expiry = '300101', optional = '<'.repeat(14);
  let b = number + digit(number) + 'UTO' + birth + digit(birth) + sex + expiry + digit(expiry) + optional + digit(optional);
  b += digit(b.slice(0, 10) + b.slice(13, 20) + b.slice(21, 43));
  return [a, b];
}
function td1(birth = '900512', sex = 'F') {
  const number = 'DEMO00099', expiry = '300101';
  const a = 'I<UTO' + number + digit(number) + '<'.repeat(15);
  let b = birth + digit(birth) + sex + expiry + digit(expiry) + 'UTO' + '<'.repeat(11);
  b += digit(a.slice(5, 30) + b.slice(0, 7) + b.slice(8, 15) + b.slice(18, 29));
  return [a, b, 'NGUYEN<<VAN<MAU'.padEnd(30, '<')];
}
const replaceAt = (value, index, replacement) => value.slice(0, index) + replacement + value.slice(index + 1);

test('TD3 fictional MRZ validates all field and composite checksums', () => {
  const lines = td3();
  assert.deepEqual(lines.map(line => line.length), [44, 44]);
  assert.deepEqual(parse(lines.join('\n')), { cmnd: 'DEMO00099', ten_that: 'NGUYEN VAN MAU', ngay_sinh: '1990-05-12', gioi_tinh: 'M' });
  for (const index of [9, 19, 27, 42, 43]) {
    const broken = replaceAt(lines[1], index, String((Number(lines[1][index]) + 1) % 10));
    assert.deepEqual(parse(lines[0] + '\n' + broken), {}, `check digit ${index}`);
  }
});

test('TD1 fictional MRZ validates document, birth, expiry and composite digits', () => {
  const lines = td1();
  assert.deepEqual(lines.map(line => line.length), [30, 30, 30]);
  assert.deepEqual(parse(lines.join('\n')), { cmnd: 'DEMO00099', ten_that: 'NGUYEN VAN MAU', ngay_sinh: '1990-05-12', gioi_tinh: 'F' });
  for (const [line, index] of [[0, 14], [1, 6], [1, 14], [1, 29]]) {
    const broken = [...lines];
    broken[line] = replaceAt(broken[line], index, String((Number(broken[line][index]) + 1) % 10));
    assert.deepEqual(parse(broken.join('\n')), {});
  }
});

test('MRZ bad field digit remains invalid even when composite is recalculated', () => {
  const [a, original] = td3();
  let b = replaceAt(original, 9, String((Number(original[9]) + 1) % 10));
  b = b.slice(0, 43) + digit(b.slice(0, 10) + b.slice(13, 20) + b.slice(21, 43));
  assert.deepEqual(parse(a + '\n' + b), {});
});

test('MRZ never guesses a century, unknown sex, birth place or address', () => {
  for (const make of [td1, td3]) {
    assert.deepEqual(parse(make('050512', '<').join('\n')), { cmnd: 'DEMO00099', ten_that: 'NGUYEN VAN MAU' });
    assert.deepEqual(parse(make('900231', '<').join('\n')), { cmnd: 'DEMO00099', ten_that: 'NGUYEN VAN MAU' });
    assert.deepEqual(parse(make().map(line => line + '<').join('\n')), {});
  }
  assert.deepEqual(parse('CMND: ANOTHER-ID\n' + td3().join('\n')), { ten_that: 'NGUYEN VAN MAU', ngay_sinh: '1990-05-12', gioi_tinh: 'M' });
});

function png(width = 800, height = 600) {
  const bytes = Buffer.alloc(33);
  Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]).copy(bytes);
  bytes.writeUInt32BE(13, 8); bytes.write('IHDR', 12);
  bytes.writeUInt32BE(width, 16); bytes.writeUInt32BE(height, 20);
  return new File([bytes], 'fictional-unit-header.png', { type: 'image/png' });
}
function jpeg() {
  return new File([Uint8Array.from([255, 216, 255, 192, 0, 11, 8, 2, 88, 3, 32, 1, 1, 17, 0, 255, 217])], 'fictional-unit-header.jpg', { type: 'image/jpeg' });
}
function webp(kind = 'VP8X', animated = false) {
  const bytes = Buffer.alloc(30);
  bytes.write('RIFF'); bytes.writeUInt32LE(22, 4); bytes.write('WEBP', 8); bytes.write(kind, 12); bytes.writeUInt32LE(10, 16);
  if (kind === 'VP8X') { bytes[20] = animated ? 2 : 0; bytes.writeUIntLE(799, 24, 3); bytes.writeUIntLE(599, 27, 3); }
  else if (kind === 'VP8 ') { bytes.set([0x9d, 1, 0x2a], 23); bytes.writeUInt16LE(800, 26); bytes.writeUInt16LE(600, 28); }
  else { bytes[20] = 0x2f; bytes.writeUInt32LE(799 | (599 << 14), 21); }
  return new File([bytes], 'fictional-unit-header.webp', { type: 'image/webp' });
}

// VM mocks exercise our lifecycle and boundary code, not recognition accuracy.
// Real OCR is always the locally installed Tesseract engine in the application.
function browser(options = {}) {
  const state = { closed: 0, terminated: 0, decoded: 0, canvases: [], workers: [], draws: [], timers: 0 };
  class Worker {
    constructor(url, settings) { state.workers.push({ url, settings }); }
    terminate() { state.terminated++; }
    postMessage(message, transfer) {
      state.message = message; state.transfer = transfer;
      options.onStart?.();
      if (options.hang) return;
      queueMicrotask(() => {
        this.onmessage?.({ data: { type: 'progress', status: 'recognizing text', progress: 0.5 } });
        this.onmessage?.({ data: options.error ? { type: 'error' } : { type: 'result', text: options.text ?? golden, confidence: 92 } });
      });
    }
  }
  const sandbox = {
    File, Blob, URL, ArrayBuffer, Uint8Array, DataView, AbortController, Worker,
    setTimeout(callback, ms) {
      state.timers++;
      return setTimeout(callback, options.fastTimeout ? 10 : ms);
    },
    clearTimeout(id) { state.timers--; clearTimeout(id); },
    createImageBitmap: options.bitmap || (async () => {
      state.decoded++;
      return { width: options.width || 800, height: options.height || 600, close() { state.closed++; } };
    }),
    document: { createElement(tag) {
      assert.equal(tag, 'canvas');
      const canvas = {
        width: 0, height: 0,
        getContext() { return { fillRect() {}, drawImage(...args) { state.draws.push(args); } }; },
        toBlob(callback) { state.canvasSize = [canvas.width, canvas.height]; callback(new Blob(['synthetic-unit-canvas'])); },
      };
      state.canvases.push(canvas);
      return canvas;
    } },
  };
  vm.runInNewContext(source, sandbox, { filename: 'ocr.js' });
  return { api: sandbox.DocumentOCR, state, sandbox };
}

test('recognize default language, draft output, progress and resource cleanup', async () => {
  const { api, state } = browser();
  const progress = [];
  const result = await api.recognize(png(), undefined, event => progress.push(plain(event)));
  assert.deepEqual(plain(result), { text: golden, fields: expected, confidence: 92 });
  assert.equal(state.message.language, 'eng');
  assert.deepEqual(state.workers.map(item => item.url), ['/ocr.js']);
  assert.equal(state.transfer[0], state.message.image);
  assert.equal(state.closed, 1); assert.equal(state.terminated, 1); assert.equal(state.timers, 0);
  assert.equal(state.canvases[0].width, 0); assert.equal(state.canvases[0].height, 0);
  assert.ok(progress.some(event => event.status === 'recognizing text' && event.progress === 0.5));
});

test('raw text is returned even when no draft field is recognized', async () => {
  const { api } = browser({ text: 'unlabeled fictional OCR text' });
  const result = await api.recognize(png());
  assert.equal(result.text, 'unlabeled fictional OCR text');
  assert.deepEqual(plain(result.fields), {});
});

test('only three exact language choices and actual image Files are accepted', async () => {
  const { api, state } = browser();
  for (const language of ['eng+vie', 'vie', 'khm', '../eng', 'https://invalid.test/eng', '', null, {}, ['eng']]) {
    await assert.rejects(api.recognize(png(), language), { name: 'TypeError' });
  }
  for (const file of ['https://invalid.test/image.png', new Blob(['x'], { type: 'image/png' }), {}, new File(['x'], 'x.svg', { type: 'image/svg+xml' })]) {
    await assert.rejects(api.recognize(file), { name: 'TypeError' });
  }
  await assert.rejects(api.recognize(new File([], 'empty.png', { type: 'image/png' })), { name: 'RangeError' });
  await assert.rejects(api.recognize(new File([new Uint8Array(10 * 1024 * 1024 + 1)], 'large.png', { type: 'image/png' })), { name: 'RangeError' });
  await assert.rejects(api.recognize(png(), 'eng', null, {}), { name: 'TypeError' });
  assert.equal(state.workers.length, 0);
  for (const language of ['eng', 'vie+eng', 'khm+eng']) await api.recognize(png(), language);
});

test('container signatures and dimension limits are checked before image decoding', async () => {
  const { api, state } = browser();
  for (const file of [new File(['not an image'], 'fake.png', { type: 'image/png' }), png(12001, 1), png(6000, 5000), png(0, 600), webp('VP8X', true)]) {
    await assert.rejects(api.recognize(file));
  }
  assert.equal(state.decoded, 0); assert.equal(state.workers.length, 0);
  for (const file of [png(), jpeg(), webp(), webp('VP8 '), webp('VP8L')]) await api.recognize(file);
  assert.equal(state.decoded, 5);
});

test('verified image dimensions are downscaled to a longest side of 1800', async () => {
  const { api, state } = browser({ width: 4400, height: 2200 });
  await api.recognize(png(4400, 2200));
  assert.deepEqual(state.canvasSize, [1800, 900]);
  const mismatch = browser({ width: 799, height: 600 });
  await assert.rejects(mismatch.api.recognize(png()));
  assert.equal(mismatch.state.closed, 1); assert.equal(mismatch.state.workers.length, 0);
  const rotated = browser({ width: 600, height: 800 });
  await rotated.api.recognize(png());
});

test('already-aborted, initializing and active OCR all cancel cleanly', async () => {
  const controller = new AbortController();
  controller.abort();
  const first = browser();
  await assert.rejects(first.api.recognize(png(), 'eng', null, controller.signal), { name: 'AbortError' });
  assert.equal(first.state.decoded, 0);
  const ongoing = new AbortController();
  const second = browser({ hang: true, onStart: () => ongoing.abort() });
  await assert.rejects(second.api.recognize(png(), 'eng', null, ongoing.signal), { name: 'AbortError' });
  assert.equal(second.state.terminated, 1); assert.equal(second.state.closed, 1); assert.equal(second.state.timers, 0);
});

test('late bitmap completion after abort closes the bitmap', async () => {
  const controller = new AbortController();
  let resolveBitmap, closed = 0;
  const { api } = browser({ bitmap: () => new Promise(resolve => { resolveBitmap = resolve; controller.abort(); }) });
  await assert.rejects(api.recognize(png(), 'eng', null, controller.signal), { name: 'AbortError' });
  resolveBitmap({ width: 800, height: 600, close() { closed++; } });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(closed, 1);
});

test('timeout and engine error release workers; callback exceptions are isolated', async () => {
  const timeout = browser({ hang: true, fastTimeout: true });
  await assert.rejects(timeout.api.recognize(png()), { name: 'TimeoutError' });
  assert.equal(timeout.state.terminated, 1); assert.equal(timeout.state.timers, 0);
  const engine = browser({ error: true });
  await assert.rejects(engine.api.recognize(png()));
  assert.equal(engine.state.terminated, 1);
  const callbacks = browser();
  await callbacks.api.recognize(png(), 'eng', () => { throw new Error('UI exception'); });
  assert.equal(callbacks.state.terminated, 1);
});

test('Image fallback revokes temporary object URLs', async () => {
  const { api, sandbox } = browser();
  sandbox.createImageBitmap = undefined;
  let revoked = 0;
  sandbox.URL = { createObjectURL() { return 'blob:unit-test'; }, revokeObjectURL(url) { assert.equal(url, 'blob:unit-test'); revoked++; } };
  sandbox.Image = class {
    naturalWidth = 800; naturalHeight = 600;
    set src(value) { if (value) queueMicrotask(() => this.onload?.()); }
  };
  await api.recognize(png());
  assert.equal(revoked, 1);
});

test('controller lazily imports same-origin engine and explicitly disables remote/cache/blob defaults', async () => {
  const calls = [], messages = [];
  let terminated = 0;
  const sandbox = {
    ArrayBuffer, Uint8Array, URL,
    location: { origin: 'http://127.0.0.1:8787' },
    importScripts(url) { calls.push(url); },
    postMessage(message) { messages.push(message); },
    Tesseract: { async createWorker(language, oem, options) {
      calls.push({ language, oem, options });
      options.logger({ status: 'loading language traineddata', progress: 0.2 });
      return { async recognize(image, options, output) {
        assert.ok(image instanceof Uint8Array); assert.deepEqual(plain(output), { text: true });
        return { data: { text: golden, confidence: 90 } };
      }, async terminate() { terminated++; } };
    } },
  };
  vm.runInNewContext(source, sandbox);
  assert.equal(calls.length, 0);
  await sandbox.onmessage({ data: { image: new ArrayBuffer(10), language: 'vie+eng' } });
  assert.equal(calls[0], 'http://127.0.0.1:8787/assets/ocr/tesseract.min.js');
  const { language, oem, options } = calls[1];
  assert.equal(language, 'vie+eng'); assert.equal(oem, 1);
  assert.equal(options.workerBlobURL, false); assert.equal(options.cacheMethod, 'none');
  assert.equal(options.legacyCore, false); assert.equal(options.legacyLang, false);
  for (const field of ['corePath', 'workerPath', 'langPath']) assert.ok(options[field].startsWith('http://127.0.0.1:8787/assets/ocr/'));
  assert.ok(messages.some(message => message.type === 'result' && message.text === golden));
  assert.equal(terminated, 1);
  assert.doesNotMatch(source, /\b(?:localStorage|sessionStorage|indexedDB|fetch|XMLHttpRequest|sendBeacon)\s*[.(]/);
  assert.doesNotMatch(source, /https?:\/\/|cdn\./);
});

test('locked packages and generated assets include only required runtime variants and licenses', () => {
  const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
  const lock = JSON.parse(fs.readFileSync(path.join(root, 'package-lock.json'), 'utf8'));
  for (const [name, version] of Object.entries(pkg.dependencies)) {
    assert.match(version, /^\d+\.\d+\.\d+$/);
    assert.equal(lock.packages[`node_modules/${name}`].version, version);
    assert.ok(lock.packages[`node_modules/${name}`].integrity);
  }
  const assets = path.join(root, 'static', 'assets', 'ocr');
  for (const variant of ['lstm', 'simd-lstm', 'relaxedsimd-lstm']) {
    assert.deepEqual(fs.readFileSync(path.join(assets, `tesseract-core-${variant}.wasm.js`)), fs.readFileSync(path.join(root, 'node_modules', 'tesseract.js-core', `tesseract-core-${variant}.js`)));
    assert.equal(fs.readFileSync(path.join(assets, `tesseract-core-${variant}.wasm`)).subarray(0, 4).toString('hex'), '0061736d');
  }
  for (const lang of ['eng', 'vie', 'khm']) {
    assert.deepEqual(fs.readFileSync(path.join(assets, `${lang}.traineddata.gz`)), fs.readFileSync(path.join(root, 'node_modules', '@tesseract.js-data', lang, '4.0.0_best_int', `${lang}.traineddata.gz`)));
    assert.equal(JSON.parse(fs.readFileSync(path.join(assets, `${lang}.LICENSE.json`))).license, 'MIT');
  }
  assert.equal(fs.readdirSync(assets).length, 18);
});

test('HTTP MIME, strict OCR allowlist and CSP work without reading application data', () => {
  const script = `
import http.client, pathlib, sys, threading
sys.path.insert(0, sys.argv[1])
from app import DemoServer, OCR_FILES, CSP
class NoDataStore:
    def __getattr__(self, name):
        def unused(*args):
            raise AssertionError('Static requests must not access application data')
        return unused
server = DemoServer(0, NoDataStore(), pathlib.Path(sys.argv[1]) / 'static')
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
def request(path):
    connection = http.client.HTTPConnection('127.0.0.1', server.server_port)
    connection.request('HEAD', path)
    response = connection.getresponse()
    result = response.status, dict(response.getheaders())
    response.read()
    connection.close()
    return result
try:
    for name, mime in OCR_FILES.items():
        status, headers = request('/' + name)
        assert status == 200, (name, status)
        assert headers['Content-Type'] == mime
        assert 'Content-Encoding' not in headers
        assert headers['Content-Security-Policy'] == CSP
    assert request('/ocr.js')[0] == 200
    for path in ['/assets/other.js', '/assets/ocr/other.js', '/assets/ocr/other.wasm', '/assets/ocr/other.gz', '/assets/ocr/eng.LICENSE.json', '/assets/ocr/tesseract.min.js.map', '/assets/ocr/unlisted.png', '/node_modules/tesseract.js/dist/tesseract.min.js', '/assets/ocr/../tesseract.min.js', '/assets/ocr/%2e%2e/tesseract.min.js']:
        assert request(path)[0] == 404, path
    assert "script-src 'self' 'wasm-unsafe-eval'" in CSP
    assert "worker-src 'self'" in CSP
    assert "img-src 'self' blob:" in CSP
    assert "'unsafe-eval'" not in CSP and 'https:' not in CSP
finally:
    server.shutdown()
    server.server_close()
    thread.join()
`;
  const result = spawnSync('python3', ['-B', '-c', script, root], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr || result.stdout);
});
