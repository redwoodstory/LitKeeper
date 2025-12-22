const form = document.getElementById('downloadForm');
const submitBtn = form.querySelector('button[type="submit"]');
const loading = document.getElementById('loading');
const result = document.getElementById('result');
const formatError = document.getElementById('formatError');

form.addEventListener('submit', async (e) => {
  e.preventDefault();

  const formatCheckboxes = form.querySelectorAll('input[name="format"]:checked');
  if (formatCheckboxes.length === 0) {
    formatError.classList.remove('hidden');
    return;
  }
  formatError.classList.add('hidden');

  result.style.display = 'none';
  result.className = 'hidden mt-4 p-4 rounded-lg';
  loading.classList.remove('hidden');
  submitBtn.disabled = true;

  try {
    const formData = new FormData(form);
    const response = await fetch('/', {
      method: 'POST',
      body: formData
    });

    const data = await response.json();

    result.classList.remove('hidden');
    if (data.success === "true") {
      result.classList.add('bg-green-100', 'dark:bg-green-900', 'text-green-800', 'dark:text-green-200', 'border', 'border-green-200', 'dark:border-green-800');
      result.textContent = data.message;

      setTimeout(() => {
        window.location.reload();
      }, 1000);

      form.reset();
      form.querySelectorAll('input[name="format"]').forEach(cb => cb.checked = true);
    } else {
      result.classList.add('bg-red-100', 'dark:bg-red-900', 'text-red-800', 'dark:text-red-200', 'border', 'border-red-200', 'dark:border-red-800');
      result.textContent = data.message;
    }
  } catch (error) {
    result.classList.remove('hidden');
    result.classList.add('bg-red-100', 'dark:bg-red-900', 'text-red-800', 'dark:text-red-200', 'border', 'border-red-200', 'dark:border-red-800');
    result.textContent = 'An error occurred while processing your request.';
  } finally {
    loading.classList.add('hidden');
    submitBtn.disabled = false;
  }
});
