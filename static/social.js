(() => {
    document.querySelectorAll("[data-like]").forEach((btn) => {
        btn.addEventListener("click", async () => {
            if (btn.dataset.needLogin) {
                window.location.href = "/login";
                return;
            }
            const resp = await fetch(`/api/posts/${btn.dataset.like}/like`, { method: "POST" });
            const data = await resp.json();
            if (!resp.ok) {
                if (data.login) window.location.href = "/login";
                return;
            }
            btn.classList.toggle("on", data.liked);
            btn.querySelector(".like-count").textContent = data.like_count;
        });
    });

    document.querySelectorAll("[data-reveal]").forEach((btn) => {
        btn.addEventListener("click", (e) => {
            e.preventDefault();
            const card = btn.closest(".page-card");
            const img = card && card.querySelector("img[data-drawing]");
            if (!img || !img.dataset.photo) return;
            const showingPhoto = img.getAttribute("src") === img.dataset.photo;
            img.src = showingPhoto ? img.dataset.drawing : img.dataset.photo;
            btn.textContent = showingPhoto ? "Photo" : "Drawing";
            btn.classList.toggle("on", !showingPhoto);
        });
    });

    document.querySelectorAll(".post-tabs [data-view]").forEach((btn) => {
        btn.addEventListener("click", () => {
            const view = btn.dataset.view;
            document.querySelectorAll(".post-tabs [data-view]").forEach((b) => {
                b.classList.toggle("active", b === btn);
            });
            document.querySelectorAll(".post-view").forEach((pane) => {
                pane.classList.toggle("active", pane.dataset.view === view);
            });
        });
    });

    const inspect = document.getElementById("inspect");
    if (inspect) {
        const scroller = document.getElementById("inspect-scroll");
        const big = document.getElementById("inspect-img");
        const label = document.getElementById("inspect-label");
        const closeBtn = document.getElementById("inspect-close");

        function open(src, alt, fx, fy) {
            big.src = src;
            big.alt = alt || "";
            inspect.classList.remove("hidden");
            inspect.setAttribute("aria-hidden", "false");
            document.body.style.overflow = "hidden";
            const place = () => {
                // Desktop: 1 image pixel = 1 device pixel, true print grain.
                // Phones: 1 image pixel = 1 CSS pixel so the keys stay legible on retina screens.
                const small = window.matchMedia("(max-width: 860px)").matches;
                const dpr = small ? 1 : (window.devicePixelRatio || 1);
                const w = big.naturalWidth / dpr;
                const h = big.naturalHeight / dpr;
                big.style.width = w + "px";
                big.style.height = h + "px";
                label.textContent = `${big.naturalWidth} × ${big.naturalHeight} · print size · drag to move`;
                const margin = 32;
                scroller.scrollLeft = margin + fx * w - scroller.clientWidth / 2;
                scroller.scrollTop = margin + fy * h - scroller.clientHeight / 2;
            };
            if (big.complete && big.naturalWidth) place();
            else big.onload = place;
        }

        function close() {
            inspect.classList.add("hidden");
            inspect.setAttribute("aria-hidden", "true");
            document.body.style.overflow = "";
            big.removeAttribute("src");
        }

        document.querySelectorAll("img[data-inspect]").forEach((img) => {
            img.addEventListener("click", (e) => {
                const r = img.getBoundingClientRect();
                const fx = r.width ? (e.clientX - r.left) / r.width : 0.5;
                const fy = r.height ? (e.clientY - r.top) / r.height : 0.5;
                open(img.currentSrc || img.src, img.alt, fx, fy);
            });
        });

        closeBtn.addEventListener("click", close);
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape" && !inspect.classList.contains("hidden")) close();
        });

        let drag = null;
        scroller.addEventListener("pointerdown", (e) => {
            if (e.button !== 0 || e.pointerType === "touch") return;
            drag = { x: e.clientX, y: e.clientY, l: scroller.scrollLeft, t: scroller.scrollTop, moved: false };
            scroller.classList.add("dragging");
            scroller.setPointerCapture(e.pointerId);
        });
        scroller.addEventListener("pointermove", (e) => {
            if (!drag) return;
            const dx = e.clientX - drag.x;
            const dy = e.clientY - drag.y;
            if (Math.abs(dx) > 3 || Math.abs(dy) > 3) drag.moved = true;
            scroller.scrollLeft = drag.l - dx;
            scroller.scrollTop = drag.t - dy;
        });
        const endDrag = (e) => {
            if (!drag) return;
            const moved = drag.moved;
            drag = null;
            scroller.classList.remove("dragging");
            if (!moved && e.target === scroller) close();
        };
        scroller.addEventListener("pointerup", endDrag);
        scroller.addEventListener("pointercancel", endDrag);
    }

    document.querySelectorAll("[data-delete]").forEach((btn) => {
        btn.addEventListener("click", async (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (!confirm("Take this page off the wall?")) return;
            const resp = await fetch(`/api/posts/${btn.dataset.delete}`, { method: "DELETE" });
            if (!resp.ok) return;
            const card = btn.closest(".page-card");
            if (card) card.remove();
            else window.location.href = "/";
        });
    });
})();
