# Browser search result highlighter - mod kaiu 2026
# Version 3.4.1b, date: 2026-11-15
# Designed to simplify the editing of fields containing very long text.
# Anki has a known bug where navigating to a field using the Tab key fails to adjust the scroll position to match the cursor's location—a significant issue when dealing with fields that contain a large amount of content. This add-on provides a workaround for that bug. For added convenience, selected text remains highlighted even if you switch to a different system window. On wide screens, the HTML code for a field is displayed on the right, making it easier to compare. All these features can be toggled on or off in the settings.
# The add-on includes a text search function with highlighting; additionally, an option can be enabled in the settings to allow for quick highlighting via a double-click.

# Includes the following add-on:
#   Browser search result highlighter
#   https://github.com/hssm/browser-search-result-highlighter
#   Version 3.4.1

# A portion of the code is taken from this add-on:
#   https://ankiweb.net/shared/info/1920690901



import json

import aqt.browser.browser
from aqt import *
from aqt import mw
from aqt import gui_hooks
from aqt.browser import SearchContext
from aqt.editor import Editor, EditorMode
from aqt.webview import WebContent
from aqt.qt import QTimer
from anki.config import Config
from aqt.addcards import AddCards
import base64


from .utils.parser import parse_search


# Polyfill for FindFlags and UI components across Qt versions
if qtmajor == 6:
    import PyQt6.QtWebEngineCore as webcore
    FIND_BACKWARD = webcore.QWebEnginePage.FindFlag.FindBackward
    FIND_FORWARD = webcore.QWebEnginePage.FindFlag(0)
    MSGBOX_WARNING = QMessageBox.Icon.Warning
    MSGBOX_OK = QMessageBox.StandardButton.Ok
else:
    import PyQt5.QtWebEngineWidgets as webwidgets
    FIND_BACKWARD = webwidgets.QWebEnginePage.FindBackward
    FIND_FORWARD = webwidgets.QWebEnginePage.FindFlags()
    MSGBOX_WARNING = QMessageBox.Warning
    MSGBOX_OK = QMessageBox.Ok
    
    
from aqt.qt import (
    QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy,
    QPushButton, QComboBox, QCompleter, QShortcut,
    QKeySequence, QApplication, Qt
)
   

addonconfig = mw.addonManager.getConfig(__name__)

addon_package = mw.addonManager.addon_from_module(__name__)
default_settings = [
    ('auto', True),
    ('position', 'inline'),
    ('alignment', 'right'),
    ('nofocus', True),
    ('minimap', True),
    # Rely on CSS for defaults
    ('light-background', None),
    ('light-foreground', None),
    ('light-overlap', None),
    ('light-match-position', None),
    ('dark-background', None),
    ('dark-foreground', None),
    ('dark-overlap', None),
    ('dark-match-position', None),
]

