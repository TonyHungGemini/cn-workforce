'use strict';

const form = document.getElementById('login-form');
const input = document.getElementById('access-code');
const submit = document.getElementById('login-submit');
const error = document.getElementById('login-error');

function nextPath() {
  const value = new URLSearchParams(location.search).get('next') || '/';
  return value.startsWith('/') && !value.startsWith('//') ? value : '/';
}

fetch('/api/v1/session', {cache: 'no-store'})
  .then(response => response.json())
  .then(data => { if (data.authenticated) location.replace(nextPath()); })
  .catch(() => {});

form.addEventListener('submit', async event => {
  event.preventDefault();
  error.textContent = '';
  if (!input.value.trim()) {
    error.textContent = 'Vui lòng nhập mã truy cập.';
    input.focus();
    return;
  }
  submit.disabled = true;
  try {
    const response = await fetch('/api/v1/session', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({code: input.value.trim()}),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) throw new Error(data.error || 'Không đăng nhập được. Vui lòng thử lại.');
    location.replace(nextPath());
  } catch (failure) {
    error.textContent = failure.message;
    submit.disabled = false;
    input.select();
  }
});
