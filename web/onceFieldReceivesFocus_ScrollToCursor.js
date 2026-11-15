/* restoring scroll position for Anki */
(() => {	    

	function scrollToActiveCaret(event) {
		const target = event.target;

        requestAnimationFrame(() => {

            const area = document.querySelector(".scroll-area");
            if (!area) return;

            let caretTop;
            let caretBottom;
            let cursorInfo = {};

            // CodeMirror
            if (target.tagName === "TEXTAREA") {
                const cm = target.closest(".CodeMirror");
                if (!cm?.CodeMirror) return;

                const editor = cm.CodeMirror;
                const pos = editor.getCursor();
                const coords = editor.cursorCoords(pos, "local");
                const cmRect = cm.getBoundingClientRect();

                caretTop = cmRect.top + coords.top;
                caretBottom = cmRect.top + coords.bottom;

                cursorInfo = {
                    editor: "CodeMirror",
                    line: pos.line,
                    ch: pos.ch
                };

            // Rich-text
            } else {
                const host = target.closest(".rich-text-editable");
                if (!host || !host.shadowRoot) return;

                const shadow = host.shadowRoot;
                const selection = shadow.getSelection();

                if (!selection || !selection.focusNode) return;

                const range = document.createRange();
                range.setStart(selection.focusNode, selection.focusOffset);
                range.collapse(true);

                const caret = range.getBoundingClientRect();

                if (!caret.height) return;

                caretTop = caret.top;
                caretBottom = caret.bottom;

                cursorInfo = {
                    editor: "Rich-text",
                    focusOffset: selection.focusOffset
                };
            }

            // General scrolling
            const areaRect = area.getBoundingClientRect();

            let delta = 0;

            if (caretTop < areaRect.top) {
                delta = caretTop - areaRect.top - 20;
            } else if (caretBottom > areaRect.bottom) {
                delta = caretBottom - areaRect.bottom + 20;
            }

            if (delta !== 0) {
                area.scrollTop += delta;
            }

        });	
	}
	
    document.addEventListener("focusin", (event) => {
		scrollToActiveCaret(event);
    }, true);
    
})();