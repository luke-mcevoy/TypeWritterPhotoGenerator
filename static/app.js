(() => {
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    let originalFile = null;
    let currentFile = null;
    let currentImageData = null;
    let currentHtmlData = null;
    let currentTextData = null;
    let cropper = null;
    let pendingCropFile = null;
    let cropUrl = null;
    let previewUrl = null;
    let cropRevision = 0;
    let cropFocus = null;
    let savedCrop = null;
    let debounceTimer = null;
    let abort = null;
    let genSeq = 0;
    let zoomMode = "fit";
    let printing = false;
    let colorEndpoints = null;
    const colorCanvas = document.createElement("canvas");

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
    const liveBar = $("#live-bar");
    const liveBarFill = $("#live-bar-fill");
    const livePct = $("#live-pct");
    const postProgress = $("#post-progress");
    const postProgressFill = $("#post-progress-fill");
    const postProgressLabel = $("#post-progress-label");
    const postProgressPct = $("#post-progress-pct");
    const stageProgress = $("#stage-progress");
    const stageProgressFill = $("#stage-progress-fill");
    const stageProgressLabel = $("#stage-progress-label");
    const stageProgressPct = $("#stage-progress-pct");
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
    const drawingStyle = $("#drawing-style");
    const colorAmountSlider = $("#color-amount-slider");
    const shadowFillSlider = $("#shadow-fill-slider");

    function syncDrawingStyle() {
        const original = drawingStyle.value === "original";
        $("#color-controls").classList.toggle("hidden", !["vibrant", "refined", "ribbon"].includes(drawingStyle.value));
        $$(".vibrant-only").forEach(el => el.classList.toggle("hidden", drawingStyle.value !== "vibrant"));
        $$(".original-only").forEach(el => el.classList.toggle("hidden", !original));
        $$(".contour-only").forEach(el => el.classList.toggle("hidden", original));
        $("#download-text-btn").classList.toggle("hidden", !original || !currentTextData);
        $("#download-html-btn").classList.toggle("hidden", !original || !currentHtmlData);
    }

    function paintColor() {
        $("#color-amount-value").value = `${colorAmountSlider.value}%`;
        colorAmountSlider.setAttribute("aria-valuetext", `${colorAmountSlider.value}% color`);
        if (!colorEndpoints) return;
        const context = colorCanvas.getContext("2d");
        const [mono, full] = colorEndpoints;
        colorCanvas.width = mono.naturalWidth;
        colorCanvas.height = mono.naturalHeight;
        const amount = Number(colorAmountSlider.value) / 100;
        const blended = context.createImageData(colorCanvas.width, colorCanvas.height);
        for (let i = 0; i < blended.data.length; i++) {
            blended.data[i] = Math.round(mono.rgba[i]*(1-amount) + full.rgba[i]*amount);
        }
        context.putImageData(blended, 0, 0);
        currentImageData = colorCanvas.toDataURL("image/png");
        glyphImage.src = sideGlyph.src = currentImageData;
    }

    colorAmountSlider.addEventListener("input", paintColor);
    drawingStyle.addEventListener("change", syncDrawingStyle);
    syncDrawingStyle();
    paintColor();

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
            columns: 200,
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
        if (printing) return;
        if (!file.type.startsWith("image/")) return toast("Choose an image file", "error");
        showCropper(file);
    }

    function showCropper(file) {
        if (printing) return;
        closeCropper(false);
        pendingCropFile = file;
        cropFocus = document.activeElement;
        const revision = cropRevision;
        $("#apply-crop-btn").disabled = true;
        $("#crop-ratio").value = "free";
        $("#crop-size").textContent = "Loading photo…";
        cropSection.classList.remove("hidden");
        cropImage.onload = () => {
            if (revision !== cropRevision) return;
            if (!window.Cropper) {
                $("#crop-size").textContent = "Crop controls could not load. You can still use the full image.";
                return;
            }
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
                ready() {
                    if (revision !== cropRevision) return;
                    if (file === originalFile && savedCrop) cropper.setData(savedCrop);
                    $("#apply-crop-btn").disabled = false;
                },
                crop(event) {
                    $("#crop-size").textContent = `${Math.round(event.detail.width)} × ${Math.round(event.detail.height)} pixels`;
                },
            });
        };
        cropImage.onerror = () => {
            if (revision !== cropRevision) return;
            closeCropper();
            toast("This photo could not be opened. Try a JPEG, PNG or WebP image.", "error");
        };
        cropUrl = URL.createObjectURL(file);
        cropImage.src = cropUrl;
        $("#skip-crop-btn").focus();
    }

    function closeCropper(restoreFocus = true) {
        ++cropRevision;
        if (cropper) cropper.destroy();
        cropper = null;
        pendingCropFile = null;
        cropImage.onload = cropImage.onerror = null;
        cropSection.classList.add("hidden");
        if (cropUrl) URL.revokeObjectURL(cropUrl);
        cropUrl = null;
        if (restoreFocus && cropFocus?.isConnected) cropFocus.focus();
    }

    function acceptPhoto(file, original, selection = null) {
        ++genSeq;
        clearTimeout(debounceTimer);
        originalFile = original;
        savedCrop = selection;
        currentImageData = currentHtmlData = currentTextData = null;
        colorEndpoints = null;
        glyphImage.classList.add("hidden");
        sideGlyph.classList.add("hidden");
        openWorkspace(file, URL.createObjectURL(file));
        generate({ preview: true });
    }

    $("#apply-crop-btn").addEventListener("click", () => {
        if (!cropper) return;
        const revision = cropRevision;
        const file = pendingCropFile;
        const selection = cropper.getData(true);
        const canvas = cropper.getCroppedCanvas({ maxWidth: 4096, maxHeight: 4096 });
        if (!canvas || !canvas.width || !canvas.height) return toast("Select an area to crop", "error");
        $("#apply-crop-btn").disabled = true;
        canvas.toBlob((blob) => {
            if (revision !== cropRevision) return;
            if (!blob) {
                $("#apply-crop-btn").disabled = false;
                return toast("Could not crop this photo", "error");
            }
            const croppedFile = new File([blob], file.name.replace(/\.[^.]+$/, "") + "-crop.png", { type: "image/png" });
            acceptPhoto(croppedFile, file, selection);
        }, "image/png");
    });

    $("#skip-crop-btn").addEventListener("click", () => closeCropper());
    $("#use-full-image-btn").addEventListener("click", () => {
        if (pendingCropFile) acceptPhoto(pendingCropFile, pendingCropFile);
    });
    $("#reset-crop-btn").addEventListener("click", () => {
        $("#crop-ratio").value = "free";
        cropper?.setAspectRatio(NaN);
        cropper?.reset();
    });
    $("#crop-ratio").addEventListener("change", event => {
        cropper?.setAspectRatio(event.target.value === "free" ? NaN : Number(event.target.value));
    });
    cropSection.addEventListener("keydown", event => {
        if (event.key === "Escape") { event.preventDefault(); closeCropper(); }
        if (event.key !== "Tab") return;
        const controls = [...cropSection.querySelectorAll("button:not(:disabled), select")];
        const first = controls[0], last = controls.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });

    function openWorkspace(file, nextUrl) {
        currentFile = file;
        closeCropper();
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        previewUrl = nextUrl;
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
    if (shadowFillSlider) {
        const paintShadow = () => {
            $("#shadow-fill-value").textContent = `${shadowFillSlider.value}%`;
        };
        shadowFillSlider.addEventListener("input", paintShadow);
        paintShadow();
    }

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
        drawingStyle,
        shadowFillSlider,
    ].filter(Boolean);
    liveControls.forEach((el) => {
        el.addEventListener("input", () => scheduleGenerate(350));
        el.addEventListener("change", () => scheduleGenerate(250));
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
        colorEndpoints = null;
        ++genSeq;
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => generate({ preview: true }), ms);
    }

    const EXPECTED_MS = {
        preview: { original: 2500, monochrome: 5000, ribbon: 6500, refined: 7000, vibrant: 8000 },
        print: { original: 4000, monochrome: 7000, ribbon: 9000, refined: 8000, vibrant: 11000 },
    };

    let progressClock = null;
    let progressState = null;

    function expectedMs(kind) {
        const style = drawingStyle ? drawingStyle.value : "vibrant";
        const table = EXPECTED_MS[kind] || EXPECTED_MS.preview;
        return table[style] || 8000;
    }

    function paintProgress(label, pct, { indeterminate = false } = {}) {
        liveStatus.classList.add("busy");
        liveText.textContent = label;
        const percent = Math.round(Math.max(0, Math.min(1, pct || 0)) * 100);
        liveBar.hidden = false;
        livePct.hidden = indeterminate;
        liveBar.classList.toggle("indeterminate", indeterminate);
        if (!indeterminate) {
            liveBarFill.style.width = `${percent}%`;
            livePct.textContent = `${percent}%`;
        }
        if (stageProgress) {
            stageProgress.hidden = false;
            stageProgress.classList.toggle("indeterminate", indeterminate);
            stageProgressLabel.textContent = label;
            stageProgressFill.style.width = indeterminate ? "35%" : `${percent}%`;
            stageProgressPct.textContent = indeterminate ? "" : `${percent}%`;
        }
        if (postProgress && !postProgress.hidden) {
            postProgress.classList.toggle("indeterminate", indeterminate);
            postProgressLabel.textContent = label;
            if (indeterminate) {
                postProgressPct.textContent = "";
            } else {
                postProgressFill.style.width = `${percent}%`;
                postProgressPct.textContent = `${percent}%`;
            }
        }
    }

    function setLive(busy, label, pct = null) {
        if (!busy) {
            stopProgressClock();
            liveStatus.classList.remove("busy");
            liveText.textContent = label;
            liveBar.hidden = true;
            livePct.hidden = true;
            liveBar.classList.remove("indeterminate");
            liveBarFill.style.width = "0%";
            if (stageProgress) {
                stageProgress.hidden = true;
                stageProgress.classList.remove("indeterminate");
            }
            return;
        }
        if (progressState) progressState.label = label;
        if (pct != null) {
            if (progressState) {
                progressState.serverPct = Math.max(progressState.serverPct || 0, pct);
                progressState.indeterminate = false;
                progressState.displayPct = Math.max(progressState.displayPct || 0, pct);
            }
            paintProgress(label, progressState ? progressState.displayPct : pct);
        } else {
            if (progressState) progressState.indeterminate = true;
            paintProgress(label, progressState ? progressState.displayPct : 0, { indeterminate: true });
        }
    }

    function startProgressClock(kind, label) {
        stopProgressClock();
        const started = performance.now();
        const expected = expectedMs(kind);
        progressState = { label, serverPct: 0, displayPct: 0, kind, indeterminate: false };
        const tick = () => {
            if (!progressState) return;
            if (progressState.indeterminate) {
                paintProgress(progressState.label, progressState.displayPct || 0, { indeterminate: true });
                return;
            }
            const elapsed = performance.now() - started;
            const clock = 0.92 * (1 - Math.exp(-elapsed / expected));
            progressState.displayPct = Math.max(clock, progressState.serverPct || 0);
            paintProgress(progressState.label, progressState.displayPct);
        };
        tick();
        progressClock = setInterval(tick, 200);
    }

    function stopProgressClock() {
        if (progressClock) clearInterval(progressClock);
        progressClock = null;
        progressState = null;
    }

    function showPostProgress(show) {
        if (!postProgress) return;
        postProgress.hidden = !show;
        postProgress.classList.remove("indeterminate");
        if (show) {
            postProgressFill.style.width = "0%";
            postProgressPct.textContent = "";
            postProgressLabel.textContent = "Feeding the paper…";
        }
    }

    function setPrinting(busy) {
        printing = busy;
        $$(".rail input, .rail select, .preset, #file-input, #download-image-btn, #post-btn, #crop-btn, #change-image-btn, #apply-crop-btn, #cancel-post-btn")
            .forEach(el => { el.disabled = busy; });
    }

    function newJob() {
        if (window.crypto && crypto.randomUUID) return crypto.randomUUID().replace(/-/g, "");
        return Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join("");
    }

    // The server reports how far along the current render is; poll it while a
    // /convert or /api/posts request is in flight so the studio can show the
    // stage ("Striking keys · pass 2 of 4") and a percentage, and, when the
    // machine is busy with someone else's page, how far along that one is.
    function watchProgress(job, fallbackLabel) {
        let stopped = false;
        const tick = async () => {
            if (stopped) return;
            try {
                const resp = await fetch(`/progress/${job}`, { cache: "no-store" });
                if (!resp.ok || stopped) return;
                const info = await resp.json();
                if (stopped) return;
                if (info.stage === "rendering" && info.pct != null) {
                    setLive(true, info.label || fallbackLabel, info.pct);
                } else if (info.busy) {
                    const percent = Math.round((info.busy.pct || 0) * 100);
                    setLive(true, `Another page is printing · ${percent}%`, info.busy.pct);
                } else if (info.stage === "waiting") {
                    setLive(true, "Waiting for the typewriter…", null);
                }
            } catch (_err) {
                // Progress is cosmetic; the main request reports real errors.
            }
        };
        const timer = setInterval(tick, 250);
        tick();
        return { stop() { stopped = true; clearInterval(timer); } };
    }

    async function submitDrawing(url, options, job = null, fallbackLabel = "Typing…") {
        const watcher = job ? watchProgress(job, fallbackLabel) : null;
        try {
            for (let attempt = 0; ; attempt++) {
                const response = await fetch(url, options);
                if (response.status !== 503 || !response.headers.has("Retry-After") || attempt >= 30) return response;
                await response.text();
                setLive(true, "Waiting for the typewriter…");
                await new Promise(resolve => setTimeout(resolve, 2000));
            }
        } finally {
            watcher?.stop();
        }
    }

    // The server draws one page at a time and cannot cancel a render once it has
    // started, so never have more than one request in flight. Changes made while
    // a preview is drawing are coalesced into a single follow-up render.
    let inflight = null;
    let previewDirty = false;

    async function generate({ preview = true, scale = null } = {}) {
        if (!currentFile) return null;
        if (printing) return null;
        if (preview && inflight) {
            previewDirty = true;
            return null;
        }
        if (!preview && inflight) {
            setLive(true, "Finishing the preview…");
            await inflight;
        }
        const run = renderRequest({ preview, scale });
        inflight = run;
        try {
            return await run;
        } finally {
            if (inflight === run) inflight = null;
            if (preview && previewDirty) {
                previewDirty = false;
                scheduleGenerate(0);
            }
        }
    }

    async function renderRequest({ preview, scale }) {
        const savedPreviewEndpoints = colorEndpoints;
        if (!preview) {
            setPrinting(true);
            clearTimeout(debounceTimer);
        }
        abort = new AbortController();
        const seq = ++genSeq;
        colorEndpoints = null;
        const signal = abort.signal;
        const label = preview ? "Typing…" : "Printing…";
        startProgressClock(preview ? "preview" : "print", label);
        setLive(true, label, 0);

        const job = newJob();
        const formData = new FormData();
        appendImage(formData, currentFile);
        appendSettings(formData, scale);
        formData.append("preview", preview ? "1" : "0");
        formData.append("job", job);

        try {
            const resp = await submitDrawing("/convert", {
                method: "POST",
                body: formData,
                signal,
            }, job, label);
            const data = await resp.json();
            if (seq !== genSeq) return null;
            if (!resp.ok) {
                setLive(false, "Jammed");
                toast(data.error || "The machine jammed", "error");
                return null;
            }
            let endpoints = null;
            if (preview && data.color_endpoints?.length === 2) {
                endpoints = await Promise.all(data.color_endpoints.map(async url => {
                    const picture = new Image();
                    picture.src = url;
                    await picture.decode();
                    const canvas = document.createElement("canvas");
                    canvas.width = picture.naturalWidth;
                    canvas.height = picture.naturalHeight;
                    const context = canvas.getContext("2d");
                    context.drawImage(picture, 0, 0);
                    picture.rgba = context.getImageData(0, 0, canvas.width, canvas.height).data;
                    return picture;
                }));
                if (seq !== genSeq) return null;
            }
            currentHtmlData = data.html_data;
            currentTextData = data.text_data;
            currentImageData = data.image_data;

            glyphImage.onload = () => applyZoom(zoomMode);
            glyphImage.src = data.image_data;
            sideGlyph.src = data.image_data;
            colorEndpoints = endpoints;
            paintColor();
            syncDrawingStyle();
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
            if (!preview) {
                setPrinting(false);
                // Reuse the preview endpoints for instant color changes after saving.
                colorEndpoints = savedPreviewEndpoints;
            }
        }
    }

    $("#download-image-btn").addEventListener("click", async () => {
        const scale = parseInt(scaleSlider.value, 10);
        setLive(true, "Printing…");
        const data = await generate({ preview: false, scale });
        if (data && data.image_data) {
            const extension = data.image_data.startsWith("data:image/png") ? "png" : "jpg";
            downloadUrl(data.image_data, `typewriter-drawing.${extension}`);
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
        if (!currentFile || printing) return;
        const confirmBtn = $("#confirm-post-btn");
        confirmBtn.disabled = true;
        clearTimeout(debounceTimer);
        previewDirty = false;
        ++genSeq;
        if (inflight) {
            // Let the current preview finish rather than polling a busy server.
            setLive(true, "Finishing the preview…");
            await inflight;
        }
        setPrinting(true);
        const scale = parseInt(scaleSlider.value, 10);
        let posted = false;
        showPostProgress(true);
        startProgressClock("print", "Printing…");
        setLive(true, "Printing…", 0);
        try {
            const job = newJob();
            const formData = new FormData();
            appendImage(formData, currentFile);
            formData.append("caption", postCaption.value.trim());
            appendSettings(formData, scale);
            formData.append("job", job);
            const resp = await submitDrawing("/api/posts", {
                method: "POST",
                headers: { "X-Requested-With": "fetch" },
                body: formData,
            }, job, "Printing…");
            const raw = await resp.text();
            let data = {};
            try {
                data = raw ? JSON.parse(raw) : {};
            } catch (_err) {
                confirmBtn.disabled = false;
                toast("The press ran out of memory. Try again in a moment.", "error");
                return;
            }
            if (!resp.ok) {
                confirmBtn.disabled = false;
                if (data.login) {
                    window.location.href = window.CARRIAGE.loginUrl;
                    return;
                }
                toast(data.error || "Could not post", "error");
                return;
            }
            posted = true;
            setLive(true, "On the wall", 1);
            postCaption.value = "";
            toast("On the wall");
            setTimeout(() => {
                window.location.href = data.post.url;
            }, 400);
        } catch (err) {
            confirmBtn.disabled = false;
            toast("Could not post: " + err.message, "error");
        } finally {
            if (!posted) {
                confirmBtn.disabled = false;
                setPrinting(false);
                setLive(false, "Live");
                showPostProgress(false);
            }
        }
    });

    $("#download-text-btn").addEventListener("click", () => {
        if (!currentTextData) return;
        const blob = new Blob([currentTextData], { type: "text/plain" });
        const url = URL.createObjectURL(blob);
        downloadUrl(url, "typewriter-drawing.txt");
        URL.revokeObjectURL(url);
    });

    function appendImage(formData, file) {
        const name = (file && file.name) || "photo.jpg";
        formData.append("image", file, name);
    }

    function appendSettings(formData, scale = null) {
        const values = {
            drawing_style: drawingStyle.value,
            color_amount: Number(colorAmountSlider.value) / 100,
            shadow_fill: shadowFillSlider ? Number(shadowFillSlider.value) / 100 : 1,
            columns: columnsSlider.value, charset: charsetSelect.value,
            paper: paperSelect.value, ink: inkSelect.value,
            contrast: contrastSlider.value, detail: detailSlider.value,
            simplify: simplifySlider.value, overstrike: overstrikeSlider.value,
            pressure: pressureSlider.value, wander: wanderSlider.value,
            scale: scale == null ? scaleSlider.value : scale,
            tightness: "0.90", inscription: inscriptionInput.value.trim(),
            invert: invertCheck.checked ? "1" : "0",
        };
        Object.entries(values).forEach(([key, value]) => formData.append(key, String(value)));
    }

    async function fileToDataUrl(file) {
        if (!file) return "";
        try {
            const bitmap = await createImageBitmap(file);
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
