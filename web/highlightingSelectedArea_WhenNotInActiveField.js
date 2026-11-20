/* ===================================================== */
/* Constant highlighting of selected text Rich-text fields */
/* ===================================================== */
(() => {

    // If the code has already been run, disable the previous handlers.
    window.__ankiRichSelectionController?.abort();

    // We remove the lights from the previous installation.
    for (const name of window.__ankiRichSelectionNames || []) {
        CSS.highlights.delete(name);
    }

    const controller = new AbortController();
    window.__ankiRichSelectionController = controller;

    const savedSelections  = new WeakMap();
    const fieldIds         = new WeakMap();
    const restoreTimers    = new WeakMap();
    const mouseupTimers    = new WeakMap();
    const clearTimers      = new WeakMap();

    const highlightPrefix = "anki-rich-selection-";
    const highlightNames  = [];
    window.__ankiRichSelectionNames = highlightNames;

    let nextFieldId     = 0;
    let nextHighlightId = 0;

    const STYLE_ID = "persistent-selection-style";


    /* ----------------------------------------------------- */
    /* Utilities */
    /* ----------------------------------------------------- */

    function getFieldId(host) {
        if (!host || typeof host !== "object") return null;

        if (!fieldIds.has(host)) {
            fieldIds.set(host, ++nextFieldId);

            // console.log("[NEW HOST]", {
            //     fieldId: nextFieldId,
            //     host,
            //     isConnected: host.isConnected,
            // });
        }

        return fieldIds.get(host);
    }


    function getPath(node, root) {
        const path = [];

        while (node && node !== root) {
            const parent = node.parentNode;
            if (!parent) return null;

            path.unshift(
                Array.prototype.indexOf.call(parent.childNodes, node)
            );
            node = parent;
        }

        return node === root ? path : null;
    }


    function getNode(root, path) {
        let node = root;
        for (const index of path || []) {
            node = node?.childNodes[index];
            if (!node) return null;
        }
        return node;
    }


    function normalizeText(text) {
        return text.replace(/\r?\n/g, "");
    }


    function getEditable(host) {
        return host?.shadowRoot?.querySelector("anki-editable") || null;
    }


    /* ----------------------------------------------------- */
    /* Search Range by text (fallback when DOM is rebuilt) */
    /* ----------------------------------------------------- */

    function findRangeByText(editable, saved) {
        const fullText = editable.textContent;
        const needle   = saved.text;
        if (!needle) return null;

        const first = fullText.indexOf(needle);
        if (first === -1) return null;

        const second = fullText.indexOf(needle, first + 1);
        if (second !== -1) {
            // console.log("[RESTORE AMBIGUOUS TEXT]", { needle });
            return null;
        }

        const walker = document.createTreeWalker(editable, NodeFilter.SHOW_TEXT);

        let pos = 0;
        let startNode = null, startOffset = 0;
        let endNode   = null, endOffset   = 0;
        let node;

        while ((node = walker.nextNode())) {
            const len       = node.data.length;
            const nodeStart = pos;
            const nodeEnd   = pos + len;

            if (startNode === null && first >= nodeStart && first < nodeEnd) {
                startNode   = node;
                startOffset = first - nodeStart;
            }

            if (
                endNode === null &&
                first + needle.length > nodeStart &&
                first + needle.length <= nodeEnd
            ) {
                endNode   = node;
                endOffset = first + needle.length - nodeStart;
                break;
            }

            pos = nodeEnd;
        }

        if (!startNode || !endNode) return null;

        const range = document.createRange();
        range.setStart(startNode, startOffset);
        range.setEnd(endNode, endOffset);

        if (range.toString() !== needle) return null;
        return range;
    }


    /* ----------------------------------------------------- */
    /* Backlight style in shadow root                        */
    /* ----------------------------------------------------- */
    
    function ensureHighlightStyle(shadow, highlightName) {
        let style = shadow.querySelector(`#${STYLE_ID}`);
        if (!style) {
            style = document.createElement("style");
            style.id = STYLE_ID;
            shadow.appendChild(style);
        }

        const rule = `::highlight(${highlightName})`;
        if (!style.textContent.includes(rule)) {
            style.textContent += `
                ${rule} {
                    background: #bdffff;
                }
            `;
        }
    }


    /* ----------------------------------------------------- */
    /* Backlight restoration                              */
    /* ----------------------------------------------------- */    

    function restoreHighlight(host, saved) {
        const shadow   = host.shadowRoot;
        const editable = getEditable(host);
        if (!editable) return;

        const startNode = getNode(editable, saved.startPath);
        const endNode   = getNode(editable, saved.endPath);

        let range = null;

        if (startNode && endNode) {
            try {
                range = document.createRange();
                range.setStart(startNode, saved.startOffset);
                range.setEnd(endNode, saved.endOffset);
            } catch (e) {
                // console.log("[RESTORE FAILED: RANGE BUILD]", {
                //     fieldId: getFieldId(host),
                //     error: String(e),
                // });
                range = null;
            }
        } else {
            // console.log("[RESTORE FALLBACK: TEXT SEARCH]", {
            //     fieldId: getFieldId(host),
            //     text: saved.text,
            // });
            range = findRangeByText(editable, saved);
        }

        if (!range) {
            // console.log("[RESTORE FAILED: NODES+SEARCH]", {
            //     fieldId: getFieldId(host),
            // });
            return;
        }

        try {
            const restoredText = range.toString();

            if (
                normalizeText(restoredText) !== normalizeText(saved.text) ||
                !restoredText
            ) {
                // console.log("[RESTORE FAILED: TEXT]", {
                //     fieldId: getFieldId(host),
                //     saved: JSON.stringify(saved.text),
                //     restored: JSON.stringify(restoredText),
                // });
                return;
            }

            ensureHighlightStyle(shadow, saved.highlightName);

            // Forced reflow.
            void editable.offsetHeight;

            CSS.highlights.set(saved.highlightName, new Highlight(range));

            // Forced redraw: remove and reinstall
            //in the next frame (fixes the Electron bug with repaint in the Shadow DOM).
            const name = saved.highlightName;
            requestAnimationFrame(() => {
                const hl = CSS.highlights.get(name);
                if (hl) {
                    CSS.highlights.delete(name);
                    CSS.highlights.set(name, hl);
                }
            });

            // console.log("[RESTORE SUCCESS]", {
            //     fieldId: getFieldId(host),
            //     name: saved.highlightName,
            //     text: saved.text,
            // });

        } catch (error) {
            console.error("[RICH-TEXT HIGHLIGHT ERROR]", error);
        }
    }


    /* ----------------------------------------------------- */
    /* Centralized selection saving                 */
    /* ----------------------------------------------------- */

    function commitSelectionForHost(host, reason = "unknown") {
        if (!host?.isConnected || !host.shadowRoot) return;

        const shadow = host.shadowRoot;
        const editable = getEditable(host);
        if (!editable) return;

        const selection = shadow.getSelection?.();
        if (!selection) return;

        // Empty selection -clear the highlight.
        if (selection.isCollapsed || selection.rangeCount === 0) {
            const oldSaved = savedSelections.get(host);
            if (oldSaved) {
                CSS.highlights.delete(oldSaved.highlightName);
                savedSelections.delete(host);
                // console.log("[SELECTION CLEARED]", {
                //     fieldId: getFieldId(host),
                //     reason,
                // });
            }
            return;
        }

        const range = selection.getRangeAt(0);

        // We check that both ends of the selection are inside the editable field.
        const startPath = getPath(range.startContainer, editable);
        const endPath   = getPath(range.endContainer,   editable);
        if (startPath === null || endPath === null) return;

        let saved = savedSelections.get(host);

        const newText = selection.toString();
        if (!newText) return;

        // There is nothing to save if the selection has not changed.
        if (saved) {
            const same =
                saved.text === newText &&
                saved.startOffset === range.startOffset &&
                saved.endOffset === range.endOffset &&
                JSON.stringify(saved.startPath) === JSON.stringify(startPath) &&
                JSON.stringify(saved.endPath) === JSON.stringify(endPath);
            if (same) return;
        }

        if (!saved) {
            const highlightName = highlightPrefix + (++nextHighlightId);
            saved = { highlightName };
            highlightNames.push(highlightName);
        }

        saved.startPath   = startPath;
        saved.startOffset = range.startOffset;
        saved.endPath     = endPath;
        saved.endOffset   = range.endOffset;
        saved.text        = newText;

        savedSelections.set(host, saved);

        // We remove the old backlight -the new one will be restored
        //when focusin/blur/next restoreHighlight.
        CSS.highlights.delete(saved.highlightName);

        // console.log("[SELECTION COMMITTED]", {
        //     fieldId: getFieldId(host),
        //     text: saved.text,
        //     reason,
        // });
    }


    /* ----------------------------------------------------- */
    /* Mouseup: saving after releasing the mouse */
    /*(with double/triple click protection) */
    /* ----------------------------------------------------- */

    document.addEventListener("mouseup", (event) => {
		const eventPath = event.composedPath();

		const host = eventPath.find(node =>
			node instanceof Element &&
			node.matches(".rich-text-editable")
		) || event.target.closest?.(".rich-text-editable");

		if (!host || !host.shadowRoot) return;

		const editable = getEditable(host);
		if (!editable) return;

		// IMPORTANT: checking through editable.contains, and not through instanceof+matches,
		//because inside shadow root nodes belong to another realm
		//and do not pass instanceof Element.		
		const isInsideEditable = eventPath.some(node =>
			node === editable ||
			(node?.nodeType && editable.contains(node))
		);

		clearTimeout(mouseupTimers.get(host));

		const isTrusted = event.isTrusted;
		const button    = event.button;
		const detail    = event.detail;

		const timer = setTimeout(() => {
			if (mouseupTimers.get(host) === timer) {
				mouseupTimers.delete(host);
			}

			if (!host.isConnected || !host.shadowRoot) return;

			const selection = host.shadowRoot.getSelection?.();

			// Collapse with a regular left-click inside an editable -
			//remove the highlight (normal behavior).
			//detail === 0 -not a single click (software mouseup, drag, etc.),
			//detail === 2/3 -double/triple click, selection
			//can be collapsed in between, don't touch it.
			if (!selection || selection.isCollapsed) {
				const isSingleClick =
					isTrusted &&
					button === 0 &&
					detail === 1 &&
					isInsideEditable;

				if (!isSingleClick) return;

				const oldSaved = savedSelections.get(host);
				if (oldSaved) {
					CSS.highlights.delete(oldSaved.highlightName);
					savedSelections.delete(host);
					// console.log("[SAVED SELECTION DELETE]", {
					// 	fieldId: getFieldId(host),
					// });
				}
				return;
			}

			commitSelectionForHost(host, "mouseup");
		}, 100);

		mouseupTimers.set(host, timer);

	}, {
		capture: true,
		signal: controller.signal,
	});


    /* ----------------------------------------------------- */
    /* selectionchange inside shadow root                   */
    /* ----------------------------------------------------- */

    let lastSelectionSnapshot = new WeakMap();

    function snapshotSelection(host) {
        const shadow = host.shadowRoot;
        const sel = shadow?.getSelection?.();
        if (!sel || sel.isCollapsed || sel.rangeCount === 0) {
            return { collapsed: true };
        }
        const r = sel.getRangeAt(0);
        return {
            collapsed: false,
            startNode: r.startContainer,
            startOffset: r.startOffset,
            endNode: r.endContainer,
            endOffset: r.endOffset,
            text: r.toString(),
        };
    }

    function snapshotEqual(a, b) {
        if (!a || !b) return false;
        if (a.collapsed !== b.collapsed) return false;
        if (a.collapsed) return true;
        return (
            a.startNode === b.startNode &&
            a.startOffset === b.startOffset &&
            a.endNode === b.endNode &&
            a.endOffset === b.endOffset &&
            a.text === b.text
        );
    }

    function onSelectionChange(host) {
        const current = snapshotSelection(host);
        const prev    = lastSelectionSnapshot.get(host);
        lastSelectionSnapshot.set(host, current);

        if (snapshotEqual(prev, current)) return;

        if (current.collapsed) {
            // Debounce -so that double/triple clicks do not reset the backlight.
            clearTimeout(clearTimers.get(host));
            const timer = setTimeout(() => {
                clearTimers.delete(host);
                if (!host.isConnected) return;

                const now = snapshotSelection(host);
                if (now.collapsed) {
                    commitSelectionForHost(host, "selectionchange-collapsed");
                }
            }, 80);
            clearTimers.set(host, timer);
            return;
        }

        //Non-empty allocation -commit immediately, but with protection from “intermediate”
        //double-click states (the word is first highlighted there, then
        //nothing changes -everything is ok here).
        commitSelectionForHost(host, "selectionchange");
    }

    function attachShadowSelectionListeners() {
        for (const host of document.querySelectorAll(".rich-text-editable")) {
            const shadow = host.shadowRoot;
            if (!shadow || shadow.__ankiSelListener) continue;
            shadow.__ankiSelListener = true;

            shadow.addEventListener("selectionchange", () => {
                onSelectionChange(host);
            }, { signal: controller.signal });
        }
    }

    // We are picking up new fields.
    const fieldObserver = new MutationObserver(() => {
        attachShadowSelectionListeners();
    });
    fieldObserver.observe(document.body, { childList: true, subtree: true });
    controller.signal.addEventListener("abort", () => fieldObserver.disconnect());

    attachShadowSelectionListeners();


    /* ----------------------------------------------------- */
    /* keyup: Shift+arrows, Shift+Home/End, Ctrl+A, etc.   */
    /*(insurance in case selectionchange doesn’t work) */
    /* ----------------------------------------------------- */

    document.addEventListener("keyup", (event) => {
        const host = event.composedPath().find(node =>
            node instanceof Element &&
            node.matches(".rich-text-editable")
        );
        if (!host) return;

        // We are only interested in the “highlight” keys.
        const relevant =
            event.shiftKey ||
			event.key === "Shift" ||
			event.key === "ArrowLeft" ||
			event.key === "ArrowRight" ||            
			event.key === "ArrowUp" ||
            event.key === "ArrowDown" ||
            event.key === "Home" ||
            event.key === "End" ||
            event.key === "PageUp" ||
            event.key === "PageDown" ||
            (event.ctrlKey && (event.key === "a" || event.key === "A"));

        if (!relevant) return;

        // A slight delay in case the browser has not yet updated selection.
        setTimeout(() => {
            if (!host.isConnected) return;
            commitSelectionForHost(host, "keyup");
        }, 0);

    }, {
        capture: true,
        signal: controller.signal,
    });


    /* ----------------------------------------------------- */
    /* Restoring highlights when switching fields       */
    /* ----------------------------------------------------- */

    document.addEventListener("focusin", () => {
        document.querySelectorAll(".rich-text-editable").forEach((host) => {
            const saved = savedSelections.get(host);
            if (!saved) return;

            // Give Anki time to rebuild the DOM after losing focus.
            clearTimeout(restoreTimers.get(host));
            const timer = setTimeout(() => {
                if (!host.isConnected) return;

                // If the focus is again inside this field and the selection is alive -
                //restoration is not necessary, but there will be no harm.
                restoreHighlight(host, saved);
                restoreTimers.delete(host);
            }, 250);
            restoreTimers.set(host, timer);
        });

    }, {
        capture: true,
        signal: controller.signal,
    });


    /* ----------------------------------------------------- */
    /* Recovering from Anki Window Loss of Focus           */  
    /* ----------------------------------------------------- */  

    window.addEventListener("blur", () => {
        document.querySelectorAll(".rich-text-editable").forEach((host) => {
            const saved = savedSelections.get(host);
            if (!saved) return;

            restoreHighlight(host, saved);
        });
    }, {
        signal: controller.signal,
    });



})();




