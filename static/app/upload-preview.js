document.querySelectorAll('input[type="file"]').forEach((input) => {
  const label = Array.from(document.querySelectorAll('label[for]'))
    .find((candidate) => candidate.htmlFor === input.id);
  if (!label) return;

  const fileName = document.createElement('span');
  fileName.className = 'upload-filename';
  fileName.setAttribute('aria-live', 'polite');
  label.append(fileName);

  let previewUrl = null;
  input.addEventListener('change', () => {
    const file = input.files?.[0];
    fileName.textContent = file ? file.name : '';
    input.parentElement.querySelectorAll(`[data-upload-preview="${input.id}"]`)
      .forEach((preview) => preview.remove());

    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      previewUrl = null;
    }
    if (!file) return;

    const isImage = file.type.startsWith('image/');
    const isVideo = file.type.startsWith('video/');
    if (!isImage && !isVideo) return;

    previewUrl = URL.createObjectURL(file);
    const preview = document.createElement(isImage ? 'img' : 'video');
    preview.className = 'upload-preview';
    preview.dataset.uploadPreview = input.id;
    preview.src = previewUrl;
    preview.alt = isImage ? file.name : '';
    if (isVideo) {
      preview.controls = true;
      preview.playsInline = true;
    }
    input.insertAdjacentElement('afterend', preview);
  });
});
