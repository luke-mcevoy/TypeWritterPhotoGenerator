(() => {
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    let originalFile = null;
    let currentFile = null;
    let currentImageData = null;
    let currentHtmlData = null;
    let currentTextData = null;
    let cropper = null;
    let debounceTimer = null;
    let abort = null;
    let genSeq = 0;
    let zoomMode = "fit";
    let printing = false;

    const dropZone = $("#drop-zone");
    const fileInput = $("#file-input");
    const cropSection = $("#crop-section");
    const cropImage = $("#crop-image");
    const workspace = $("#workspace");
    const originalImage = $("#original-image");
    const glyphImage = $("#glyph-image");
    const sideOriginal = $("#side-original");
    const sideGlyph = $("#side-glyph");
    const glyphPlaceholder = $("#glyph-placeholder");
    const sideGlyphPlaceholder = $("#side-glyph-placeholder");
    const liveStatus = $("#live-status");
    const liveText = $("#live-text");
    const downloadSection = $("#download-section");
    const dimensionsInfo = $("#dimensions-info");

    const columnsSlider = $("#columns-slider");
    const contrastSlider = $("#contrast-slider");
    const detailSlider = $("#detail-slider");
    const overstrikeSlider = $("#overstrike-slider");
    const pressureSlider = $("#pressure-slider");
    const wanderSlider = $("#wander-slider");
    const scaleSlider = $("#scale-slider");
    const simplifySlider = $("#simplify-slider");
    const charsetSelect = $("#charset-select");
    const paperSelect = $("#paper-select");
    const inkSelect = $("#ink-select");
    const inscriptionInput = $("#inscription-input");
    const invertCheck = $("#invert-check");

    const PRESETS = {
        study: {
            charset: "classic",
            columns: 110,
            contrast: 1.25,
            detail: 0.25,
            simplify: 0.5,
            overstrike: 0,
            pressure: 0.82,
            wander: 0.55,
            scale: 1,
        },
        portrait: {
            charset: "portrait",
            columns: 180,
            contrast: 1.4,
            detail: 0.4,
            simplify: 0.4,
            overstrike: 1,
            pressure: 0.88,
            wander: 0.7,
            scale: 2,
        },
        scene: {
            charset: "scene",
            columns: 170,
            contrast: 1.45,
            detail: 0.25,
            simplify: 0.75,
            overstrike: 1,
            pressure: 0.9,
            wander: 0.8,
            scale: 2,
        },
        architecture: {
            charset: "architecture",
            columns: 200,
            contrast: 1.5,
            detail: 0.35,
            simplify: 0.7,
            overstrike: 1,
            pressure: 0.9,
            wander: 0.45,
            scale: 2,
        },
        exhibition: {
            charset: "scene",
            columns: 220,
            contrast: 1.4,
            detail: 0.3,
            simplify: 0.7,
            overstrike: 2,
            pressure: 0.92,
            wander: 0.65,
            scale: 3,
        },
    };

    dropZone.addEventListener("click", () => fileInput.click());
    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("drag-over");
    });
    dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("drag-over");
        const files = e.dataTransfer.files;
        if (files.length > 0 && files[0].type.startsWith("image/")) {
            handleFile(files[0]);
        }
    });
    fileInput.addEventListener("change", () => {
        if (fileInput.files.length > 0) handleFile(fileInput.files[0]);
    });
    $("#change-image-btn").addEventListener("click", () => {
        fileInput.value = "";
        fileInput.click();
    });
    $("#crop-btn").addEventListener("click", () => {
        if (originalFile) showCropper(originalFile);
    });

    function handleFile(file) {
        originalFile = file;
        currentImageData = null;
        currentHtmlData = null;
        currentTextData = null;
        openWorkspace(file, URL.createObjectURL(file));
        generate({ preview: true });
    }

    function showCropper(file) {
        cropSection.classList.remove("hidden");
        if (cropper) {
            cropper.destroy();
            cropper = null;
        }
        const url = URL.createObjectURL(file);
        cropImage.src = url;
        cropImage.onload = () => {
            cropper = new Cropper(cropImage, {
                viewMode: 1,
                autoCropArea: 1,
                responsive: true,
                background: false,
                guides: true,
                center: true,
                highlight: true,
                movable: true,
                zoomable: true,
                rotatable: false,
                scalable: false,
            });
        };
    }

    $("#apply-crop-btn").addEventListener("click", () => {
        if (!cropper) return;
        const canvas = cropper.getCroppedCanvas();
        canvas.toBlob((blob) => {
            const croppedFile = new File([blob], (originalFile || currentFile).name, { type: "image/png" });
            openWorkspace(croppedFile, canvas.toDataURL("image/png"));
            generate({ preview: true });
        }, "image/png");
    });

    $("#skip-crop-btn").addEventListener("click", () => {
        if (cropper) {
            cropper.destroy();
            cropper = null;
        }
        cropSection.classList.add("hidden");
    });

    function openWorkspace(file, previewUrl) {
        currentFile = file;
        if (cropper) {
            cropper.destroy();
            cropper = null;
        }
        cropSection.classList.add("hidden");
        workspace.classList.add("has-file");
        document.body.classList.add("has-file");
        originalImage.src = previewUrl;
        sideOriginal.src = previewUrl;
        downloadSection.classList.remove("hidden");
        switchTab("drawing");
    }

    $$(".tab").forEach((tab) => {
        tab.addEventListener("click", () => switchTab(tab.dataset.tab));
    });

    function switchTab(name) {
        $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
        $$(".preview-pane").forEach((p) => p.classList.remove("active"));
        $(`#preview-${name}`).classList.add("active");
    }

    function bindSlider(slider, label, digits) {
        const paint = () => {
            const n = parseFloat(slider.value);
            label.textContent = Number.isInteger(n) || digits === 0 ? String(n) : n.toFixed(digits);
        };
        slider.addEventListener("input", paint);
        paint();
    }

    bindSlider(columnsSlider, $("#columns-value"), 0);
    bindSlider(contrastSlider, $("#contrast-value"), 2);
    bindSlider(detailSlider, $("#detail-value"), 2);
    bindSlider(simplifySlider, $("#simplify-value"), 2);
    bindSlider(overstrikeSlider, $("#overstrike-value"), 0);
    bindSlider(pressureSlider, $("#pressure-value"), 2);
    bindSlider(wanderSlider, $("#wander-value"), 2);
    bindSlider(scaleSlider, $("#scale-value"), 0);

    const liveControls = [
        columnsSlider,
        contrastSlider,
        detailSlider,
        simplifySlider,
        overstrikeSlider,
        pressureSlider,
        wanderSlider,
        charsetSelect,
        paperSelect,
        inkSelect,
        invertCheck,
    ];
    liveControls.forEach((el) => {
        el.addEventListener("input", () => scheduleGenerate(70));
        el.addEventListener("change", () => scheduleGenerate(40));
    });
    inscriptionInput.addEventListener("input", () => scheduleGenerate(500));

    $$(".preset").forEach((btn) => {
        btn.addEventListener("click", () => applyPreset(btn.dataset.preset));
    });

    function applyPreset(name) {
        const p = PRESETS[name];
        if (!p) return;
        $$(".preset").forEach((b) => b.classList.toggle("active", b.dataset.preset === name));
        charsetSelect.value = p.charset;
        columnsSlider.value = p.columns;
        contrastSlider.value = p.contrast;
        detailSlider.value = p.detail;
        simplifySlider.value = p.simplify;
        overstrikeSlider.value = p.overstrike;
        pressureSlider.value = p.pressure;
        wanderSlider.value = p.wander;
        scaleSlider.value = p.scale;
        [
            columnsSlider,
            contrastSlider,
            detailSlider,
            simplifySlider,
            overstrikeSlider,
            pressureSlider,
            wanderSlider,
            scaleSlider,
        ].forEach((s) => s.dispatchEvent(new Event("input")));
        scheduleGenerate(80);
    }

    $$(".zoom-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            zoomMode = btn.dataset.zoom;
            applyZoom(zoomMode);
        });
    });

    function applyZoom(mode) {
        const box = $("#preview-container");
        $$(".zoom-btn").forEach((b) => b.classList.toggle("active", b.dataset.zoom === mode));
        box.classList.toggle("zoomed", mode !== "fit");
        glyphImage.style.width = "";
        if (mode === "1" && glyphImage.naturalWidth) {
            glyphImage.style.width = `${glyphImage.naturalWidth}px`;
        } else if (mode === "2" && glyphImage.naturalWidth) {
            glyphImage.style.width = `${glyphImage.naturalWidth * 2}px`;
        }
    }

    function scheduleGenerate(ms) {
        if (!currentFile || printing) return;
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => generate({ preview: true }), ms);
    }

    function setLive(busy, label) {
        liveStatus.classList.toggle("busy", busy);
        liveText.textContent = label;
    }

    async function generate({ preview = true, scale = null } = {}) {
        if (!currentFile) return null;
        if (preview && printing) return null;
        if (preview) {
            if (abort) abort.abort();
            abort = new AbortController();
        } else {
            printing = true;
            clearTimeout(debounceTimer);
            if (abort) abort.abort();
            abort = new AbortController();
        }
        const seq = ++genSeq;
        const signal = abort.signal;
        setLive(true, preview ? "Typing…" : "Printing…");

        const formData = new FormData();
        formData.append("image", currentFile);
        formData.append("columns", columnsSlider.value);
        formData.append("charset", charsetSelect.value);
        formData.append("paper", paperSelect.value);
        formData.append("ink", inkSelect.value);
        formData.append("contrast", contrastSlider.value);
        formData.append("detail", detailSlider.value);
        formData.append("simplify", simplifySlider.value);
        formData.append("overstrike", overstrikeSlider.value);
        formData.append("pressure", pressureSlider.value);
        formData.append("wander", wanderSlider.value);
        formData.append("scale", scale == null ? scaleSlider.value : String(scale));
        formData.append("tightness", "0.90");
        formData.append("inscription", inscriptionInput.value.trim());
        formData.append("invert", invertCheck.checked ? "1" : "0");
        formData.append("preview", preview ? "1" : "0");

        try {
            const resp = await fetch("/convert", {
                method: "POST",
                body: formData,
                signal,
            });
            const data = await resp.json();
            if (seq !== genSeq) return null;
            if (!resp.ok) {
                setLive(false, "Jammed");
                toast(data.error || "The machine jammed", "error");
                return null;
            }
            currentHtmlData = data.html_data;
            currentTextData = data.text_data;
            if (!preview) currentImageData = data.image_data;
            else currentImageData = data.image_data;

            glyphImage.onload = () => applyZoom(zoomMode);
            glyphImage.src = data.image_data;
            sideGlyph.src = data.image_data;
            glyphImage.classList.remove("hidden");
            sideGlyph.classList.remove("hidden");
            glyphPlaceholder.classList.add("hidden");
            sideGlyphPlaceholder.classList.add("hidden");
            downloadSection.classList.remove("hidden");
            const d = data.dimensions;
            dimensionsInfo.textContent =
                `${d.chars_wide} × ${d.chars_tall} keys · ${d.img_width} × ${d.img_height} px`;
            setLive(false, "Live");
            return data;
        } catch (err) {
            if (err.name === "AbortError") return null;
            if (seq === genSeq) {
                setLive(false, "Jammed");
                toast("Network error: " + err.message, "error");
            }
            return null;
        } finally {
            if (!preview) printing = false;
        }
    }

    $("#download-image-btn").addEventListener("click", async () => {
        const scale = parseInt(scaleSlider.value, 10);
        setLive(true, "Printing…");
        const data = await generate({ preview: false, scale });
        if (data && data.image_data) {
            downloadUrl(data.image_data, "typewriter-drawing.jpg");
            setLive(false, "Live");
        }
    });

    $("#download-html-btn").addEventListener("click", () => {
        if (!currentHtmlData) return;
        const blob = new Blob([currentHtmlData], { type: "text/html" });
        const url = URL.createObjectURL(blob);
        downloadUrl(url, "typewriter-drawing.html");
        URL.revokeObjectURL(url);
    });

    const postBtn = $("#post-btn");
    const postModal = $("#post-modal");
    const postCaption = $("#post-caption");
    if (postBtn) {
        postBtn.addEventListener("click", () => {
            if (!window.CARRIAGE || !window.CARRIAGE.signedIn) {
                window.location.href = (window.CARRIAGE && window.CARRIAGE.loginUrl) || "/login?next=/studio";
                return;
            }
            if (!currentImageData) {
                toast("Type a drawing first", "error");
                return;
            }
            postModal.classList.remove("hidden");
            postCaption.focus();
        });
    }
    $("#cancel-post-btn")?.addEventListener("click", () => postModal.classList.add("hidden"));
    $("#confirm-post-btn")?.addEventListener("click", async () => {
        if (!currentFile) return;
        const confirmBtn = $("#confirm-post-btn");
        confirmBtn.disabled = true;
        clearTimeout(debounceTimer);
        const scale = parseInt(scaleSlider.value, 10);
        setLive(true, "Printing…");
        let imageData = currentImageData;
        const hi = await generate({ preview: false, scale });
        if (hi && hi.image_data) imageData = hi.image_data;
        if (!imageData) {
            confirmBtn.disabled = false;
            toast("Could not post that drawing", "error");
            return;
        }
        try {
            const resp = await fetch("/api/posts", {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-Requested-With": "fetch" },
                body: JSON.stringify({
                    image_data: imageData,
                    source_data: await fileToDataUrl(currentFile),
                    caption: postCaption.value.trim(),
                }),
            });
            const data = await resp.json();
            if (!resp.ok) {
                confirmBtn.disabled = false;
                if (data.login) {
                    window.location.href = window.CARRIAGE.loginUrl;
                    return;
                }
                toast(data.error || "Could not post", "error");
                return;
            }
            postModal.classList.add("hidden");
            postCaption.value = "";
            toast("On the wall");
            setTimeout(() => {
                window.location.href = data.post.url;
            }, 400);
        } catch (err) {
            confirmBtn.disabled = false;
            toast("Could not post: " + err.message, "error");
        }
    });

    $("#download-text-btn").addEventListener("click", () => {
        if (!currentTextData) return;
        const blob = new Blob([currentTextData], { type: "text/plain" });
        const url = URL.createObjectURL(blob);
        downloadUrl(url, "typewriter-drawing.txt");
        URL.revokeObjectURL(url);
    });

    async function fileToDataUrl(file) {
        if (!file) return "";
        try {
            const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
            const canvas = document.createElement("canvas");
            canvas.width = bitmap.width;
            canvas.height = bitmap.height;
            canvas.getContext("2d").drawImage(bitmap, 0, 0);
            bitmap.close();
            return canvas.toDataURL("image/jpeg", 0.88);
        } catch (_err) {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result);
                reader.onerror = reject;
                reader.readAsDataURL(file);
            });
        }
    }

    function downloadUrl(href, name) {
        const a = document.createElement("a");
        a.href = href;
        a.download = name;
        a.click();
    }

    function toast(message, type = "") {
        const el = document.createElement("div");
        el.className = `toast ${type}`;
        el.textContent = message;
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 2800);
    }
})();