/* ========================================== */
/* constant highlighting of highlighted code  */
/* ========================================== */

(() => {
    const editors = new WeakMap();

    // Normal Highlight CSS CodeMirror
    const style = document.createElement("style");
    style.id = "codemirror-selection-style";

    style.textContent = `
        .CodeMirror .CodeMirror-selected {
            /* background: #3367d188 !important; */
			background: #ffffa1 !important;
						
        }

        .CodeMirror .my-saved-selection {
            /* background: #3367d155 !important; */
			background: #bdffff !important; 
        }
    `;

    document.getElementById(style.id)?.remove();
    document.head.appendChild(style);

    document.addEventListener("focusin", (event) => {
        if (event.target.tagName !== "TEXTAREA") return;

        const cm = event.target.closest(".CodeMirror");
        if (!cm?.CodeMirror) return;

        let state = editors.get(cm);

        // First entry into this editor
        if (!state) {
            state = {
                selection: null,
                mark: null
            };

            editors.set(cm, state);

            // Maintaining the selection after releasing the mouse
            cm.addEventListener("mouseup", () => {
                requestAnimationFrame(() => {
                    const s = cm.CodeMirror.listSelections()[0];

                    if (!s || s.empty()) {
                        state.selection = null;
                        return;
                    }

                    state.selection = {
                        from: { ...s.from() },
                        to: { ...s.to() }
                    };

                    // console.log("[SELECTION SAVED]", {
                    //     text: cm.CodeMirror.getRange(
                    //         state.selection.from,
                    //         state.selection.to
                    //     )
                    // });
                });
            });

            // Restoring the backlight after losing focus
            cm.addEventListener("focusout", () => {
                setTimeout(() => {
                    if (!state.selection) return;

                    if (state.mark) {
                        state.mark.clear();
                    }

                    state.mark = cm.CodeMirror.markText(
                        state.selection.from,
                        state.selection.to,
                        {
                            className: "my-saved-selection"
                        }
                    );

                    // console.log("[SELECTION RESTORED]", {
                    //     text: cm.CodeMirror.getRange(
                    //         state.selection.from,
                    //         state.selection.to
                    //     )
                    // });
                }, 100);
            });

            // console.log("[CODEMIRROR ATTACHED]", cm);
        }

        // The editor has received focus again -remove the old mark
        if (state.mark) {
            state.mark.clear();
            state.mark = null;
        }

    }, true);

    
})();