class BrowserSearchResultHighlighter:
    def __init__(self, mw):
        self.mw = mw
        self.filter_terms = []

    def editor_init(self, editor):
        if editor.editorMode is EditorMode.BROWSER:
            config = mw.col.get_config('bsrh', {})
            config = self.set_config_defaults(config)
            config = json.dumps(config)
            editor.web.eval(f"addControls({config})")

    def set_config_defaults(self, config):
        for setting, default in default_settings:
            if setting not in config:
                config[setting] = default
        return config

    def browser_will_show(self, browser):
        self.browser = browser
        self.table = browser.table
        self.editor = browser.editor
        self.col = browser.col

    def did_search(self, ctx: SearchContext):
        """Search has happened (regardless of source). Do highlight."""
        self.filter_terms = parse_search(ctx.search)
        # If the global setting to ignore accents in browser search is turned on
        # (i.e. nc: for every term) then we can match its behavior by moving all normal terms
        # to noncomb. Luckily for us, enabling this setting only affects normal search terms
        # (and not re: or front: etc) so solving this problem becomes easy for us.
        if self.col.get_config_bool(Config.Bool.IGNORE_ACCENTS_IN_SEARCH):
            self.filter_terms['noncomb'].extend(self.filter_terms['normal'])
            self.filter_terms['normal'] = []
        #print("bsrh: Highlighting these terms: ", self.filter_terms)


    def on_webview_will_set_content(self, web_content: WebContent, context):
        if not isinstance(context, Editor):
            return
        if not isinstance(context.parentWindow, aqt.browser.browser.Browser):
            return
        web_content.js.append(f"/_addons/{addon_package}/web/editor.js")
        web_content.js.append(f"/_addons/{addon_package}/web/presets.js")
        web_content.css.append(f"/_addons/{addon_package}/web/editor.css")

        highlightingSelectedArea_WhenNotInActiveField = addonconfig.get("highlightingSelectedArea_WhenNotInActiveField", True)
        if highlightingSelectedArea_WhenNotInActiveField:
            web_content.js.append(f"/_addons/{addon_package}/web/highlightingSelectedArea_WhenNotInActiveField.js")
        
        forWideScreenСode_WindowIsOnRight = addonconfig.get("forWideScreenСode_WindowIsOnRight", True)
        if forWideScreenСode_WindowIsOnRight:
            web_content.js.append(f"/_addons/{addon_package}/web/forWideScreenСode_WindowIsOnRight.js")
        
        onceFieldReceivesFocus_ScrollToCursor = addonconfig.get("onceFieldReceivesFocus_ScrollToCursor", True)
        if onceFieldReceivesFocus_ScrollToCursor:
            web_content.js.append(f"/_addons/{addon_package}/web/onceFieldReceivesFocus_ScrollToCursor.js")

    def editor_did_load_note(self, editor, focusTo=None) -> None:
        if editor.editorMode is EditorMode.BROWSER:
            as_str = json.dumps(bsrh.filter_terms)
            as_b64 = base64.b64encode((as_str.encode())).decode()
            editor.web.eval(f"terms_str = '{as_b64}'")
            editor.web.eval(f"parseTerms()")
            editor.web.eval("beginHighlighter()")

    def on_js_message(self, handled, message, context):
        if not message.startswith('BSRH:'):
            return handled
        self.save_config(json.loads(message[5:]))
        return True, None

    def save_config(self, new):
        config = mw.col.get_config('bsrh', dict())
        for (key, _) in default_settings:
            config[key] = new[key]
        mw.col.set_config('bsrh', config)

mw.addonManager.setWebExports(__name__, r"web/.*")
bsrh = BrowserSearchResultHighlighter(mw)
# Hooks
gui_hooks.browser_will_show.append(bsrh.browser_will_show)
gui_hooks.browser_did_search.append(bsrh.did_search)
gui_hooks.webview_will_set_content.append(bsrh.on_webview_will_set_content)
gui_hooks.editor_did_load_note.append(bsrh.editor_did_load_note)
gui_hooks.editor_did_init.append(bsrh.editor_init)
gui_hooks.webview_did_receive_js_message.append(bsrh.on_js_message)



MAX_SEARCH_HISTORY = 25
SEARCH_HISTORY_CONFIG_KEY = "search~History"

class HistoryComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.before_popup = None

    def showPopup(self):
        if self.before_popup:
            self.before_popup()

        super().showPopup()
        
        
