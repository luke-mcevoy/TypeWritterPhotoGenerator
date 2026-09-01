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
