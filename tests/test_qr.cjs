const {test} = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const path = require('node:path');
const QR = require(path.join(__dirname, '../static/qr.js'));

// Reference matrices were cross-checked module-by-module against qrcode@1.5.4
// (byte mode, ECC M) for every mask 0-7 on versions 1-10 before being frozen here.
const digest = matrix => crypto.createHash('sha256').update(matrix.map(row => row.join('')).join('\n')).digest('hex');
const vectors = [
  {text: 'C2-0001', version: 1, mask: 2, hash: '1dec5bd97655cdf771c220fa5e8d26e425a4fca5457b21c315f813f3ac7263ec'},
  {text: 'KH-291026-0007', version: 1, mask: 0, hash: 'da0a915bb5e9fd87f6d0e8dd6d1984330e1876d90e392668e65d78ff095ad831'},
  {text: 'CRCK2-DSX02-KV2-001', version: 2, mask: 2, hash: 'ddfe20539f6468bbb649febcfae5a06c50c27058009e2a397c1dc650f08c0e80'},
  {text: 'C2-9999', version: 1, mask: 4, hash: '7d5073e64088ae484ab333f89848ff19cf78f11797ec56a4ffb5e600e716620a'},
  {text: 'A'.repeat(213), version: 10, mask: 3, hash: '8dac1222425d443a7a95a5b9aaac3fdda1206fa4f149363e5987ab516e76f15e'},
];

function readFormat(matrix, copy) {
  const size = matrix.length;
  const bits = [];
  if (copy === 1) {
    for (let i = 0; i < 6; i += 1) bits.push(matrix[i][8]);
    bits.push(matrix[7][8], matrix[8][8], matrix[8][7]);
    for (let i = 9; i < 15; i += 1) bits.push(matrix[8][14 - i]);
  } else {
    for (let i = 0; i < 8; i += 1) bits.push(matrix[8][size - 1 - i]);
    for (let i = 8; i < 15; i += 1) bits.push(matrix[size - 15 + i][8]);
  }
  return bits.reduce((value, bit, index) => value | (bit << index), 0);
}

function finderIsValid(matrix, top, left) {
  for (let row = 0; row < 7; row += 1) {
    for (let col = 0; col < 7; col += 1) {
      const edge = row === 0 || row === 6 || col === 0 || col === 6;
      const center = row >= 2 && row <= 4 && col >= 2 && col <= 4;
      if (matrix[top + row][left + col] !== (edge || center ? 1 : 0)) return false;
    }
  }
  return true;
}

test('frozen QR matrices match the reference encoder', () => {
  for (const vector of vectors) {
    const matrix = QR.matrix(vector.text);
    assert.equal((matrix.length - 17) / 4, vector.version, `version ${vector.text.slice(0, 12)}`);
    assert.equal(digest(matrix), vector.hash, `matrix ${vector.text.slice(0, 12)}`);
    assert.equal(digest(QR.matrix(vector.text, {mask: vector.mask})), vector.hash, 'mask override must reproduce the chosen symbol');
  }
});

test('version is chosen from byte length before overflow', () => {
  assert.equal(QR.version('C2-0001'), 1);
  assert.equal(QR.version('A'.repeat(14)), 1);
  assert.equal(QR.version('A'.repeat(15)), 2);
  assert.equal(QR.version('A'.repeat(213)), 10);
  assert.throws(() => QR.matrix('A'.repeat(214)), /quá dài/);
  assert.equal(QR.matrix('Nguyễn').length, 21);
});

test('symbol keeps finder, timing and dark module patterns intact', () => {
  for (const vector of vectors) {
    const matrix = QR.matrix(vector.text);
    const size = matrix.length;
    assert.ok(finderIsValid(matrix, 0, 0), 'top-left finder');
    assert.ok(finderIsValid(matrix, 0, size - 7), 'top-right finder');
    assert.ok(finderIsValid(matrix, size - 7, 0), 'bottom-left finder');
    for (let i = 8; i < size - 8; i += 1) {
      assert.equal(matrix[6][i], i % 2 === 0 ? 1 : 0, 'horizontal timing');
      assert.equal(matrix[i][6], i % 2 === 0 ? 1 : 0, 'vertical timing');
    }
    assert.equal(matrix[size - 8][8], 1, 'dark module');
  }
});

test('format information encodes ECC M and a legal mask', () => {
  for (const vector of vectors) {
    const matrix = QR.matrix(vector.text);
    const first = readFormat(matrix, 1);
    assert.equal(readFormat(matrix, 2), first, 'format copies must agree');
    const value = first ^ 0x5412;
    const data = value >> 10;
    assert.equal((data >> 3) & 3, 0, 'ECC level M');
    const mask = data & 7;
    assert.equal(mask, vector.mask);
    let rest = data << 10;
    for (let i = 14; i >= 10; i -= 1) if ((rest >> i) & 1) rest ^= 0x537 << (i - 10);
    assert.equal(rest, value & 0x3ff, 'BCH remainder');
  }
});

test('SVG output is self contained and escapes labels', () => {
  const svg = QR.svg('C2-0001', {margin: 1, label: 'Mã "QR" <b>'});
  assert.match(svg, /^<svg class="qr" viewBox="0 0 23 23"/);
  assert.match(svg, /<path d="M/);
  assert.match(svg, /aria-label="Mã &quot;QR&quot; &lt;b&gt;"/);
  assert.doesNotMatch(svg, /<b>|<script|href=/);
  assert.notEqual(QR.svg('C2-0001'), QR.svg('C2-0002'));
  assert.notEqual(QR.svg('C2-0001', {margin: 1}), QR.svg('C2-0001'));
});