class BSPSearchPanel(QWidget):

    def __init__(self, target: AddCards | Editor | AnkiQt):

        if isinstance(target, AddCards):
            super().__init__(target)
            self.parent = target
            self.addcards = target
            self.editor = target.editor

        elif isinstance(target, Editor):
            super().__init__(target.widget)
            self.parent = target
            self.addcards = None
            self.editor = target

        elif isinstance(target, AnkiQt):
            super().__init__(target)
            self.parent = target
            self.addcards = None
            self.editor = target
        else:
            return
            

        self.mw = getattr(target, "mw", target)

        self.cursor_hand = (
            Qt.CursorShape.PointingHandCursor
            if qtmajor == 6 else Qt.PointingHandCursor
        )

        
        
        
        # State Management variables
        self._is_jumping = False
        self._search_chain_remaining = 0
        self._current_search_term = ""

        self.setup_ui()
        
        # self.editor.web.installEventFilter(self)
        
        self.install_web_event_filters()
        
        self.editor.web.findText("") # Сбрасываем поиск при первоначальной загрузке
        self.safe_inject_layout()
        self.hide()

    # ---------------------------------------------------------
    # Search history
    # ---------------------------------------------------------

    def get_search_history(self):
        history = addonconfig.get(SEARCH_HISTORY_CONFIG_KEY, [])

        if not isinstance(history, list):
            return []

        result = []

        for item in history:
            if not isinstance(item, str):
                continue

            item = item.strip()

            if item and item not in result:
                result.append(item)

        return result[:MAX_SEARCH_HISTORY]


    def save_search_history(self, text):
        history = self.get_search_history()
        # Удаляем старую запись, если она уже есть.
        history = [item for item in history if item != text]
        # Перемещаем выбранное значение в начало.
        history.insert(0, text)
        history = history[:MAX_SEARCH_HISTORY]
        addonconfig[SEARCH_HISTORY_CONFIG_KEY] = history
        self.mw.addonManager.writeConfig(__name__, addonconfig)

    def update_search_history(self, text):

        history = self.get_search_history()

        self.search_input.blockSignals(True)
        self.search_line.blockSignals(True)

        try:
            self.search_input.clear()
            self.search_input.addItems(history)

            # Оставляем текущий запрос в поле ввода
            self.search_input.setCurrentText(text)

        finally:
            self.search_line.blockSignals(False)
            self.search_input.blockSignals(False)

    # ---------------------------------------------------------
    # UI
    # ---------------------------------------------------------

    def setup_ui(self):

        self.setObjectName("bspSearchPanel")

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.toolbar_container = QWidget()

        self.toolbar_container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )

        self.toolbar_layout = QHBoxLayout(self.toolbar_container)
        self.toolbar_layout.setContentsMargins(8, 6, 8, 6)
        self.toolbar_layout.setSpacing(8)

        self.setStyleSheet("""
            QWidget#bspSearchPanel {
                border-bottom: 2px solid palette(highlight);
                background-color: palette(window);
            }

            QComboBox#bspInput {
                border: 1px solid palette(mid);
                border-radius: 4px;
                padding: 5px 10px;
                min-width: 120px;
                background-color: palette(base);
                color: palette(text);
                font-size: 13px;
            }

            QComboBox#bspInput:focus {
                border: 1px solid palette(highlight);
            }

            QComboBox#bspInput::drop-down {
                border: 1px solid palette(mid);
                padding-top: 2px;
                padding-right: 2px;
                padding-bottom: 2px;
                width: 20px;
            }

            QComboBox#bspInput QAbstractItemView {
                background-color: palette(base);
                color: palette(text);
                selection-background-color: palette(highlight);
                selection-color: palette(highlighted-text);
                border: 1px solid palette(mid);                
                border-radius: 0px;
                outline: none;
                padding: 3px;
            }
            QComboBox#bspInput QAbstractItemView::item {
                border-radius: 0px;
            }

            QPushButton.bspBtn {
                border: 1px solid palette(mid);
                border-radius: 4px;
                padding: 5px 15px;
                background-color: palette(button);
                color: palette(button-text);
                font-size: 12px;
            }

            QPushButton.bspBtn:hover {
                background-color: palette(light);
            }

            QPushButton.bspBtn:pressed {
                background-color: palette(mid);
            }
        """)

        # -----------------------------------------------------
        # Search ComboBox
        # -----------------------------------------------------

        self.search_input = HistoryComboBox()
        self.search_input.before_popup = self.reload_search_history

        self.search_input.setObjectName("bspInput")
        self.search_input.setEditable(True)

        self.search_input.setInsertPolicy(
            QComboBox.InsertPolicy.NoInsert
            if qtmajor == 6 else QComboBox.NoInsert
        )

        self.search_input.setMaxCount(MAX_SEARCH_HISTORY)

        self.search_input.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        
        self.search_input.activated.connect(self.on_history_selected)        

        # Загружаем историю, но не выбираем ни одну запись.
        self.search_input.addItems(self.get_search_history())
        # При первом открытии поле должно быть пустым.
        self.search_input.setCurrentIndex(-1)
        self.search_input.setEditText("")

        # Получаем внутренний QLineEdit
        self.search_line = self.search_input.lineEdit()

        self.search_line.setPlaceholderText(
            "Search... [Enter or Shift+Enter]"
        )

        # -----------------------------------------------------
        # QCompleter
        # -----------------------------------------------------

        self.completer = QCompleter(
            self.search_input.model(),
            self.search_input
        )
        
        if qtmajor == 6:

            self.completer.setCaseSensitivity(
                Qt.CaseSensitivity.CaseInsensitive
            )

            self.completer.setFilterMode(
                Qt.MatchFlag.MatchContains
            )

            self.completer.setCompletionMode(
                QCompleter.CompletionMode.PopupCompletion
            )

        else:

            self.completer.setCaseSensitivity(
                Qt.CaseInsensitive
            )

            self.completer.setFilterMode(
                Qt.MatchContains
            )

            self.completer.setCompletionMode(
                QCompleter.PopupCompletion
            )


        self.completer.activated.connect(lambda text: self.on_history_text_selected(text))
        
        self.search_input.setCompleter(self.completer)
    
        # -----------------------------------------------------
        # Signals
        # -----------------------------------------------------

        self.search_line.returnPressed.connect(
            self.on_return_pressed
        )

        # Поиск по мере ввода, как и в первоначальном коде
        self.search_line.textChanged.connect(
            lambda t: self.editor.web.findText(t)
        )

        # -----------------------------------------------------
        # Buttons
        # -----------------------------------------------------

        self.btn_next = QPushButton("↓ Next")
        self.btn_next.setProperty("class", "bspBtn")
        self.btn_next.setCursor(self.cursor_hand)
        self.btn_next.clicked.connect(self.find_next)

        self.btn_prev = QPushButton("↑ Prev")
        self.btn_prev.setProperty("class", "bspBtn")
        self.btn_prev.setCursor(self.cursor_hand)
        self.btn_prev.clicked.connect(self.find_prev)

        self.btn_close = QPushButton("✕ Close")
        self.btn_close.setProperty("class", "bspBtn")
        self.btn_close.setCursor(self.cursor_hand)
        self.btn_close.clicked.connect(self.close_search)
        self.btn_close.setToolTip("Close [Shift+Esc]")

        # -----------------------------------------------------
        # Layout
        # -----------------------------------------------------

        self.toolbar_layout.addWidget(self.search_input, 1)
        self.toolbar_layout.addWidget(self.btn_next, 0)
        self.toolbar_layout.addWidget(self.btn_prev, 0)
        self.toolbar_layout.addWidget(self.btn_close, 0)

        self.main_layout.addWidget(self.toolbar_container)

        # -----------------------------------------------------
        # Shortcuts
        # -----------------------------------------------------

        self.shortcut_esc = QShortcut(
            QKeySequence("Shift+Esc"), self
        )

        self.shortcut_esc.activated.connect(
            self.close_search
        )
    

    def reload_search_history(self):
        current_text = self.search_input.currentText()

        history = self.get_search_history()

        self.search_input.blockSignals(True)
        self.search_line.blockSignals(True)

        try:
            self.search_input.clear()
            self.search_input.addItems(history)

            # Восстанавливаем текст, который был введён в поле.
            self.search_input.setCurrentIndex(-1)
            self.search_input.setEditText(current_text)

        finally:
            self.search_line.blockSignals(False)
            self.search_input.blockSignals(False)
            
            
    def _move_history_to_top(self, text):
        self.save_search_history(text)

        # print("[HISTORY AFTER]", self.get_search_history())

        self.update_search_history(text)
        self.search_input.setEditText(text)
        
        
    def on_history_selected(self, index):
        text = self.search_input.itemText(index).strip()

        if not text:
            return

        # print("[HISTORY SELECTED]", index, repr(text))

        self.save_search_history(text)
        self.update_search_history(text)

        # Явно запускаем поиск, даже если текст не изменился.
        self.editor.web.findText(text)


    def on_history_text_selected(self, text):
        text = text.strip()

        if not text:
            return

        self.save_search_history(text)
        self.update_search_history(text)

        # Выбор подсказки QCompleter тоже запускает поиск.
        self.editor.web.findText(text)

    

    # ---------------------------------------------------------
    # Layout injection
    # ---------------------------------------------------------

    def safe_inject_layout(self):

        try:
            target_layout = self.editor.web.parentWidget().layout()

            if isinstance(target_layout, QVBoxLayout):

                idx = target_layout.indexOf(self.editor.web)

                if idx >= 0:
                    target_layout.insertWidget(idx, self)
                    return

            outer_layout = self.editor.widget.layout()

            if isinstance(outer_layout, QVBoxLayout):

                insert_idx = max(0, outer_layout.count() - 1)

                outer_layout.insertWidget(insert_idx, self)
                return

        except Exception:
            self.editor.widget.layout().addWidget(self)

    # ---------------------------------------------------------
    # Search execution
    # ---------------------------------------------------------

    def on_return_pressed(self, *args):

        modifiers = QApplication.keyboardModifiers()

        if modifiers & (
            Qt.KeyboardModifier.ShiftModifier
            if qtmajor == 6 else Qt.ShiftModifier
        ):
            self.find_prev()

        else:
            self.find_next()

    def _run_search(self, backward=False):
        text = self.search_input.currentText().strip()

        if not text:
            return

        # Обновляем историю при каждом запуске поиска,
        # даже если выбрано то же самое значение.
        self.save_search_history(text)
        self.update_search_history(text)

        if backward:
            self.editor.web.findText(
                text,
                QWebEnginePage.FindFlag.FindBackward
            )
        else:
            self.editor.web.findText(text)

    def find_next(self, *args):
        self._run_search(backward=False)

    def find_prev(self, *args):
        self._run_search(backward=True)

    # ---------------------------------------------------------
    # Show / Close
    # ---------------------------------------------------------

    def show_search(self):
        selected_text = self.editor.web.selectedText()
        self.show()
        self.search_input.setFocus()
        if selected_text:
            self.search_input.setCurrentText(selected_text)
            self.save_search_history(selected_text)
            self.update_search_history(selected_text)
        else:
            current_text = self.search_input.currentText()
            self.search_input.setCurrentText(current_text)
            self.search_line.selectAll()

    def close_search(self):
        self.hide()
        self.search_input.setCurrentText("")
        self.editor.web.findText("")
        self.editor.web.setFocus()
        
    

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonDblClick:
            web = self.editor.web
            if obj == web or web.isAncestorOf(obj):
                searchOnDoubleClick = addonconfig.get("searchOnDoubleClick", False) 
                searchOnDoubleClick_WhenSearchPanelIsOpen = addonconfig.get("searchOnDoubleClick_WhenSearchPanelIsOpen", False)
                if searchOnDoubleClick_WhenSearchPanelIsOpen and self.isHidden():
                    return False
                if searchOnDoubleClick or searchOnDoubleClick_WhenSearchPanelIsOpen:
                    # Даём странице завершить выделение слова.
                    QTimer.singleShot(50, self.search_selected_word)

        return False      
     
    
    def install_web_event_filters(self):
        web = self.editor.web

        # Сам WebView.
        web.installEventFilter(self)

        # Внутренний виджет, которому может доставляться событие.
        focus_proxy = web.focusProxy()
        if focus_proxy:
            focus_proxy.installEventFilter(self)

        # Все уже созданные дочерние виджеты WebView.
        for child in web.findChildren(QWidget):
            child.installEventFilter(self)
     

    def search_selected_word(self):
        selected_text = self.editor.web.selectedText().strip()

        if not selected_text:
            return

        self.save_search_history(selected_text)
        self.update_search_history(selected_text)

        self.editor.web.findText(selected_text)


