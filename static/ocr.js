/* Local-only OCR. Draft fields are never saved or applied by this module. */
(function (scope) {
  'use strict';

  const LANGUAGES = new Set(['eng', 'vie+eng', 'khm+eng']);
  const ASSETS = '/assets/ocr/';
  const MAX_FILE = 10 * 1024 * 1024;
  const MAX_DIMENSION = 12000;
  const MAX_PIXELS = 24000000;
  const TARGET_DIMENSION = 1800;
  const TIMEOUT = 120000;
  const LIMITS = { cmnd: 64, ten_that: 150, ngay_sinh: 10, gioi_tinh: 1, noi_sinh: 250, dia_chi: 500 };
  const ALIASES = {
    cmnd: ['so dinh danh ca nhan', 'so can cuoc cong dan', 'so chung minh nhan dan', 'so cmnd', 'so cccd', 'cmnd', 'cccd', 'so ho chieu', 'identity card number', 'national id number', 'document number', 'passport number', 'passport no.', 'passport no', 'id number', 'id no.', 'id no', 'so', 'sb'],
    ten_that: ['ho va ten', 'ho ten', 'full name', 'name'],
    ngay_sinh: ['ngay thang nam sinh', 'ngay sinh', 'date of birth', 'birth date', 'dob'],
    gioi_tinh: ['gioi tinh', 'gender', 'sex'],
    noi_sinh: ['noi sinh', 'place of birth', 'birthplace'],
    dia_chi: ['dia chi thuong tru', 'noi thuong tru', 'noi cu tru', 'dia chi', 'place of residence', 'permanent address', 'residential address', 'address'],
  };
  const BARE_ID = new Set(['so', 'sb']);
  const fold = value => value.normalize('NFD').replace(/\p{M}/gu, '').replace(/[đĐ]/g, 'd').toLowerCase();
  const CONFUSABLE = { 0: 'o', 1: 'i', 2: 'z', 4: 'a', 5: 's', 6: 'o', 8: 'b', 9: 'g', '|': 'l' };
  const escapeRE = value => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const LABELS = Object.entries(ALIASES).map(([field, aliases]) => {
    const alternatives = aliases.slice().sort((a, b) => b.length - a.length).map(escapeRE).join('|');
    return [field, new RegExp(`^(?:${alternatives})(?:\\s*/\\s*(?:${alternatives}))?(?:\\s*[:：]\\s*|\\s+|$)`, 'u')];
  });
  // Then a phone photo: strip accents, fold look-alike digits back to letters
  // ("Gi6i tinh", "S6") and look for a label anywhere in the line, because the
  // engine often prefixes junk such as "| " or "mm. ".
  function foldedChars(line) {
    return Array.from(line, ch => {
      const base = fold(ch);
      return CONFUSABLE[base] ?? base;
    });
  }

  function label(line, loose) {
    if (!loose) {
      for (const [field, pattern] of LABELS) {
        const match = pattern.exec(fold(line));
        if (match) {
          const head = fold(match[0]).replace(/[\s:：/]+$/, '');
          return { field, head, value: line.slice(match[0].length).trim() };
        }
      }
      return null;
    }
    const text = foldedChars(line).join('');
    let best = null;
    for (const [field, aliases] of Object.entries(ALIASES)) {
      for (const alias of aliases) {
        for (let index = text.indexOf(alias); index !== -1; index = text.indexOf(alias, index + 1)) {
          const before = index ? text[index - 1] : '';
          const after = text[index + alias.length] || '';
          if (/[a-z]/.test(before) || /[a-z]/.test(after)) continue;
          if (!best || index < best.index || (index === best.index && alias.length > best.length)) {
            best = { field, head: alias, index, length: alias.length };
          }
        }
      }
    }
    if (!best) return null;
    const value = Array.from(line).slice(best.index + best.length).join('').replace(/^[\s:：;,”’"'’\-–—.]+/, '').trim();
    return { field: best.field, head: best.head, value };
  }

  // Bare "Số" only counts as a document number when the value is mostly digits,
  // so an address line such as "Số 12, Đường…" cannot become a CMND number.
  const usable = item => {
    if (!BARE_ID.has(item.head)) return true;
    const value = item.value;
    return (value.match(/\d/g) || []).length >= 6 && /^[A-Z0-9-]+(?: [A-Z0-9-]+){0,2}$/i.test(value);
  };

  function dateISO(year, month, day) {
    if (![year, month, day].every(Number.isInteger) || year < 1900 || month < 1 || month > 12 || day < 1 || day > 31) return '';
    const date = new Date(Date.UTC(year, month - 1, day));
    const now = new Date();
    const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
    if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day || date.getTime() > today) return '';
    return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
  }

  function birthDate(value, vietnamese) {
    let match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    if (match) return dateISO(+match[1], +match[2], +match[3]);
    match = /^(\d{1,2})([/.\-])(\d{1,2})\2(\d{4})$/.exec(value);
    if (match) {
      const a = +match[1], b = +match[3], year = +match[4];
      if (vietnamese || a > 12 || a === b) return dateISO(year, b, a);
      if (b > 12) return dateISO(year, a, b);
      // English numeric dates with two possible orders are deliberately omitted.
      return '';
    }
    const months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];
    match = /^(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{4})$/i.exec(value);
    if (match) return dateISO(+match[3], months.indexOf(match[2].slice(0, 3).toLowerCase()) + 1, +match[1]);
    return '';
  }

  function clean(field, value) {
    if (typeof value !== 'string' || /[\p{Cc}\p{Cf}]/u.test(value)) return '';
    value = value.normalize('NFC').trim().replace(/\s+/g, ' ');
    if (!value || value.length > LIMITS[field]) return '';
    if (field === 'cmnd') return /^[A-Z0-9][A-Z0-9 -]{2,63}$/i.test(value) ? value : '';
    if (field === 'ten_that') return /^[\p{L}\p{M}][\p{L}\p{M} .'’\-]*$/u.test(value) ? value : '';
    if (field === 'noi_sinh' || field === 'dia_chi') {
      return /[\p{L}\p{N}]/u.test(value) && /^[\p{L}\p{M}\p{N} .,;'’()/#:\-]+$/u.test(value) ? value : '';
    }
    return value;
  }

  function checkDigit(value, digit, fillerAllowed = false) {
    if (!/^[A-Z0-9<]+$/.test(value) || !/^[0-9]$/.test(digit) && !(fillerAllowed && digit === '<')) return false;
    let sum = 0;
    for (let i = 0; i < value.length; i++) {
      const code = value.charCodeAt(i);
      const number = code === 60 ? 0 : code >= 65 ? code - 55 : code - 48;
      sum += number * [7, 3, 1][i % 3];
    }
    return sum % 10 === (digit === '<' ? 0 : Number(digit));
  }

  function mrzBirth(value) {
    if (!/^\d{6}$/.test(value)) return '';
    // ICAO gives only YY. Do not guess when both 19YY and 20YY are possible.
    const candidates = [1900, 2000].map(century => dateISO(century + Number(value.slice(0, 2)), Number(value.slice(2, 4)), Number(value.slice(4, 6)))).filter(Boolean);
    return candidates.length === 1 ? candidates[0] : '';
  }

  function mrzFields(number, birth, sex, names) {
    const fields = {};
    if (/^[A-Z0-9]+<*$/.test(number)) fields.cmnd = number.replace(/<+$/, '');
    const nameParts = /^([A-Z]+(?:<[A-Z]+)*)<<([A-Z]+(?:<[A-Z]+)*)<*$/.exec(names);
    if (nameParts) fields.ten_that = `${nameParts[1]} ${nameParts[2]}`.replace(/</g, ' ');
    const date = mrzBirth(birth);
    if (date) fields.ngay_sinh = date;
    if (sex === 'M' || sex === 'F') fields.gioi_tinh = sex;
    return fields;
  }

  function parseMRZ(lines, add) {
    for (let i = 0; i < lines.length - 1; i++) {
      const a = lines[i], b = lines[i + 1], c = lines[i + 2] || '';
      let fields;
      if (/^P[A-Z<][A-Z<]{3}[A-Z<]{39}$/.test(a) && /^[A-Z0-9<]{44}$/.test(b)) {
        if (!/^[A-Z<]{3}$/.test(b.slice(10, 13)) || !/^[MF<]$/.test(b[20]) || !/^\d{6}$/.test(b.slice(21, 27))) continue;
        if (!checkDigit(b.slice(0, 9), b[9]) || !checkDigit(b.slice(13, 19), b[19]) ||
            !checkDigit(b.slice(21, 27), b[27]) || !checkDigit(b.slice(28, 42), b[42], true) ||
            !checkDigit(b.slice(0, 10) + b.slice(13, 20) + b.slice(21, 43), b[43])) continue;
        fields = mrzFields(b.slice(0, 9), b.slice(13, 19), b[20], a.slice(5));
      } else if (/^[IAC][A-Z<][A-Z<]{3}[A-Z0-9<]{25}$/.test(a) && /^[A-Z0-9<]{30}$/.test(b) && /^[A-Z<]{30}$/.test(c)) {
        if (!/^[MF<]$/.test(b[7]) || !/^[A-Z<]{3}$/.test(b.slice(15, 18)) || !/^\d{6}$/.test(b.slice(8, 14))) continue;
        if (!checkDigit(a.slice(5, 14), a[14]) || !checkDigit(b.slice(0, 6), b[6]) ||
            !checkDigit(b.slice(8, 14), b[14]) ||
            !checkDigit(a.slice(5, 30) + b.slice(0, 7) + b.slice(8, 15) + b.slice(18, 29), b[29])) continue;
        fields = mrzFields(a.slice(5, 14), b.slice(0, 6), b[7], c);
      }
      if (fields) for (const [field, value] of Object.entries(fields)) add(field, value);
    }
  }

  function parse(text) {
    if (typeof text !== 'string' || text.length > 100000) return {};
    const fields = {};
    const conflicts = new Set();
    const add = (field, value) => {
      value = clean(field, value);
      if (!value || conflicts.has(field)) return;
      if (fields[field] && fields[field] !== value) {
        delete fields[field];
        conflicts.add(field);
      } else fields[field] = value;
    };
    const lines = text.normalize('NFC').split(/\r\n?|\n|\u2028|\u2029/).map(line => line.trim());
    for (let i = 0; i < lines.length; i++) {
      let item = label(lines[i], false);
      if (!item || !usable(item)) item = label(lines[i], true);
      if (!item || !usable(item)) continue;
      let value = item.value;
      // A value may occupy the immediately following line, but never consume
      // another label, arbitrary later paragraphs, or an MRZ line as an address.
      if (!value && lines[i + 1] && !label(lines[i + 1], false) && !label(lines[i + 1], true) && !/[<:：]/.test(lines[i + 1])) value = lines[i + 1];
      if (item.field === 'ngay_sinh') value = birthDate(value, fold(item.head).startsWith('ngay'));
      if (item.field === 'gioi_tinh') value = ({ nam: 'M', male: 'M', m: 'M', nu: 'F', female: 'F', f: 'F' })[fold(value)] || '';
      add(item.field, value);
    }
    parseMRZ(lines, add);
    return fields;
  }

  function failure(message, name = 'Error') {
    const error = new Error(message);
    error.name = name;
    return error;
  }

  function abortReason(signal) {
    return signal.reason && signal.reason.name === 'TimeoutError'
      ? signal.reason : failure('Đã hủy nhận dạng.', 'AbortError');
  }

  function active(signal) {
    if (signal.aborted) throw abortReason(signal);
  }

  function abortable(promise, signal, releaseLate) {
    return new Promise((resolve, reject) => {
      let ended = false;
      const abort = () => {
        if (ended) return;
        ended = true;
        signal.removeEventListener('abort', abort);
        reject(abortReason(signal));
      };
      signal.addEventListener('abort', abort, { once: true });
      if (signal.aborted) abort();
      Promise.resolve(promise).then(value => {
        signal.removeEventListener('abort', abort);
        if (ended) { if (releaseLate) releaseLate(value); return; }
        ended = true;
        resolve(value);
      }, error => {
        signal.removeEventListener('abort', abort);
        if (!ended) { ended = true; reject(error); }
      });
    });
  }

  function dimensions(width, height) {
    if (!Number.isInteger(width) || !Number.isInteger(height) || width < 1 || height < 1 ||
        width > MAX_DIMENSION || height > MAX_DIMENSION || width * height > MAX_PIXELS) {
      throw failure('Ảnh vượt giới hạn 12.000 px mỗi chiều hoặc 24 triệu điểm ảnh.', 'RangeError');
    }
    return { width, height };
  }

  // Read container dimensions before allocating a decoded bitmap, then verify
  // the browser-decoded dimensions too. No SVG, URLs, PDF, or unbounded input.
  function headerDimensions(bytes, mime) {
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const ascii = (start, count) => String.fromCharCode(...bytes.subarray(start, start + count));
    if (mime === 'image/png' && bytes.length >= 33 &&
        bytes[0] === 137 && ascii(1, 7) === 'PNG\r\n\x1a\n' && view.getUint32(8) === 13 && ascii(12, 4) === 'IHDR') {
      return dimensions(view.getUint32(16), view.getUint32(20));
    }
    if (mime === 'image/jpeg' && bytes.length >= 4 && bytes[0] === 255 && bytes[1] === 216) {
      let offset = 2;
      while (offset + 3 < bytes.length) {
        if (bytes[offset++] !== 255) break;
        while (bytes[offset] === 255) offset++;
        const marker = bytes[offset++];
        if (marker === 0xda || marker === 0xd9 || marker === undefined) break;
        if (marker === 0x01 || marker >= 0xd0 && marker <= 0xd7) continue;
        if (offset + 2 > bytes.length) break;
        const length = view.getUint16(offset);
        if (length < 2 || offset + length > bytes.length) break;
        if ([0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf].includes(marker)) {
          if (length < 8) break;
          return dimensions(view.getUint16(offset + 5), view.getUint16(offset + 3));
        }
        offset += length;
      }
    }
    if (mime === 'image/webp' && bytes.length >= 30 && ascii(0, 4) === 'RIFF' && ascii(8, 4) === 'WEBP' && view.getUint32(4, true) + 8 === bytes.length) {
      const kind = ascii(12, 4);
      const size = view.getUint32(16, true);
      if (size + 20 > bytes.length) throw failure('Dữ liệu WebP không hợp lệ.');
      if (kind === 'VP8X' && size >= 10) {
        if (bytes[20] & 2) throw failure('Vui lòng chọn ảnh tĩnh, không dùng WebP động.');
        const u24 = n => bytes[n] + bytes[n + 1] * 256 + bytes[n + 2] * 65536;
        return dimensions(u24(24) + 1, u24(27) + 1);
      }
      if (kind === 'VP8 ' && size >= 10 && bytes[23] === 0x9d && bytes[24] === 0x01 && bytes[25] === 0x2a) {
        return dimensions(view.getUint16(26, true) & 0x3fff, view.getUint16(28, true) & 0x3fff);
      }
      if (kind === 'VP8L' && size >= 5 && bytes[20] === 0x2f) {
        const bits = view.getUint32(21, true);
        return dimensions((bits & 0x3fff) + 1, ((bits >>> 14) & 0x3fff) + 1);
      }
    }
    throw failure('Nội dung ảnh không khớp PNG/JPEG/WebP hợp lệ.', 'TypeError');
  }

  async function decode(file, signal) {
    active(signal);
    if (typeof scope.createImageBitmap === 'function') {
      const bitmap = await abortable(scope.createImageBitmap(file), signal, late => late.close());
      return { image: bitmap, width: bitmap.width, height: bitmap.height, release: () => bitmap.close() };
    }
    const url = scope.URL.createObjectURL(file);
    const image = new scope.Image();
    let release;
    const promise = new Promise((resolve, reject) => {
      release = () => {
        image.onload = null;
        image.onerror = null;
        image.src = '';
        scope.URL.revokeObjectURL(url);
      };
      image.onload = () => resolve({ image, width: image.naturalWidth, height: image.naturalHeight, release });
      image.onerror = () => reject(failure('Không giải mã được ảnh.'));
      image.src = url;
    });
    try { return await abortable(promise, signal, () => release()); }
    catch (error) { release(); throw error; }
  }

  async function prepareImage(file, signal) {
    active(signal);
    const bytes = new Uint8Array(await abortable(file.arrayBuffer(), signal));
    const header = headerDimensions(bytes, file.type);
    active(signal);
    const decoded = await decode(file, signal);
    let canvas;
    try {
      active(signal);
      dimensions(decoded.width, decoded.height);
      // EXIF orientation may swap axes, but must not change the pixel count.
      if (!(decoded.width === header.width && decoded.height === header.height ||
            decoded.width === header.height && decoded.height === header.width)) throw failure('Kích thước ảnh giải mã không khớp.');
      const scale = Math.min(1, TARGET_DIMENSION / Math.max(decoded.width, decoded.height));
      canvas = scope.document.createElement('canvas');
      canvas.width = Math.max(1, Math.round(decoded.width * scale));
      canvas.height = Math.max(1, Math.round(decoded.height * scale));
      const context = canvas.getContext('2d', { alpha: false });
      if (!context) throw failure('Trình duyệt không hỗ trợ xử lý ảnh.');
      context.fillStyle = '#fff';
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.drawImage(decoded.image, 0, 0, canvas.width, canvas.height);
      const blob = await abortable(new Promise((resolve, reject) => {
        canvas.toBlob(value => value ? resolve(value) : reject(failure('Không chuẩn bị được ảnh.')), 'image/png');
      }), signal);
      return await abortable(blob.arrayBuffer(), signal);
    } finally {
      decoded.release();
      if (canvas) { canvas.width = 0; canvas.height = 0; }
    }
  }

  function notify(callback, status, progress) {
    if (typeof callback !== 'function') return;
    try { callback({ status, progress: Math.max(0, Math.min(1, Number(progress) || 0)) }); }
    catch (_) { /* A UI callback must not leak an OCR worker. */ }
  }

  function processImage(image, language, onProgress, signal) {
    active(signal);
    return new Promise((resolve, reject) => {
      // A same-origin controller gives us a Worker handle BEFORE asynchronous
      // Tesseract initialization. Termination also terminates its child worker,
      // including stalled loader/core/language downloads (HTML worker lifecycle).
      const worker = new scope.Worker('/ocr.js', { name: 'document-ocr-controller' });
      let ended = false;
      const finish = (error, data) => {
        if (ended) return;
        ended = true;
        signal.removeEventListener('abort', abort);
        worker.onmessage = null;
        worker.onerror = null;
        worker.onmessageerror = null;
        worker.terminate();
        if (error) reject(error); else resolve(data);
      };
      const abort = () => finish(abortReason(signal));
      signal.addEventListener('abort', abort, { once: true });
      worker.onerror = event => {
        event.preventDefault();
        finish(failure('Không khởi chạy được OCR cục bộ. Hãy chạy npm run setup:ocr và thử lại.'));
      };
      worker.onmessageerror = () => finish(failure('Không nhận được kết quả OCR.'));
      worker.onmessage = ({ data }) => {
        if (!data || ended) return;
        if (data.type === 'progress') notify(onProgress, String(data.status).slice(0, 100), data.progress);
        else if (data.type === 'result' && typeof data.text === 'string') finish(null, data);
        else if (data.type === 'error') finish(failure('OCR cục bộ thất bại. Kiểm tra bộ dữ liệu OCR và thử ảnh rõ hơn.'));
      };
      if (signal.aborted) abort();
      else {
        try { worker.postMessage({ image, language }, [image]); }
        catch (error) { finish(error); }
      }
    });
  }

  async function recognize(file, language = 'eng', onProgress, signal) {
    if (!LANGUAGES.has(language)) throw failure('Ngôn ngữ OCR phải là eng, vie+eng hoặc khm+eng.', 'TypeError');
    if (typeof scope.File !== 'function' || !(file instanceof scope.File) ||
        !['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) throw failure('Chỉ nhận tệp PNG, JPEG hoặc WebP.', 'TypeError');
    if (file.size < 1 || file.size > MAX_FILE) throw failure('Ảnh phải có dung lượng từ 1 byte đến 10 MB.', 'RangeError');
    if (signal != null && (typeof signal.addEventListener !== 'function' || typeof signal.removeEventListener !== 'function' || typeof signal.aborted !== 'boolean')) {
      throw failure('AbortSignal không hợp lệ.', 'TypeError');
    }
    const controller = new AbortController();
    const abort = () => controller.abort(failure('Đã hủy nhận dạng.', 'AbortError'));
    if (signal) {
      signal.addEventListener('abort', abort, { once: true });
      if (signal.aborted) abort();
    }
    const timer = setTimeout(() => controller.abort(failure('OCR quá thời gian 60 giây. Hãy thử ảnh nhỏ, rõ hơn.', 'TimeoutError')), TIMEOUT);
    try {
      active(controller.signal);
      notify(onProgress, 'preparing image', 0);
      const image = await prepareImage(file, controller.signal);
      const result = await processImage(image, language, onProgress, controller.signal);
      active(controller.signal);
      const confidence = Number.isFinite(result.confidence) ? Math.max(0, Math.min(100, result.confidence)) : 0;
      return { text: result.text, fields: parse(result.text), confidence };
    } finally {
      clearTimeout(timer);
      if (signal) signal.removeEventListener('abort', abort);
    }
  }

  // This same file doubles as the disposable, same-origin OCR controller.
  // No personal pixels/text leave workers except the explicit result message;
  // no storage API, telemetry, remote URL, or application save API is used.
  if (typeof scope.importScripts === 'function' && typeof scope.document === 'undefined') {
    let started = false;
    scope.onmessage = async ({ data }) => {
      if (started) return;
      started = true;
      let worker;
      try {
        if (!data || !LANGUAGES.has(data.language) || !(data.image instanceof ArrayBuffer) || data.image.byteLength > 25 * 1024 * 1024) throw failure('Invalid OCR request');
        const base = new URL(ASSETS, scope.location.origin).href;
        scope.importScripts(`${base}tesseract.min.js`);
        worker = await scope.Tesseract.createWorker(data.language, 1, {
          workerPath: `${base}worker.min.js`,
          corePath: base,
          langPath: base,
          workerBlobURL: false,
          cacheMethod: 'none',
          gzip: true,
          legacyCore: false,
          legacyLang: false,
          logger: event => scope.postMessage({ type: 'progress', status: event.status, progress: event.progress }),
          errorHandler: () => scope.postMessage({ type: 'error' }),
        });
        const result = await worker.recognize(new Uint8Array(data.image), {}, { text: true });
        scope.postMessage({ type: 'result', text: result.data.text, confidence: result.data.confidence });
      } catch (_) {
        // Do not expose engine diagnostics that might contain document text.
        scope.postMessage({ type: 'error' });
      } finally {
        if (worker) await worker.terminate();
      }
    };
  } else {
    const api = Object.freeze({ recognize, parse });
    if (typeof module === 'object' && module.exports) module.exports = api;
    else scope.DocumentOCR = api;
  }
})(typeof self !== 'undefined' ? self : globalThis);
