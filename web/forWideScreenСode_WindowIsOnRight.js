/* code editor on the right if the screen is wide */
(() => {
    const style = document.createElement("style");
    style.id = "test-code-editor-layout";
    style.textContent = `
        /* code editor on the right if the screen is wide */
        @media (min-width: 800px) {
            .editing-area {
                display: inline-flex !important;
                width: 100%;
            }

            .editing-area .collapsible {
                width: 100%;
            }

            .editing-area div:nth-child(1).collapsible:not(:has(+ .collapsible.hidden)) {
                width: 50%;
            }

            .editing-area div:nth-child(2).collapsible:not(.hidden) {
                width: 50%;
            }
        }
    `;

    document.getElementById(style.id)?.remove();
    document.head.appendChild(style);
})();