'use strict';
const copy = document.getElementById('copy');
copy.addEventListener('click', async () => {
  const status = document.getElementById('copy-status');
  try {
    await navigator.clipboard.writeText(document.getElementById('commands').textContent);
    status.textContent = 'Commands copied.';
  } catch {
    status.textContent = 'Select and copy the commands manually.';
  }
});
