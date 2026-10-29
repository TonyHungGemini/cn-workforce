'use strict';

/*
 * QR byte-mode encoder (ECC M, versions 1-10) written for this project so the
 * app never loads a QR library from a CDN. Payloads here are short printable
 * IDs (C2-0001, KH-291026-0007), so one ECC level and ten versions are enough.
 */
const QRCode = (() => {
  const SPEC = {
    1: {blocks: [[1, 16, 10]], align: [], remainder: 0},
    2: {blocks: [[1, 28, 16]], align: [6, 18], remainder: 7},
    3: {blocks: [[1, 44, 26]], align: [6, 22], remainder: 7},
    4: {blocks: [[2, 32, 18]], align: [6, 26], remainder: 7},
    5: {blocks: [[2, 43, 24]], align: [6, 30], remainder: 7},
    6: {blocks: [[4, 27, 16]], align: [6, 34], remainder: 7},
    7: {blocks: [[4, 31, 18]], align: [6, 22, 38], remainder: 0},
    8: {blocks: [[2, 38, 22], [2, 39, 22]], align: [6, 24, 42], remainder: 0},
    9: {blocks: [[3, 36, 22], [2, 37, 22]], align: [6, 26, 46], remainder: 0},
    10: {blocks: [[4, 43, 26], [1, 44, 26]], align: [6, 28, 50], remainder: 0},
  };
  const MAX_VERSION = 10;
  const ECC_FORMAT_BITS = 0x00; // ECC level M in the 15-bit format field.
  const PAD = [0xEC, 0x11];

  const dataCapacity = version => SPEC[version].blocks.reduce((sum, [count, data]) => sum + count * data, 0);

  function utf8Bytes(text) {
    const value = String(text ?? '');
    if (typeof TextEncoder === 'function') return Array.from(new TextEncoder().encode(value));
    return Array.from(unescape(encodeURIComponent(value)), char => char.charCodeAt(0));
  }

  function bitBuffer() {
    const bits = [];
    return {
      bits,
      put(value, length) { for (let i = length - 1; i >= 0; i -= 1) bits.push((value >>> i) & 1); },
    };
  }

  function chooseVersion(byteLength) {
    for (let version = 1; version <= MAX_VERSION; version += 1) {
      const countBits = version < 10 ? 8 : 16;
      if (4 + countBits + byteLength * 8 <= dataCapacity(version) * 8) return version;
    }
    throw new Error('Nội dung quá dài để tạo mã QR trong bản này (tối đa 213 byte).');
  }

  function dataCodewords(text, version) {
    const bytes = utf8Bytes(text);
    const buffer = bitBuffer();
    buffer.put(0b0100, 4);
    buffer.put(bytes.length, version < 10 ? 8 : 16);
    for (const byte of bytes) buffer.put(byte, 8);
    const capacity = dataCapacity(version) * 8;
    for (let i = 0; i < Math.min(4, capacity - buffer.bits.length); i += 1) buffer.bits.push(0);
    while (buffer.bits.length % 8) buffer.bits.push(0);
    const words = [];
    for (let i = 0; i < buffer.bits.length; i += 8) {
      words.push(buffer.bits.slice(i, i + 8).reduce((value, bit) => (value << 1) | bit, 0));
    }
    let pad = 0;
    while (words.length < dataCapacity(version)) words.push(PAD[pad++ % 2]);
    return words;
  }

  const EXP = new Array(512);
  const LOG = new Array(256);
  (() => {
    let value = 1;
    for (let i = 0; i < 255; i += 1) {
      EXP[i] = value;
      LOG[value] = i;
      value <<= 1;
      if (value & 0x100) value ^= 0x11D;
    }
    for (let i = 255; i < 512; i += 1) EXP[i] = EXP[i - 255];
  })();
  const multiply = (a, b) => (a === 0 || b === 0 ? 0 : EXP[LOG[a] + LOG[b]]);

  function generator(degree) {
    let polynomial = [1];
    for (let i = 0; i < degree; i += 1) {
      const next = new Array(polynomial.length + 1).fill(0);
      for (let j = 0; j < polynomial.length; j += 1) {
        next[j] ^= polynomial[j];
        next[j + 1] ^= multiply(polynomial[j], EXP[i]);
      }
      polynomial = next;
    }
    return polynomial;
  }

  function remainder(data, degree) {
    const divisor = generator(degree);
    const result = data.concat(new Array(degree).fill(0));
    for (let i = 0; i < data.length; i += 1) {
      const factor = result[i];
      if (!factor) continue;
      for (let j = 0; j < divisor.length; j += 1) result[i + j] ^= multiply(divisor[j], factor);
    }
    return result.slice(data.length);
  }

  function interleave(words, version) {
    const groups = SPEC[version].blocks;
    const dataBlocks = [];
    const eccBlocks = [];
    let offset = 0;
    for (const [count, dataLength, eccLength] of groups) {
      for (let block = 0; block < count; block += 1) {
        const data = words.slice(offset, offset + dataLength);
        offset += dataLength;
        dataBlocks.push(data);
        eccBlocks.push(remainder(data, eccLength));
      }
    }
    const out = [];
    const longest = Math.max(...dataBlocks.map(block => block.length));
    for (let i = 0; i < longest; i += 1) {
      for (const block of dataBlocks) if (i < block.length) out.push(block[i]);
    }
    const longestEcc = Math.max(...eccBlocks.map(block => block.length));
    for (let i = 0; i < longestEcc; i += 1) {
      for (const block of eccBlocks) if (i < block.length) out.push(block[i]);
    }
    return out;
  }

  const MASKS = [
    (row, col) => (row + col) % 2 === 0,
    (row) => row % 2 === 0,
    (row, col) => col % 3 === 0,
    (row, col) => (row + col) % 3 === 0,
    (row, col) => (Math.floor(row / 2) + Math.floor(col / 3)) % 2 === 0,
    (row, col) => ((row * col) % 2) + ((row * col) % 3) === 0,
    (row, col) => (((row * col) % 2) + ((row * col) % 3)) % 2 === 0,
    (row, col) => (((row + col) % 2) + ((row * col) % 3)) % 2 === 0,
  ];

  function formatBits(mask) {
    let value = (ECC_FORMAT_BITS << 3) | mask;
    let rest = value << 10;
    for (let i = 14; i >= 10; i -= 1) if ((rest >>> i) & 1) rest ^= 0x537 << (i - 10);
    return ((value << 10) | rest) ^ 0x5412;
  }

  function versionBits(version) {
    let rest = version << 12;
    for (let i = 17; i >= 12; i -= 1) if ((rest >>> i) & 1) rest ^= 0x1F25 << (i - 12);
    return (version << 12) | rest;
  }

  function blank(size) {
    return Array.from({length: size}, () => new Array(size).fill(null));
  }

  function buildFunctionPatterns(version) {
    const size = 17 + version * 4;
    const modules = blank(size);
    const reserved = blank(size);
    const set = (row, col, dark) => {
      if (row < 0 || col < 0 || row >= size || col >= size) return;
      modules[row][col] = dark ? 1 : 0;
      reserved[row][col] = 1;
    };
    const finder = (top, left) => {
      for (let row = -1; row <= 7; row += 1) {
        for (let col = -1; col <= 7; col += 1) {
          const inside = row >= 0 && row <= 6 && col >= 0 && col <= 6;
          const dark = inside && (row === 0 || row === 6 || col === 0 || col === 6 || (row >= 2 && row <= 4 && col >= 2 && col <= 4));
          set(top + row, left + col, dark);
        }
      }
    };
    finder(0, 0);
    finder(0, size - 7);
    finder(size - 7, 0);
    for (let i = 8; i < size - 8; i += 1) {
      set(6, i, i % 2 === 0);
      set(i, 6, i % 2 === 0);
    }
    const centers = SPEC[version].align;
    for (const row of centers) {
      for (const col of centers) {
        if ((row === 6 && col === 6) || (row === 6 && col === size - 7) || (row === size - 7 && col === 6)) continue;
        for (let dr = -2; dr <= 2; dr += 1) {
          for (let dc = -2; dc <= 2; dc += 1) {
            const edge = Math.max(Math.abs(dr), Math.abs(dc));
            set(row + dr, col + dc, edge !== 1);
          }
        }
      }
    }
    for (let i = 0; i < 9; i += 1) {
      if (i !== 6) set(8, i, false);
      if (i !== 6) set(i, 8, false);
    }
    for (let i = 0; i < 8; i += 1) {
      set(8, size - 1 - i, false);
      set(size - 1 - i, 8, false);
    }
    set(size - 8, 8, true);
    if (version >= 7) {
      for (let i = 0; i < 6; i += 1) {
        for (let j = 0; j < 3; j += 1) {
          set(i, size - 11 + j, false);
          set(size - 11 + j, i, false);
        }
      }
    }
    return {modules, reserved, size};
  }

  function placeData(modules, reserved, words, version) {
    const size = modules.length;
    const bits = [];
    for (const word of words) for (let i = 7; i >= 0; i -= 1) bits.push((word >>> i) & 1);
    for (let i = 0; i < SPEC[version].remainder; i += 1) bits.push(0);
    let index = 0;
    let upward = true;
    for (let right = size - 1; right >= 1; right -= 2) {
      if (right === 6) right -= 1;
      for (let step = 0; step < size; step += 1) {
        const row = upward ? size - 1 - step : step;
        for (const col of [right, right - 1]) {
          if (reserved[row][col]) continue;
          modules[row][col] = index < bits.length ? bits[index] : 0;
          index += 1;
        }
      }
      upward = !upward;
    }
  }

  function applyMask(modules, reserved, mask) {
    const isMasked = MASKS[mask];
    for (let row = 0; row < modules.length; row += 1) {
      for (let col = 0; col < modules.length; col += 1) {
        if (!reserved[row][col] && isMasked(row, col)) modules[row][col] ^= 1;
      }
    }
  }

  function placeFormat(modules, version, mask) {
    const size = modules.length;
    const bits = formatBits(mask);
    for (let i = 0; i < 15; i += 1) {
      const dark = (bits >>> i) & 1;
      if (i < 6) modules[i][8] = dark;
      else if (i < 8) modules[i + 1][8] = dark;
      else modules[size - 15 + i][8] = dark;
    }
    for (let i = 0; i < 15; i += 1) {
      const dark = (bits >>> i) & 1;
      if (i < 8) modules[8][size - 1 - i] = dark;
      else if (i === 8) modules[8][7] = dark;
      else modules[8][14 - i] = dark;
    }
    modules[size - 8][8] = 1;
    if (version >= 7) {
      const versionValue = versionBits(version);
      for (let i = 0; i < 18; i += 1) {
        const dark = (versionValue >>> i) & 1;
        const row = Math.floor(i / 3);
        const col = size - 11 + (i % 3);
        modules[row][col] = dark;
        modules[col][row] = dark;
      }
    }
  }

  function penalty(modules) {
    const size = modules.length;
    let score = 0;
    const runScore = line => {
      let total = 0;
      let run = 1;
      for (let i = 1; i <= line.length; i += 1) {
        if (i < line.length && line[i] === line[i - 1]) run += 1;
        else {
          if (run >= 5) total += 3 + (run - 5);
          run = 1;
        }
      }
      return total;
    };
    const finder = [1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0];
    const reversed = [...finder].reverse();
    const matches = (line, start, pattern) => pattern.every((value, offset) => line[start + offset] === value);
    const linePenalty = line => {
      let total = runScore(line);
      for (let start = 0; start <= size - finder.length; start += 1) {
        if (matches(line, start, finder) || matches(line, start, reversed)) total += 40;
      }
      return total;
    };
    for (let row = 0; row < size; row += 1) score += linePenalty(modules[row]);
    for (let col = 0; col < size; col += 1) score += linePenalty(modules.map(line => line[col]));
    for (let row = 0; row < size - 1; row += 1) {
      for (let col = 0; col < size - 1; col += 1) {
        const value = modules[row][col];
        if (value === modules[row][col + 1] && value === modules[row + 1][col] && value === modules[row + 1][col + 1]) score += 3;
      }
    }
    let dark = 0;
    for (const row of modules) for (const value of row) dark += value;
    const percent = (dark * 100) / (size * size);
    score += Math.floor(Math.abs(percent - 50) / 5) * 10;
    return score;
  }

  function matrix(text, options = {}) {
    const version = chooseVersion(utf8Bytes(text).length);
    const words = interleave(dataCodewords(text, version), version);
    let best = null;
    const candidates = options.mask === undefined ? [0, 1, 2, 3, 4, 5, 6, 7] : [options.mask];
    for (const mask of candidates) {
      const {modules, reserved} = buildFunctionPatterns(version);
      placeData(modules, reserved, words, version);
      applyMask(modules, reserved, mask);
      placeFormat(modules, version, mask);
      const score = penalty(modules);
      if (!best || score < best.score) best = {score, modules};
    }
    return best.modules;
  }

  function svg(text, options = {}) {
    const margin = options.margin ?? 3;
    const modules = matrix(text);
    const size = modules.length;
    const span = size + margin * 2;
    let path = '';
    for (let row = 0; row < size; row += 1) {
      for (let col = 0; col < size; col += 1) {
        if (modules[row][col]) path += `M${col + margin} ${row + margin}h1v1h-1z`;
      }
    }
    const label = options.label ? ` aria-label="${String(options.label).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]))}"` : '';
    return `<svg class="qr" viewBox="0 0 ${span} ${span}" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges"${label}><rect width="${span}" height="${span}" fill="#fff"/><path d="${path}" fill="#000"/></svg>`;
  }

  return {matrix, svg, version: text => chooseVersion(utf8Bytes(text).length)};
})();

if (typeof module === 'object' && module.exports) module.exports = QRCode;