# -------------------------------------------------------------
# Add button
# -------------------------------------------------------------

def add_bsp_search_button(buttons, editor):

    def toggle_search(*args):
        editor.bsp_search_panel.show_search()

    shortcutOpen = addonconfig.get(
        "searchBarOpenBrowser",
        "Alt+Shift+F"
    )

    btn = editor.addButton(
        icon="",
        cmd="bsp_browser_search_add",
        func=toggle_search,
        tip=f"Search [{shortcutOpen}] - Browser search result highlighter - mod kaiu 2026",
        keys=f"{shortcutOpen}",
        label="🔍"
    )

    buttons.append(btn)

    return buttons
    


def setup_bsp_search(editor):
    bsp = BSPSearchPanel(editor)
    editor.bsp_search_panel = bsp
    
def add_cards_setup_bsp_search(addcards: AddCards) -> None:
    bsp = BSPSearchPanel(addcards)
    addcards.bsp_search_panel = bsp
    layout = addcards.form.verticalLayout_3
    layout.insertWidget(layout.count() - 1, bsp)
    
def review_setup_bsp_search():
    bsp = BSPSearchPanel(mw)
    mw.bsp_search_panel = bsp
    mw.setStyleSheet("border: none;")
    mw.mainLayout.addWidget(bsp)
    shortcutOpen = addonconfig.get("searchBarOpen", "Alt+Shift+F") 
    shortcut = QShortcut(QKeySequence(f"{shortcutOpen}"), mw)
    shortcut.activated.connect(lambda: bsp.show_search())


gui_hooks.editor_did_init.append(setup_bsp_search)
gui_hooks.editor_did_init_buttons.append(add_bsp_search_button)
gui_hooks.add_cards_did_init.append(add_cards_setup_bsp_search)
gui_hooks.main_window_did_init.append(review_setup_bsp_search)