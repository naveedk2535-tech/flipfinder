// ===== IMAGE UPLOAD PREVIEW =====
function initImageUpload() {
  const zone = document.getElementById('upload-zone');
  const input = document.getElementById('image-input');
  if (!zone || !input) return;

  const placeholder = document.getElementById('upload-placeholder');
  const preview = document.getElementById('upload-preview');
  const previewImg = document.getElementById('preview-img');
  const previewName = document.getElementById('preview-name');
  const clearBtn = document.getElementById('clear-image');

  zone.addEventListener('click', (e) => {
    if (!e.target.closest('#upload-preview')) input.click();
  });

  zone.addEventListener('dragover', (e) => {
    e.preventDefault();
    zone.classList.add('drag-over');
  });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', (e) => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) showPreview(file);
  });

  input.addEventListener('change', () => {
    if (input.files[0]) showPreview(input.files[0]);
  });

  function showPreview(file) {
    if (file.size > 8 * 1024 * 1024) {
      alert('File too large. Maximum size is 8MB.');
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      previewImg.src = e.target.result;
      const sizeMB = (file.size / 1024 / 1024).toFixed(2);
      previewName.textContent = file.name + ' (' + sizeMB + ' MB)';
      placeholder.classList.add('hidden');
      preview.classList.remove('hidden');
    };
    reader.readAsDataURL(file);
  }

  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      input.value = '';
      preview.classList.add('hidden');
      placeholder.classList.remove('hidden');
      previewImg.src = '';
    });
  }
}

// ===== CHARACTER COUNTER =====
function initCharCounter() {
  const textarea = document.getElementById('description');
  const counter = document.getElementById('char-count');
  if (!textarea || !counter) return;
  textarea.addEventListener('input', () => {
    counter.textContent = textarea.value.length;
  });
}

// ===== FORM LOADING STATE =====
function initFormLoading() {
  const form = document.getElementById('analysis-form');
  if (!form) return;
  form.addEventListener('submit', (e) => {
    const input = document.getElementById('image-input');
    const desc = document.getElementById('description');
    const link = form.querySelector('input[name="link"]');

    const hasImage = input && input.files && input.files[0];
    const hasText = desc && desc.value.trim().length > 0;
    const hasLink = link && link.value.trim().length > 0;

    if (!hasImage && !hasText && !hasLink) {
      e.preventDefault();
      alert('Please provide an image, description, or product URL before analysing.');
      return;
    }

    const btn = document.getElementById('submit-btn');
    const txt = document.getElementById('submit-text');
    if (btn) { btn.disabled = true; btn.classList.add('opacity-70'); }
    if (txt) txt.textContent = 'Analysing...';
    if (typeof lucide !== 'undefined') lucide.createIcons();
  });
}

// ===== CHART BAR ANIMATIONS =====
function initChartBars() {
  document.querySelectorAll('.chart-bar[data-height]').forEach(bar => {
    const h = bar.dataset.height;
    setTimeout(() => { bar.style.height = h + '%'; }, 200);
  });
}

// ===== OPPORTUNITY BAR ANIMATION =====
function initOpportunityBar() {
  const bar = document.querySelector('.opportunity-bar[data-width]');
  if (bar) {
    setTimeout(() => { bar.style.width = bar.dataset.width + '%'; }, 100);
  }
}

// ===== FLASH AUTO DISMISS =====
function initFlashDismiss() {
  setTimeout(() => {
    document.querySelectorAll('.flash-msg').forEach(el => {
      el.style.transition = 'opacity 0.5s ease';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 500);
    });
  }, 5000);
}

// ===== INIT ALL =====
document.addEventListener('DOMContentLoaded', () => {
  initImageUpload();
  initCharCounter();
  initFormLoading();
  initChartBars();
  initOpportunityBar();
  initFlashDismiss();
  if (typeof lucide !== 'undefined') lucide.createIcons();
});
