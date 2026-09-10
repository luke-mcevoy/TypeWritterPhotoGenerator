// Color fades between lossless endpoints that share one black drawing.
// Everything runs locally; dragging the slider does not request a new render.
document.querySelectorAll('section[data-stem]').forEach(section => {
  const buttons = [...section.querySelectorAll('button[data-version]')];
  const image = section.querySelector('.full img');
  const canvas = section.querySelector('.color-preview');
  const fullLink = section.querySelector('.full');
  const download = section.querySelector('.download');
  const controls = section.querySelector('.color-controls');
  const slider = section.querySelector('input[type="range"]');
  const output = section.querySelector('output');
  const status = section.querySelector('.color-status');
  const cache = new Map();
  let selected, endpoints, selection = 0, revision = 0, timer, objectURL;

  function endpoint(path) {
    if (!cache.has(path)) {
      const pending = (async () => {
        const picture = new Image();
        picture.src = path;
        await picture.decode();
        return picture;
      })().catch(error => { cache.delete(path); throw error; });
      cache.set(path, pending);
    }
    return cache.get(path);
  }

  function updateAmountLabel() {
    output.value = `${slider.value}%`;
    slider.setAttribute('aria-valuetext', `${slider.value}% color`);
    section.querySelector('.ribbons').textContent = Number(slider.value) === 0
      ? 'black only' : selected.dataset.ribbons;
  }

  function render() {
    if (!endpoints) return;
    const [mono, colored] = endpoints;
    const context = canvas.getContext('2d');
    context.globalAlpha = 1;
    context.drawImage(mono, 0, 0);
    context.globalAlpha = Number(slider.value) / 100;
    context.drawImage(colored, 0, 0);
    context.globalAlpha = 1;
    image.hidden = true;
    canvas.hidden = false;
    updateAmountLabel();
    const current = ++revision;
    const token = selection;
    // Delay PNG encoding until the user pauses; the visible canvas is immediate.
    clearTimeout(timer);
    download.setAttribute('aria-disabled', 'true');
    status.textContent = 'Preparing download…';
    timer = setTimeout(() => {
      canvas.toBlob(blob => {
        if (!blob || token !== selection || current !== revision) return;
        const next = URL.createObjectURL(blob);
        fullLink.href = download.href = next;
        download.download = `${section.dataset.stem}-${selected.dataset.version}-${slider.value}pct.png`;
        download.removeAttribute('aria-disabled');
        status.textContent = `${slider.value}% color ready`;
        if (objectURL) URL.revokeObjectURL(objectURL);
        objectURL = next;
      }, 'image/png');
    }, 140);
  }

  async function choose(button) {
    const token = ++selection;
    clearTimeout(timer);
    endpoints = null;
    selected = button;
    const key = button.dataset.version;
    const colored = key === 'color' || key === 'refined';
    buttons.forEach(b => b.setAttribute('aria-pressed', String(b === button)));
    section.querySelector('.showing strong').textContent = button.textContent;
    section.querySelector('.ribbons').textContent = button.dataset.ribbons;
    const path = `${section.dataset.stem}-${key}.jpg`;
    image.src = path;
    image.alt = button.textContent;
    image.hidden = false;
    canvas.hidden = true;
    fullLink.href = download.href = path;
    download.download = `${section.dataset.stem}-${key}.jpg`;
    controls.hidden = !colored;
    slider.disabled = colored;
    if (colored) download.setAttribute('aria-disabled', 'true');
    else download.removeAttribute('aria-disabled');
    if (!colored) return;
    status.textContent = 'Loading color controls…';
    updateAmountLabel();
    try {
      const pair = await Promise.all([
        endpoint(`${section.dataset.stem}-${key}-none.png`),
        endpoint(`${section.dataset.stem}-${key}-full.png`),
      ]);
      if (token !== selection) return;
      if (pair[0].naturalWidth !== pair[1].naturalWidth || pair[0].naturalHeight !== pair[1].naturalHeight) {
        throw new Error('Mismatched color endpoints');
      }
      endpoints = pair;
      canvas.width = pair[0].naturalWidth;
      canvas.height = pair[0].naturalHeight;
      canvas.setAttribute('aria-label', button.textContent);
      slider.disabled = false;
      render();
    } catch (error) {
      if (token !== selection) return;
      status.textContent = 'Showing the saved preview. Select the version again to retry color controls.';
      output.value = 'Saved preview';
      download.removeAttribute('aria-disabled');
    }
  }

  slider.addEventListener('input', render);
  buttons.forEach(button => button.addEventListener('click', () => choose(button)));
  // Never open/download a stale amount while its current PNG is being encoded.
  for (const link of [fullLink, download]) {
    link.addEventListener('click', event => {
      if (!controls.hidden && download.getAttribute('aria-disabled') === 'true') event.preventDefault();
    });
  }
  window.addEventListener('pagehide', () => { if (objectURL) URL.revokeObjectURL(objectURL); });
  choose(buttons.find(button => button.getAttribute('aria-pressed') === 'true'));
});
