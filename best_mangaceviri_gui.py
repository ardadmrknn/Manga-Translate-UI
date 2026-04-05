import json
import os
import threading
import tkinter as tk
from datetime import datetime
from tkinter import BooleanVar, StringVar, filedialog, messagebox, scrolledtext, ttk

from PIL import ImageTk

try:
    import keyboard
except ImportError:
    keyboard = None

from best_mangaceviri import DEFAULT_LOCAL_GEMMA_MODEL_PATH, ScreenTranslator


APP_THEME = {
    "bg": "#f5f1e8",
    "surface": "#fffaf2",
    "panel": "#f0e7d8",
    "panel_alt": "#e8dcc8",
    "accent": "#0f766e",
    "accent_alt": "#155e75",
    "accent_soft": "#d7efe9",
    "text": "#1f2937",
    "muted": "#6b7280",
    "border": "#d5c4ae",
    "success": "#166534",
    "warning": "#b45309",
    "danger": "#b91c1c",
}

LANGUAGE_OPTIONS = ["English", "Japanese", "Korean", "Chinese", "Spanish", "French"]
TARGET_LANGUAGE_OPTIONS = [
    "Turkish",
    "English",
    "Spanish",
    "French",
    "German",
    "Italian",
    "Portuguese",
    "Russian",
    "Arabic",
]
PREPROCESSING_LABELS = {
    "normal": "Normal",
    "denoise": "Gürültü Azalt",
    "sharpen": "Keskinleştir",
    "high_contrast": "Yüksek Kontrast",
}
PREPROCESSING_DISPLAY = list(PREPROCESSING_LABELS.values())
PREPROCESSING_REVERSE = {value: key for key, value in PREPROCESSING_LABELS.items()}


def merge_nested_dicts(base, incoming):
    result = json.loads(json.dumps(base))
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_nested_dicts(result[key], value)
        else:
            result[key] = value
    return result


class SettingsManager:
    def __init__(self, settings_file="settings.json"):
        self.settings_file = settings_file
        self.defaults = {
            "theme": "linen",
            "hotkeys": {
                "translate": "<F1>",
                "select_area": "<F2>",
                "history": "<F3>",
                "toggle_persistent_border": "<F4>",
                "overlay": "<F5>",
                "close_overlay": "<Delete>",
            },
            "last_coords": {
                "left": "575",
                "top": "150",
                "width": "750",
                "height": "850",
            },
            "last_langs": {
                "source": "English",
                "target": "Turkish",
            },
            "last_engines": {
                "ocr": "cloud_vision",
                "translator": "local_gemma",
                "gemini_quality": "normal",
                "preprocessing_profile": "normal",
            },
            "local_model": {
                "path": DEFAULT_LOCAL_GEMMA_MODEL_PATH,
            },
            "auto_translate": False,
            "layout_mode": "game",
            "window_geometry": "1240x860+80+80",
            "show_border": True,
        }
        self.settings = self.load_settings()

    def load_settings(self):
        if not os.path.exists(self.settings_file):
            self.save_settings(self.defaults)
            return merge_nested_dicts(self.defaults, {})
        try:
            with open(self.settings_file, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            return merge_nested_dicts(self.defaults, loaded)
        except (OSError, json.JSONDecodeError):
            return merge_nested_dicts(self.defaults, {})

    def save_settings(self, settings):
        self.settings = merge_nested_dicts(self.defaults, settings)
        with open(self.settings_file, "w", encoding="utf-8") as handle:
            json.dump(self.settings, handle, ensure_ascii=False, indent=4)

    def get(self, key):
        return self.settings.get(key, self.defaults.get(key))


class ScrollableFrame(tk.Frame):
    def __init__(self, parent, bg_color, *args, **kwargs):
        super().__init__(parent, bg=bg_color, *args, **kwargs)
        self.canvas = tk.Canvas(self, bg=bg_color, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=bg_color)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.window_id = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.window_id, width=e.width)
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        try:
            x, y = self.canvas.winfo_pointerxy()
            widget = self.canvas.winfo_containing(x, y)
            if widget and str(widget).startswith(str(self)):
                # Ensure the scrollable text widget doesn't get captured by this if we are scrolling over it
                if not isinstance(widget, tk.Text):
                    self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        except tk.TclError:
            pass

class CardFrame(tk.Frame):
    def __init__(self, parent, title, subtitle=None, **kwargs):
        super().__init__(parent, bg=APP_THEME["surface"], highlightthickness=1, highlightbackground=APP_THEME["border"], **kwargs)
        header = tk.Frame(self, bg=APP_THEME["surface"])
        header.pack(fill=tk.X, padx=18, pady=(16, 10))
        tk.Label(header, text=title, bg=APP_THEME["surface"], fg=APP_THEME["text"], font=("Segoe UI Semibold", 12)).pack(anchor="w")
        if subtitle:
            tk.Label(header, text=subtitle, bg=APP_THEME["surface"], fg=APP_THEME["muted"], font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 0))
        self.body = tk.Frame(self, bg=APP_THEME["surface"])
        self.body.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 18))


class StatusPill(tk.Label):
    def __init__(self, parent, text, bg_color, fg_color=None):
        super().__init__(parent, text=text, bg=bg_color, fg=fg_color or APP_THEME["text"], font=("Segoe UI Semibold", 9), padx=12, pady=6)


class ModernSettingsWindow(tk.Toplevel):
    def __init__(self, parent_gui):
        super().__init__(parent_gui.root)
        self.parent_gui = parent_gui
        self.settings_manager = parent_gui.settings_manager
        self.hotkey_vars = {}

        self.title("Ayarlar")
        self.geometry("560x470")
        self.minsize(500, 420)
        self.transient(parent_gui.root)
        self.grab_set()
        self.configure(bg=APP_THEME["bg"])

        self.build_ui()

    def build_ui(self):
        shell = tk.Frame(self, bg=APP_THEME["bg"])
        shell.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)

        tk.Label(shell, text="Uygulama Ayarları", bg=APP_THEME["bg"], fg=APP_THEME["text"], font=("Segoe UI Semibold", 17)).pack(anchor="w")
        lbl = tk.Label(shell, text="Kısayolları ve varsayılan davranışı buradan yönetebilirsiniz.", bg=APP_THEME["bg"], fg=APP_THEME["muted"], font=("Segoe UI", 10), justify=tk.LEFT)
        lbl.pack(anchor="w", fill=tk.X, expand=True, pady=(4, 14))
        lbl.bind("<Configure>", lambda e, l=lbl: l.configure(wraplength=e.width))

        hotkeys_card = CardFrame(shell, "Global Kısayollar", "Tuş kutusuna odaklanıp yeni kombinasyonu basın.")
        hotkeys_card.pack(fill=tk.X)

        labels = {
            "translate": "Çeviri başlat",
            "select_area": "Alan seç",
            "history": "Geçmişi aç",
            "toggle_persistent_border": "Çerçeveyi aç veya kapat",
            "overlay": "Overlay çeviri",
            "close_overlay": "Overlay kapat",
        }

        for row, action in enumerate(self.settings_manager.defaults["hotkeys"]):
            frame = tk.Frame(hotkeys_card.body, bg=APP_THEME["surface"])
            frame.grid(row=row, column=0, sticky="ew", pady=4)
            frame.columnconfigure(1, weight=1)
            tk.Label(frame, text=labels[action], bg=APP_THEME["surface"], fg=APP_THEME["text"], font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w", padx=(0, 12))
            variable = StringVar(value=self.settings_manager.get("hotkeys").get(action, self.settings_manager.defaults["hotkeys"][action]))
            entry = tk.Entry(frame, textvariable=variable, relief=tk.FLAT, bg=APP_THEME["panel"], fg=APP_THEME["text"], insertbackground=APP_THEME["text"], font=("Consolas", 10))
            entry.grid(row=0, column=1, sticky="ew", ipady=7)
            entry.bind("<KeyRelease>", lambda event, var=variable: self.capture_hotkey(event, var))
            self.hotkey_vars[action] = variable

        options_card = CardFrame(shell, "Davranış", "Küçük ama etkili kolaylık ayarları.")
        options_card.pack(fill=tk.X, pady=(14, 0))
        self.auto_translate_var = BooleanVar(value=self.parent_gui.auto_translate_var.get())
        self.show_border_var = BooleanVar(value=self.parent_gui.show_persistent_border_var.get())
        tk.Checkbutton(options_card.body, text="Alan seçiminden sonra otomatik çevir", variable=self.auto_translate_var, bg=APP_THEME["surface"], fg=APP_THEME["text"], activebackground=APP_THEME["surface"], selectcolor=APP_THEME["surface"], font=("Segoe UI", 10)).pack(anchor="w")
        tk.Checkbutton(options_card.body, text="Başlangıçta sürekli çerçeveyi açık tut", variable=self.show_border_var, bg=APP_THEME["surface"], fg=APP_THEME["text"], activebackground=APP_THEME["surface"], selectcolor=APP_THEME["surface"], font=("Segoe UI", 10)).pack(anchor="w", pady=(8, 0))

        footer = tk.Frame(shell, bg=APP_THEME["bg"])
        footer.pack(fill=tk.X, pady=(16, 0))
        ttk.Button(footer, text="İptal", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(footer, text="Kaydet", command=self.save).pack(side=tk.RIGHT, padx=(0, 8))

    def capture_hotkey(self, event, variable):
        event.widget.delete(0, tk.END)
        key_symbol = event.keysym
        if key_symbol in {"Control_L", "Control_R", "Alt_L", "Alt_R", "Shift_L", "Shift_R"}:
            return
        modifiers = []
        if event.state & 0x4:
            modifiers.append("Control")
        if event.state & 0x8:
            modifiers.append("Alt")
        if event.state & 0x1:
            modifiers.append("Shift")
        modifiers.append(key_symbol)
        variable.set(f"<{'-'.join(modifiers)}>")
        self.parent_gui.root.focus_set()

    def save(self):
        settings = self.parent_gui.build_settings_payload()
        settings["hotkeys"] = {action: var.get() for action, var in self.hotkey_vars.items()}
        settings["auto_translate"] = self.auto_translate_var.get()
        settings["show_border"] = self.show_border_var.get()
        self.settings_manager.save_settings(settings)
        self.parent_gui.auto_translate_var.set(self.auto_translate_var.get())
        self.parent_gui.show_persistent_border_var.set(self.show_border_var.get())
        self.parent_gui.rebind_hotkeys()
        if self.show_border_var.get():
            self.parent_gui.update_persistent_border()
        else:
            self.parent_gui.destroy_persistent_border()
        self.parent_gui.set_status("Ayarlar kaydedildi.", "success")
        self.destroy()


class HistoryWindow:
    def __init__(self, parent_gui, translator):
        self.parent_gui = parent_gui
        self.translator = translator
        self.window = tk.Toplevel(parent_gui.root)
        self.window.title("Çeviri Geçmişi")
        self.window.geometry("1120x680")
        self.window.minsize(980, 560)
        self.window.transient(parent_gui.root)
        self.window.grab_set()
        self.window.configure(bg=APP_THEME["bg"])

        self.search_var = StringVar()
        self.build_ui()
        self.load_history()

    def build_ui(self):
        shell = tk.Frame(self.window, bg=APP_THEME["bg"])
        shell.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)

        tk.Label(shell, text="Çeviri Geçmişi", bg=APP_THEME["bg"], fg=APP_THEME["text"], font=("Segoe UI Semibold", 17)).pack(anchor="w")
        lbl = tk.Label(shell, text="Arama yapın, kayıtları inceleyin veya geçmişi temizleyin.", bg=APP_THEME["bg"], fg=APP_THEME["muted"], font=("Segoe UI", 10), justify=tk.LEFT)
        lbl.pack(anchor="w", fill=tk.X, expand=True, pady=(4, 12))
        lbl.bind("<Configure>", lambda e, l=lbl: l.configure(wraplength=e.width))

        toolbar = tk.Frame(shell, bg=APP_THEME["bg"])
        toolbar.pack(fill=tk.X, pady=(0, 12))

        search_entry = tk.Entry(toolbar, textvariable=self.search_var, relief=tk.FLAT, bg=APP_THEME["surface"], fg=APP_THEME["text"], insertbackground=APP_THEME["text"], font=("Segoe UI", 10))
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8)
        search_entry.bind("<KeyRelease>", self.on_search)
        ttk.Button(toolbar, text="Ara", command=self.search_history).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(toolbar, text="Yenile", command=self.load_history).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(toolbar, text="Temizle", command=self.clear_history).pack(side=tk.LEFT, padx=(8, 0))

        table_card = CardFrame(shell, "Kayıtlar", "Son 100 çeviri burada listelenir.")
        table_card.pack(fill=tk.BOTH, expand=True)

        columns = ("Tarih", "Kaynak", "Hedef", "Orijinal", "Çeviri", "OCR", "Motor")
        self.tree = ttk.Treeview(table_card.body, columns=columns, show="headings", height=16)
        widths = {"Tarih": 145, "Kaynak": 80, "Hedef": 80, "Orijinal": 260, "Ceviri": 260, "OCR": 100, "Motor": 100}
        for column in columns:
            self.tree.heading(column, text=column)
            self.tree.column(column, width=widths[column], anchor="w")
        y_scroll = ttk.Scrollbar(table_card.body, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=y_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self.show_detail)
        self.tree.bind("<Double-1>", self.show_detail)

        detail_card = CardFrame(shell, "Detay", "Seçilen kaydın tam içeriği.")
        detail_card.pack(fill=tk.BOTH, expand=True, pady=(14, 0))
        self.detail_text = scrolledtext.ScrolledText(detail_card.body, wrap=tk.WORD, font=("Segoe UI", 10), bg=APP_THEME["panel"], fg=APP_THEME["text"], relief=tk.FLAT, insertbackground=APP_THEME["text"])
        self.detail_text.pack(fill=tk.BOTH, expand=True)
        self.detail_text.configure(state="disabled")

    def rows_from_results(self, results):
        rows = []
        for entry in results:
            try:
                date_str = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
            except Exception:
                date_str = entry.get("timestamp", "")[:16]
            original = entry.get("original", "")
            translated = entry.get("translated", "")
            rows.append((date_str, entry.get("source_lang", ""), entry.get("target_lang", ""), (original[:75] + "...") if len(original) > 75 else original, (translated[:75] + "...") if len(translated) > 75 else translated, entry.get("ocr_method", ""), entry.get("translator_engine", ""), json.dumps(entry, ensure_ascii=False)))
        return rows

    def load_history(self):
        self.populate(self.translator.get_translation_history(100))

    def populate(self, results):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in self.rows_from_results(results):
            self.tree.insert("", "end", values=row[:-1], tags=(row[-1],))
        self.write_detail("Kayıt seçildiğinde detay burada gösterilir.")

    def on_search(self, _event=None):
        query = self.search_var.get().strip()
        if len(query) >= 2 or not query:
            self.search_history()

    def search_history(self):
        query = self.search_var.get().strip()
        if query:
            self.populate(self.translator.search_translation_history(query))
        else:
            self.load_history()

    def write_detail(self, text):
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert("1.0", text)
        self.detail_text.configure(state="disabled")

    def show_detail(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            return
        item = self.tree.item(selection[0])
        try:
            payload = json.loads(item["tags"][0])
        except (KeyError, IndexError, json.JSONDecodeError):
            self.write_detail("Detay verisi okunamadı.")
            return
        detail = (
            f"Tarih: {payload.get('timestamp', '')}\n"
            f"Dil: {payload.get('source_lang', '')} -> {payload.get('target_lang', '')}\n"
            f"OCR: {payload.get('ocr_method', '')}\n"
            f"Motor: {payload.get('translator_engine', '')}\n\n"
            f"Orijinal Metin:\n{payload.get('original', '')}\n\n"
            f"Ceviri:\n{payload.get('translated', '')}"
        )
        self.write_detail(detail)

    def clear_history(self):
        if messagebox.askyesno("Geçmişi Temizle", "Tüm çeviri geçmişi silinsin mi?", parent=self.window):
            self.translator.clear_translation_history()
            self.load_history()


class ResultsPopoutWindow(tk.Toplevel):
    def __init__(self, parent_gui):
        super().__init__(parent_gui.root)
        self.parent_gui = parent_gui
        self.title("Sonuçlar")
        self.geometry("980x520")
        self.minsize(860, 420)
        self.configure(bg=APP_THEME["bg"])
        self.protocol("WM_DELETE_WINDOW", self.close)

        shell = tk.Frame(self, bg=APP_THEME["bg"])
        shell.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)
        pane = ttk.PanedWindow(shell, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True)

        original_card = CardFrame(pane, "Orijinal", "Yakalanan OCR metni")
        translated_card = CardFrame(pane, "Ceviri", "Düzenlenebilir çeviri paneli")
        pane.add(original_card, weight=1)
        pane.add(translated_card, weight=1)

        self.original = scrolledtext.ScrolledText(original_card.body, wrap=tk.WORD, font=("Segoe UI", 11), bg=APP_THEME["panel"], fg=APP_THEME["text"], relief=tk.FLAT)
        self.original.pack(fill=tk.BOTH, expand=True)
        self.original.configure(state="disabled")

        self.translated = scrolledtext.ScrolledText(translated_card.body, wrap=tk.WORD, font=("Segoe UI", 11), bg=APP_THEME["panel"], fg=APP_THEME["text"], relief=tk.FLAT, insertbackground=APP_THEME["text"])
        self.translated.pack(fill=tk.BOTH, expand=True)
        self.translated.bind("<KeyRelease>", lambda _event: self.parent_gui.sync_translated_text(from_widget="popout"))

    def close(self):
        self.parent_gui.popout_window = None
        self.destroy()


class DirectOverlayWindow:
    def __init__(self, parent_gui, image, results, region, is_manga_mode=False):
        self.parent_gui = parent_gui
        self.image = image
        self.results = results
        self.region = region
        self.is_manga_mode = is_manga_mode
        self.overlay_windows = []
        self.tk_image = None

        if is_manga_mode and results:
            self.create_multiple_overlays()
        else:
            self.create_single_overlay()

    def create_multiple_overlays(self):
        for result in self.results:
            bbox = result.get("bbox")
            translated = result.get("translated", "")
            if not bbox or not translated:
                continue
            left, top, right, bottom = bbox
            width = max(80, right - left)
            height = max(50, bottom - top)

            window = tk.Toplevel(self.parent_gui.root)
            window.overrideredirect(True)
            window.attributes("-topmost", True)
            window.attributes("-alpha", 0.94)
            x = self.region["left"] + left
            y = self.region["top"] + top
            window.geometry(f"{width}x{height}+{x}+{y}")
            window.configure(bg=APP_THEME["surface"])

            canvas = tk.Canvas(window, bg=APP_THEME["surface"], highlightthickness=1, highlightbackground=APP_THEME["accent"])
            canvas.pack(fill=tk.BOTH, expand=True)
            canvas.create_rectangle(0, 0, width, height, fill=APP_THEME["surface"], outline=APP_THEME["accent"], width=2)
            canvas.create_text(width / 2, height / 2, text=translated, width=width - 16, fill=APP_THEME["text"], font=("Segoe UI Semibold", 11), justify=tk.CENTER)

            window.bind("<Escape>", lambda _event, current=window: self.close_window(current))
            window.bind("<Delete>", lambda _event, current=window: self.close_window(current))
            window.bind("<Button-1>", lambda _event, current=window: self.close_window(current))
            window.after(20000, lambda current=window: self.close_window(current))
            self.overlay_windows.append(window)

    def create_single_overlay(self):
        width = self.region["width"]
        height = self.region["height"]
        window = tk.Toplevel(self.parent_gui.root)
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        window.attributes("-alpha", 0.96)
        window.geometry(f"{width}x{height}+{self.region['left']}+{self.region['top']}")
        window.configure(bg=APP_THEME["surface"])

        canvas = tk.Canvas(window, bg=APP_THEME["surface"], highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        self.tk_image = ImageTk.PhotoImage(self.image.resize((width, height)))
        canvas.create_image(0, 0, anchor="nw", image=self.tk_image)
        for result in self.results:
            bbox = result.get("bbox")
            translated = result.get("translated", "")
            if not bbox or not translated:
                continue
            left, top, right, bottom = bbox
            canvas.create_rectangle(left, top, right, bottom, fill=APP_THEME["surface"], outline=APP_THEME["accent"], width=2)
            canvas.create_text(left + 8, top + 8, anchor="nw", text=translated, fill=APP_THEME["text"], font=("Segoe UI Semibold", 11), width=max(60, right - left - 16))

        window.bind("<Escape>", lambda _event: self.close_all())
        window.bind("<Delete>", lambda _event: self.close_all())
        window.bind("<Button-1>", lambda _event: self.close_all())
        window.after(20000, self.close_all)
        self.overlay_windows.append(window)

    def close_window(self, window):
        if window and window.winfo_exists():
            window.destroy()
        if window in self.overlay_windows:
            self.overlay_windows.remove(window)

    def close_all(self):
        for window in list(self.overlay_windows):
            self.close_window(window)


class TranslatorGUI:
    def __init__(self, root):
        self.root = root
        self.settings_manager = SettingsManager()
        self.translator = None
        self.keyboard_hotkey_refs = []
        self.selection_window = None
        self.selection_canvas = None
        self.selection_rect = None
        self.selection_size_text = None
        self.selection_origin = None
        self.persistent_border_window = None
        self.popout_window = None
        self.last_original_translation = ""
        self._updating_text = False
        self.translator_engine_buttons = {}

        self.root.title("Manga Çevirici")
        self.root.configure(bg=APP_THEME["bg"])
        self.root.geometry(self.settings_manager.get("window_geometry"))
        self.root.minsize(1120, 760)

        self.configure_styles()
        self.setup_variables()

        try:
            self.translator = ScreenTranslator(local_model_path=self.local_model_path)
        except Exception as error:
            messagebox.showerror("Başlatma Hatası", f"Cevirici baslatilamadi:\n{error}")
            self.root.destroy()
            return

        self.build_ui()
        self.update_local_gemma_availability()
        self.setup_global_hotkeys()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        if self.show_persistent_border_var.get():
            self.update_persistent_border()
        self.set_status("Hazır. Alan seçip çeviri başlatabilirsiniz.", "ready")

    def configure_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TButton", font=("Segoe UI Semibold", 10), padding=8)
        style.configure("Accent.TButton", font=("Segoe UI Semibold", 10), padding=10, foreground="white")
        style.map("Accent.TButton", background=[("active", APP_THEME["accent_alt"]), ("!disabled", APP_THEME["accent"])], foreground=[("!disabled", "white")])
        style.configure("TCombobox", fieldbackground=APP_THEME["panel"], background=APP_THEME["panel"], foreground=APP_THEME["text"], padding=6)
        style.configure("Treeview", background=APP_THEME["surface"], fieldbackground=APP_THEME["surface"], foreground=APP_THEME["text"], rowheight=30, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=APP_THEME["panel_alt"], foreground=APP_THEME["text"], font=("Segoe UI Semibold", 10), padding=8)

    def setup_variables(self):
        coords = self.settings_manager.get("last_coords")
        langs = self.settings_manager.get("last_langs")
        engines = self.settings_manager.get("last_engines")

        self.left_var = StringVar(value=coords.get("left", "575"))
        self.top_var = StringVar(value=coords.get("top", "150"))
        self.width_var = StringVar(value=coords.get("width", "750"))
        self.height_var = StringVar(value=coords.get("height", "850"))

        self.source_lang_var = StringVar(value=langs.get("source", "English"))
        self.target_lang_var = StringVar(value=langs.get("target", "Turkish"))
        self.ocr_method_var = StringVar(value=engines.get("ocr", "cloud_vision"))
        self.translator_engine_var = StringVar(value=engines.get("translator", "local_gemma"))
        self.gemini_quality_var = StringVar(value=engines.get("gemini_quality", "normal"))
        self.preprocessing_profile_var = StringVar(value=PREPROCESSING_LABELS.get(engines.get("preprocessing_profile", "normal"), "Normal"))
        self.layout_mode_var = StringVar(value=self.settings_manager.get("layout_mode"))

        self.auto_translate_var = BooleanVar(value=self.settings_manager.get("auto_translate"))
        self.show_persistent_border_var = BooleanVar(value=self.settings_manager.get("show_border"))
        self.local_model_path = self.settings_manager.get("local_model").get("path", DEFAULT_LOCAL_GEMMA_MODEL_PATH)

    def build_ui(self):
        self.main_scroll = ScrollableFrame(self.root, APP_THEME["bg"])
        self.main_scroll.pack(fill=tk.BOTH, expand=True)

        shell = tk.Frame(self.main_scroll.scrollable_frame, bg=APP_THEME["bg"])
        shell.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)
        shell.columnconfigure(0, weight=0, minsize=365)
        shell.columnconfigure(1, weight=1)
        shell.rowconfigure(1, weight=1)

        header = tk.Frame(shell, bg=APP_THEME["bg"])
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        header.columnconfigure(0, weight=1)

        title_wrap = tk.Frame(header, bg=APP_THEME["bg"])
        title_wrap.grid(row=0, column=0, sticky="w")
        tk.Label(title_wrap, text="Manga Çevirici", bg=APP_THEME["bg"], fg=APP_THEME["text"], font=("Segoe UI Semibold", 24)).pack(anchor="w")
        lbl = tk.Label(title_wrap, text="Seçili bölgeden OCR alıp sonucu daha temiz ve hızlı bir akışla sunar.", bg=APP_THEME["bg"], fg=APP_THEME["muted"], font=("Segoe UI", 10), justify=tk.LEFT)
        lbl.pack(anchor="w", fill=tk.X, expand=True, pady=(4, 0))
        lbl.bind("<Configure>", lambda e, l=lbl: l.configure(wraplength=e.width))

        pill_bar = tk.Frame(header, bg=APP_THEME["bg"])
        pill_bar.grid(row=0, column=1, sticky="e")
        StatusPill(pill_bar, "F1 Çevir", APP_THEME["accent_soft"], APP_THEME["accent_alt"]).pack(side=tk.LEFT, padx=(0, 8))
        StatusPill(pill_bar, "F2 Alan Seç", APP_THEME["panel_alt"]).pack(side=tk.LEFT, padx=(0, 8))
        StatusPill(pill_bar, "F5 Overlay", APP_THEME["panel_alt"]).pack(side=tk.LEFT)

        sidebar = tk.Frame(shell, bg=APP_THEME["bg"])
        sidebar.grid(row=1, column=0, sticky="nsew", padx=(0, 16))
        main = tk.Frame(shell, bg=APP_THEME["bg"])
        main.grid(row=1, column=1, sticky="nsew")
        main.rowconfigure(1, weight=1)
        main.columnconfigure(0, weight=1)

        self.build_sidebar(sidebar)
        self.build_main(main)

        for variable in [self.ocr_method_var, self.translator_engine_var, self.source_lang_var, self.target_lang_var, self.layout_mode_var, self.gemini_quality_var, self.preprocessing_profile_var]:
            variable.trace_add("write", lambda *_args: self.refresh_summary())

    def build_sidebar(self, parent):
        region_card = CardFrame(parent, "Yakalama Alanı", "Alan seçimi, koordinatlar ve hızlı aksiyonlar.")
        region_card.pack(fill=tk.X)
        grid = tk.Frame(region_card.body, bg=APP_THEME["surface"])
        grid.pack(fill=tk.X)
        for column in range(2):
            grid.columnconfigure(column, weight=1)
        self.make_labeled_entry(grid, "Sol", self.left_var, 0, 0)
        self.make_labeled_entry(grid, "Üst", self.top_var, 0, 1)
        self.make_labeled_entry(grid, "Genişlik", self.width_var, 1, 0)
        self.make_labeled_entry(grid, "Yükseklik", self.height_var, 1, 1)

        action_row = tk.Frame(region_card.body, bg=APP_THEME["surface"])
        action_row.pack(fill=tk.X, pady=(14, 0))
        ttk.Button(action_row, text="Alan Seç", command=self.start_area_selection).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(action_row, text="Çerçeveyi Göster", command=self.toggle_persistent_border).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))

        tk.Checkbutton(region_card.body, text="Seçimden sonra otomatik çevir", variable=self.auto_translate_var, bg=APP_THEME["surface"], fg=APP_THEME["text"], activebackground=APP_THEME["surface"], selectcolor=APP_THEME["surface"], font=("Segoe UI", 10)).pack(anchor="w", pady=(14, 0))

        engine_card = CardFrame(parent, "Motorlar", "OCR ve çeviri motorunu göreve göre eşleştirin.")
        engine_card.pack(fill=tk.X, pady=(14, 0))
        self.build_radio_group(engine_card.body, "OCR", self.ocr_method_var, [("Tesseract", "tesseract"), ("Cloud Vision", "cloud_vision"), ("Gemini Vision", "gemini")], command=self.toggle_gemini_controls)
        self.translator_engine_buttons = self.build_radio_group(engine_card.body, "Ceviri", self.translator_engine_var, [("Yerel Gemma", "local_gemma"), ("Gemini", "gemini"), ("Google Cloud", "google")])

        gemini_row = tk.Frame(engine_card.body, bg=APP_THEME["surface"])
        gemini_row.pack(fill=tk.X, pady=(12, 0))
        tk.Label(gemini_row, text="Gemini Kalite", bg=APP_THEME["surface"], fg=APP_THEME["muted"], font=("Segoe UI Semibold", 9)).pack(anchor="w")
        self.gemini_quality_combo = ttk.Combobox(gemini_row, state="readonly", values=["normal", "high"], textvariable=self.gemini_quality_var)
        self.gemini_quality_combo.pack(fill=tk.X, pady=(6, 0))

        preprocess_row = tk.Frame(engine_card.body, bg=APP_THEME["surface"])
        preprocess_row.pack(fill=tk.X, pady=(12, 0))
        tk.Label(preprocess_row, text="Ön İşleme", bg=APP_THEME["surface"], fg=APP_THEME["muted"], font=("Segoe UI Semibold", 9)).pack(anchor="w")
        ttk.Combobox(preprocess_row, state="readonly", values=PREPROCESSING_DISPLAY, textvariable=self.preprocessing_profile_var).pack(fill=tk.X, pady=(6, 0))

        tk.Label(engine_card.body, text=f"Model: {os.path.basename(self.local_model_path)}", bg=APP_THEME["surface"], fg=APP_THEME["muted"], font=("Segoe UI", 9), wraplength=290, justify=tk.LEFT).pack(anchor="w", pady=(12, 0))
        self.local_gemma_hint_label = tk.Label(engine_card.body, text="", bg=APP_THEME["surface"], fg=APP_THEME["warning"], font=("Segoe UI", 9), wraplength=290, justify=tk.LEFT)
        self.local_gemma_hint_label.pack(anchor="w", pady=(6, 0))

        language_card = CardFrame(parent, "Dil ve Akış", "Kaynak ve hedef dili değiştirin; manga veya oyun modunu seçin.")
        language_card.pack(fill=tk.X, pady=(14, 0))
        lang_row = tk.Frame(language_card.body, bg=APP_THEME["surface"])
        lang_row.pack(fill=tk.X)
        lang_row.columnconfigure(0, weight=1)
        lang_row.columnconfigure(1, weight=1)
        self.make_labeled_combo(lang_row, "Kaynak Dil", self.source_lang_var, LANGUAGE_OPTIONS, 0, 0)
        self.make_labeled_combo(lang_row, "Hedef Dil", self.target_lang_var, TARGET_LANGUAGE_OPTIONS, 0, 1)
        self.build_radio_group(language_card.body, "Yerleşim", self.layout_mode_var, [("Oyun", "game"), ("Manga", "manga")])

        utility_card = CardFrame(parent, "Yardımcı İşler", "Ayarlar, geçmiş ve dışa aktarma tek yerde.")
        utility_card.pack(fill=tk.X, pady=(14, 0))
        ttk.Button(utility_card.body, text="Ayarlar", command=self.open_settings_window).pack(fill=tk.X)
        ttk.Button(utility_card.body, text="Çeviri Geçmişi", command=self.open_history).pack(fill=tk.X, pady=(8, 0))
        ttk.Button(utility_card.body, text="Sonuçları Dışa Aktar", command=self.export_results).pack(fill=tk.X, pady=(8, 0))

        self.toggle_gemini_controls()

    def build_main(self, parent):
        control_card = CardFrame(parent, "Hızlı Aksiyonlar", "Ana iş akışı tek satırda toplandı.")
        control_card.grid(row=0, column=0, sticky="ew")

        button_row = tk.Frame(control_card.body, bg=APP_THEME["surface"])
        button_row.pack(fill=tk.X)
        self.translate_button = ttk.Button(button_row, text="Şimdi Çevir", style="Accent.TButton", command=self.perform_single_translation)
        self.translate_button.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.overlay_button = ttk.Button(button_row, text="Overlay", command=self.perform_overlay_translation)
        self.overlay_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
        ttk.Button(button_row, text="Temizle", command=self.clear_results).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
        ttk.Button(button_row, text="Pencereye Aç", command=self.open_popout_window).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))

        summary = tk.Frame(control_card.body, bg=APP_THEME["surface"])
        summary.pack(fill=tk.X, pady=(14, 0))
        self.summary_label = tk.Label(summary, text=self.build_summary_text(), bg=APP_THEME["accent_soft"], fg=APP_THEME["accent_alt"], padx=14, pady=10, font=("Segoe UI", 10), anchor="w", justify=tk.LEFT)
        self.summary_label.pack(fill=tk.X)

        results_card = CardFrame(parent, "Sonuçlar", "Orijinal OCR ve düzenlenebilir çeviri alanı yan yana.")
        results_card.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        results_card.body.rowconfigure(0, weight=1)
        results_card.body.columnconfigure(0, weight=1)
        results_card.body.columnconfigure(1, weight=1)

        original_panel = tk.Frame(results_card.body, bg=APP_THEME["surface"])
        original_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        translated_panel = tk.Frame(results_card.body, bg=APP_THEME["surface"])
        translated_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        self.build_text_panel(original_panel, "Orijinal Metin", "OCR sonucu", editable=False)
        self.build_text_panel(translated_panel, "Ceviri", "Düzenlenebilir metin", editable=True)

        feedback_bar = tk.Frame(results_card.body, bg=APP_THEME["surface"])
        feedback_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        ttk.Button(feedback_bar, text="Düzeltmeyi Gönder", command=self.submit_correction).pack(side=tk.LEFT)
        ttk.Button(feedback_bar, text="Gecmisi Ac", command=self.open_history).pack(side=tk.LEFT, padx=(8, 0))

        status_wrap = tk.Frame(parent, bg=APP_THEME["bg"])
        status_wrap.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        self.status_label = tk.Label(status_wrap, text="", bg=APP_THEME["panel_alt"], fg=APP_THEME["text"], font=("Segoe UI Semibold", 10), anchor="w", padx=14, pady=10)
        self.status_label.pack(fill=tk.X)

    def build_text_panel(self, parent, title, subtitle, editable):
        tk.Label(parent, text=title, bg=APP_THEME["surface"], fg=APP_THEME["text"], font=("Segoe UI Semibold", 11)).pack(anchor="w")
        lbl = tk.Label(parent, text=subtitle, bg=APP_THEME["surface"], fg=APP_THEME["muted"], font=("Segoe UI", 9), justify=tk.LEFT)
        lbl.pack(anchor="w", fill=tk.X, expand=True, pady=(2, 8))
        lbl.bind("<Configure>", lambda e, l=lbl: l.configure(wraplength=e.width))
        widget = scrolledtext.ScrolledText(parent, wrap=tk.WORD, font=("Segoe UI", 11), bg=APP_THEME["panel"], fg=APP_THEME["text"], relief=tk.FLAT, padx=14, pady=14, insertbackground=APP_THEME["text"])
        widget.pack(fill=tk.BOTH, expand=True)
        if editable:
            self.text_area_translated = widget
            widget.bind("<KeyRelease>", lambda _event: self.sync_translated_text(from_widget="main"))
        else:
            self.text_area_original = widget
            widget.configure(state="disabled")

    def make_labeled_entry(self, parent, label, variable, row, column):
        frame = tk.Frame(parent, bg=APP_THEME["surface"])
        frame.grid(row=row, column=column, sticky="ew", padx=(0 if column == 0 else 6, 6 if column == 0 else 0), pady=4)
        tk.Label(frame, text=label, bg=APP_THEME["surface"], fg=APP_THEME["muted"], font=("Segoe UI Semibold", 9)).pack(anchor="w")
        entry = tk.Entry(frame, textvariable=variable, relief=tk.FLAT, bg=APP_THEME["panel"], fg=APP_THEME["text"], insertbackground=APP_THEME["text"], font=("Segoe UI", 10))
        entry.pack(fill=tk.X, ipady=8, pady=(4, 0))
        variable.trace_add("write", self.on_coords_changed)

    def make_labeled_combo(self, parent, label, variable, values, row, column):
        frame = tk.Frame(parent, bg=APP_THEME["surface"])
        frame.grid(row=row, column=column, sticky="ew", padx=(0 if column == 0 else 6, 6 if column == 0 else 0), pady=4)
        tk.Label(frame, text=label, bg=APP_THEME["surface"], fg=APP_THEME["muted"], font=("Segoe UI Semibold", 9)).pack(anchor="w")
        ttk.Combobox(frame, state="readonly", textvariable=variable, values=values).pack(fill=tk.X, pady=(4, 0))

    def build_radio_group(self, parent, title, variable, options, command=None):
        frame = tk.Frame(parent, bg=APP_THEME["surface"])
        frame.pack(fill=tk.X, pady=(12, 0))
        tk.Label(frame, text=title, bg=APP_THEME["surface"], fg=APP_THEME["muted"], font=("Segoe UI Semibold", 9)).pack(anchor="w")
        row = tk.Frame(frame, bg=APP_THEME["surface"])
        row.pack(fill=tk.X, pady=(6, 0))
        buttons = {}
        for index, (label, value) in enumerate(options):
            radio = tk.Radiobutton(row, text=label, value=value, variable=variable, command=command, bg=APP_THEME["surface"], fg=APP_THEME["text"], selectcolor=APP_THEME["surface"], activebackground=APP_THEME["surface"], font=("Segoe UI", 10))
            radio.grid(row=0, column=index, sticky="w", padx=(0, 14))
            buttons[value] = radio
        return buttons

    def build_summary_text(self):
        return f"OCR: {self.ocr_method_var.get()}   |   Ceviri: {self.translator_engine_var.get()}   |   Dil: {self.source_lang_var.get()} -> {self.target_lang_var.get()}   |   Yerlesim: {self.layout_mode_var.get()}"

    def refresh_summary(self):
        if hasattr(self, "summary_label"):
            self.summary_label.configure(text=self.build_summary_text())

    def convert_key_format(self, tk_hotkey):
        if not tk_hotkey or not isinstance(tk_hotkey, str):
            return ""
        if tk_hotkey.startswith("<") and tk_hotkey.endswith(">"):
            key = tk_hotkey[1:-1].lower()
            parts = key.split("-")
            aliases = {"control": "ctrl", "alt": "alt", "shift": "shift"}
            return "+".join(aliases.get(part, part) for part in parts)
        return tk_hotkey.lower()

    def clear_registered_hotkeys(self):
        if keyboard is None:
            return
        while self.keyboard_hotkey_refs:
            hotkey_ref = self.keyboard_hotkey_refs.pop()
            try:
                keyboard.remove_hotkey(hotkey_ref)
            except (KeyError, ValueError, AttributeError):
                continue
            except Exception:
                continue

    def register_hotkey(self, key, callback):
        if keyboard is None or not key:
            return
        hotkey_ref = keyboard.add_hotkey(key, lambda current=callback: self.root.after(0, current))
        self.keyboard_hotkey_refs.append(hotkey_ref)

    def setup_global_hotkeys(self):
        if keyboard is None:
            self.set_status("keyboard paketi yok. Global kisayollar pasif, uygulama ici butonlar aktif.", "warning")
            return
        hotkeys = self.settings_manager.get("hotkeys")
        self.clear_registered_hotkeys()
        bindings = {
            "translate": self.perform_single_translation,
            "select_area": self.start_area_selection,
            "history": self.open_history,
            "toggle_persistent_border": self.toggle_persistent_border,
            "overlay": self.perform_overlay_translation,
        }
        for action, callback in bindings.items():
            key = self.convert_key_format(hotkeys.get(action))
            if key:
                try:
                    self.register_hotkey(key, callback)
                except Exception:
                    continue
        try:
            self.register_hotkey("ctrl+q", self.on_close)
            self.register_hotkey("esc", self.cancel_operations)
        except Exception:
            pass

    def rebind_hotkeys(self):
        self.setup_global_hotkeys()

    def open_settings_window(self):
        ModernSettingsWindow(self)

    def open_history(self):
        HistoryWindow(self, self.translator)

    def toggle_gemini_controls(self):
        if hasattr(self, "gemini_quality_combo"):
            state = "readonly" if self.ocr_method_var.get() == "gemini" else "disabled"
            self.gemini_quality_combo.configure(state=state)
        self.refresh_summary()

    def pick_fallback_translator_engine(self):
        if self.translator and self.translator.text_model:
            return "gemini"
        if self.translator and self.translator.google_translator_client:
            return "google"
        return "gemini"

    def update_local_gemma_availability(self, notify=False):
        if not self.translator:
            return

        is_available, reason = self.translator.get_local_gemma_availability()
        local_button = self.translator_engine_buttons.get("local_gemma")
        if local_button:
            local_button.configure(state=tk.NORMAL if is_available else tk.DISABLED)

        if hasattr(self, "local_gemma_hint_label"):
            self.local_gemma_hint_label.configure(text="" if is_available else f"Yerel Gemma devre dışı: {reason}")

        if not is_available and self.translator_engine_var.get() == "local_gemma":
            self.translator_engine_var.set(self.pick_fallback_translator_engine())
            self.refresh_summary()
            if notify:
                self.set_status("Yerel Gemma kullanılamıyor. Diğer çeviri motoruna geçildi.", "warning")

    def build_settings_payload(self):
        return {
            "theme": self.settings_manager.get("theme"),
            "hotkeys": self.settings_manager.get("hotkeys"),
            "window_geometry": self.root.geometry(),
            "last_coords": {"left": self.left_var.get(), "top": self.top_var.get(), "width": self.width_var.get(), "height": self.height_var.get()},
            "last_langs": {"source": self.source_lang_var.get(), "target": self.target_lang_var.get()},
            "last_engines": {
                "ocr": self.ocr_method_var.get(),
                "translator": self.translator_engine_var.get(),
                "gemini_quality": self.gemini_quality_var.get(),
                "preprocessing_profile": PREPROCESSING_REVERSE.get(self.preprocessing_profile_var.get(), "normal"),
            },
            "local_model": {"path": self.local_model_path},
            "auto_translate": self.auto_translate_var.get(),
            "layout_mode": self.layout_mode_var.get(),
            "show_border": self.show_persistent_border_var.get(),
        }

    def save_current_settings(self):
        self.settings_manager.save_settings(self.build_settings_payload())

    def set_status(self, text, kind="ready"):
        if not hasattr(self, "status_label"):
            return
        colors = {
            "ready": (APP_THEME["panel_alt"], APP_THEME["text"]),
            "success": ("#d9f2df", APP_THEME["success"]),
            "warning": ("#fff0d8", APP_THEME["warning"]),
            "error": ("#fde0df", APP_THEME["danger"]),
            "working": (APP_THEME["accent_soft"], APP_THEME["accent_alt"]),
        }
        bg_color, fg_color = colors.get(kind, colors["ready"])
        self.status_label.configure(text=text, bg=bg_color, fg=fg_color)

    def get_coords(self):
        try:
            return {"left": int(self.left_var.get()), "top": int(self.top_var.get()), "width": int(self.width_var.get()), "height": int(self.height_var.get())}
        except (ValueError, tk.TclError):
            return None

    def on_coords_changed(self, *_args):
        self.refresh_summary()
        if self.show_persistent_border_var.get():
            self.update_persistent_border()

    def destroy_persistent_border(self):
        if self.persistent_border_window and self.persistent_border_window.winfo_exists():
            self.persistent_border_window.destroy()
        self.persistent_border_window = None

    def toggle_persistent_border(self):
        new_state = not self.show_persistent_border_var.get()
        self.show_persistent_border_var.set(new_state)
        if new_state:
            self.update_persistent_border()
            self.set_status("Sürekli çerçeve açıldı.", "success")
        else:
            self.destroy_persistent_border()
            self.set_status("Sürekli çerçeve kapatildi.", "warning")

    def update_persistent_border(self):
        coords = self.get_coords()
        if not coords:
            return
        self.destroy_persistent_border()
        window = tk.Toplevel(self.root)
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        transparent_color = "grey1"
        try:
            window.attributes("-transparentcolor", transparent_color)
        except tk.TclError:
            pass
        window.geometry(f"{coords['width']}x{coords['height']}+{coords['left']}+{coords['top']}")
        canvas = tk.Canvas(window, bg=transparent_color, highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        canvas.create_rectangle(1, 1, coords["width"] - 2, coords["height"] - 2, outline=APP_THEME["accent"], width=3)
        self.persistent_border_window = window

    def write_original_text(self, text):
        self.text_area_original.configure(state="normal")
        self.text_area_original.delete("1.0", tk.END)
        self.text_area_original.insert("1.0", text)
        self.text_area_original.configure(state="disabled")

    def write_translated_text(self, text):
        self.text_area_translated.delete("1.0", tk.END)
        self.text_area_translated.insert("1.0", text)

    def sync_translated_text(self, from_widget="main"):
        if self._updating_text:
            return
        if not self.popout_window or not self.popout_window.winfo_exists():
            return
        self._updating_text = True
        try:
            if from_widget == "main":
                text = self.text_area_translated.get("1.0", tk.END)
                self.popout_window.translated.delete("1.0", tk.END)
                self.popout_window.translated.insert("1.0", text)
            else:
                text = self.popout_window.translated.get("1.0", tk.END)
                self.text_area_translated.delete("1.0", tk.END)
                self.text_area_translated.insert("1.0", text)
        finally:
            self._updating_text = False

    def update_text_areas(self, result=None):
        if result is None:
            original = self.text_area_original.get("1.0", tk.END)
            translated = self.text_area_translated.get("1.0", tk.END)
        else:
            original = result.get("original", "")
            translated = result.get("translated", "")
            self.last_original_translation = translated
            self.write_original_text(original)
            self.write_translated_text(translated)

        if self.popout_window and self.popout_window.winfo_exists():
            self.popout_window.original.configure(state="normal")
            self.popout_window.original.delete("1.0", tk.END)
            self.popout_window.original.insert("1.0", original)
            self.popout_window.original.configure(state="disabled")
            self.popout_window.translated.delete("1.0", tk.END)
            self.popout_window.translated.insert("1.0", translated)

    def open_popout_window(self):
        if self.popout_window and self.popout_window.winfo_exists():
            self.popout_window.lift()
            self.popout_window.focus_force()
            return
        self.popout_window = ResultsPopoutWindow(self)
        self.update_text_areas()

    def start_area_selection(self):
        self.cancel_selection()
        self.selection_window = tk.Toplevel(self.root)
        self.selection_window.attributes("-fullscreen", True)
        self.selection_window.attributes("-alpha", 0.24)
        self.selection_window.attributes("-topmost", True)
        self.selection_window.configure(bg="black", cursor="crosshair")

        self.selection_canvas = tk.Canvas(self.selection_window, bg="black", highlightthickness=0)
        self.selection_canvas.pack(fill=tk.BOTH, expand=True)
        self.selection_canvas.create_text(self.selection_window.winfo_screenwidth() // 2, 48, text="Fareyle çeviri yapılacak alanı seçin. Esc ile iptal edebilirsiniz.", fill="white", font=("Segoe UI Semibold", 16))

        self.selection_canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.selection_canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.selection_canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.selection_window.bind("<Escape>", lambda _event: self.cancel_selection())
        self.selection_window.focus_force()

    def on_mouse_down(self, event):
        self.selection_origin = (event.x, event.y)
        self.selection_rect = self.selection_canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="#ffffff", width=3, dash=(6, 4))

    def on_mouse_drag(self, event):
        if not self.selection_rect or not self.selection_origin:
            return
        start_x, start_y = self.selection_origin
        self.selection_canvas.coords(self.selection_rect, start_x, start_y, event.x, event.y)
        width = abs(event.x - start_x)
        height = abs(event.y - start_y)
        if self.selection_size_text:
            self.selection_canvas.delete(self.selection_size_text)
        self.selection_size_text = self.selection_canvas.create_text(event.x, event.y - 24, text=f"{int(width)} x {int(height)}", fill="#fff5cc", font=("Segoe UI Semibold", 12))

    def on_mouse_up(self, event):
        if not self.selection_origin:
            return
        start_x, start_y = self.selection_origin
        left = min(start_x, event.x)
        top = min(start_y, event.y)
        width = abs(event.x - start_x)
        height = abs(event.y - start_y)
        self.cancel_selection()
        if width < 10 or height < 10:
            messagebox.showwarning("Küçük Alan", "Seçilen alan çok küçük.")
            return
        self.left_var.set(str(int(left)))
        self.top_var.set(str(int(top)))
        self.width_var.set(str(int(width)))
        self.height_var.set(str(int(height)))
        self.set_status("Alan güncellendi.", "success")
        if self.auto_translate_var.get():
            self.root.after(120, self.perform_single_translation)

    def cancel_selection(self):
        if self.selection_window and self.selection_window.winfo_exists():
            self.selection_window.destroy()
        self.selection_window = None
        self.selection_canvas = None
        self.selection_rect = None
        self.selection_size_text = None
        self.selection_origin = None

    def cancel_operations(self):
        self.cancel_selection()

    def set_busy(self, busy):
        state = tk.DISABLED if busy else tk.NORMAL
        self.translate_button.configure(state=state)
        self.overlay_button.configure(state=state)

    def perform_single_translation(self):
        region = self.get_coords()
        if not region:
            messagebox.showerror("Geçersiz Giriş", "Koordinatlar sayı olmalı.")
            return
        self.set_busy(True)
        self.refresh_summary()
        self.set_status("Çeviri başlatıldı. OCR ve çeviri motorları çalışıyor.", "working")
        threading.Thread(target=self._translation_worker, args=(region,), daemon=True).start()

    def _translation_worker(self, region):
        try:
            results = self.translator.capture_and_translate_with_text_detection(region, self.source_lang_var.get(), self.target_lang_var.get(), self.ocr_method_var.get(), self.gemini_quality_var.get(), self.translator_engine_var.get(), PREPROCESSING_REVERSE.get(self.preprocessing_profile_var.get(), "normal"), self.layout_mode_var.get())
            if not results:
                self.root.after(0, lambda: self.set_status("Metin bulunamadı veya çeviri üretilemedi.", "warning"))
                return
            original = "\n\n".join(item.get("original", "") for item in results)
            translated = "\n\n".join(item.get("translated", "") for item in results)
            self.root.after(0, self.update_text_areas, {"original": original, "translated": translated})
            self.root.after(0, lambda: self.set_status(f"Çeviri tamamlandı. {len(results)} blok işlendi.", "success"))
        except Exception as error:
            self.root.after(0, lambda err=error: self.set_status(f"Hata: {err}", "error"))
        finally:
            self.root.after(0, lambda: self.set_busy(False))

    def perform_overlay_translation(self):
        region = self.get_coords()
        if not region:
            messagebox.showerror("Geçersiz Giriş", "Koordinatlar sayı olmalı.")
            return
        self.set_busy(True)
        self.set_status("Overlay için ekran yakalanıyor.", "working")
        threading.Thread(target=self._overlay_worker, args=(region,), daemon=True).start()

    def _overlay_worker(self, region):
        try:
            image = self.translator.capture_screen(region)
            if image is None:
                raise RuntimeError("Ekran görüntüsü alınamadı.")
            results = self.translator.capture_and_translate_with_text_detection(region, self.source_lang_var.get(), self.target_lang_var.get(), self.ocr_method_var.get(), self.gemini_quality_var.get(), self.translator_engine_var.get(), PREPROCESSING_REVERSE.get(self.preprocessing_profile_var.get(), "normal"), self.layout_mode_var.get())
            original = "\n\n".join(item.get("original", "") for item in results)
            translated = "\n\n".join(item.get("translated", "") for item in results)
            self.root.after(0, self.update_text_areas, {"original": original, "translated": translated})
            self.root.after(0, lambda: DirectOverlayWindow(self, image, results, region, self.layout_mode_var.get() == "manga"))
            self.root.after(0, lambda: self.set_status("Overlay gösterildi.", "success"))
        except Exception as error:
            self.root.after(0, lambda err=error: messagebox.showerror("Overlay Hatası", str(err)))
            self.root.after(0, lambda err=error: self.set_status(f"Overlay hatası: {err}", "error"))
        finally:
            self.root.after(0, lambda: self.set_busy(False))

    def clear_results(self):
        self.last_original_translation = ""
        self.write_original_text("")
        self.write_translated_text("")
        if self.popout_window and self.popout_window.winfo_exists():
            self.update_text_areas({"original": "", "translated": ""})
        self.set_status("Sonuç panelleri temizlendi.", "ready")

    def export_results(self):
        original = self.text_area_original.get("1.0", tk.END).strip()
        translated = self.text_area_translated.get("1.0", tk.END).strip()
        if not original and not translated:
            messagebox.showwarning("Boş Sonuç", "Dışa aktarılacak veri yok.")
            return
        filename = filedialog.asksaveasfilename(title="Sonuçları Kaydet", defaultextension=".txt", filetypes=[("Metin Dosyaları", "*.txt"), ("Tüm Dosyalar", "*.*")])
        if not filename:
            return
        try:
            with open(filename, "w", encoding="utf-8") as handle:
                handle.write("Orijinal Metin\n")
                handle.write("=" * 40 + "\n")
                handle.write(original + "\n\n")
                handle.write("Ceviri\n")
                handle.write("=" * 40 + "\n")
                handle.write(translated + "\n")
            self.set_status("Sonuçlar dosyaya kaydedildi.", "success")
        except OSError as error:
            messagebox.showerror("Kaydetme Hatası", str(error))

    def submit_correction(self):
        original = self.text_area_original.get("1.0", tk.END).strip()
        corrected = self.text_area_translated.get("1.0", tk.END).strip()
        if not original or not corrected:
            messagebox.showwarning("Eksik Veri", "Gönderim için hem orijinal hem de çeviri alanı dolu olmalı.")
            return
        if not self.last_original_translation:
            messagebox.showwarning("Eksik Veri", "Karşılaştırılacak ilk çeviri bulunamadı.")
            return
        self.set_status("Düzeltme BigQuery için gönderiliyor.", "working")
        threading.Thread(target=self._submit_correction_worker, args=(original, corrected), daemon=True).start()

    def _submit_correction_worker(self, original, corrected):
        try:
            self.translator.log_correction_to_bigquery(original_text=original, original_translation=self.last_original_translation, corrected_translation=corrected)
            self.root.after(0, lambda: self.set_status("Düzeltme gönderildi.", "success"))
        except Exception as error:
            self.root.after(0, lambda err=error: self.set_status(f"Düzeltme gönderilemedi: {err}", "error"))

    def on_close(self):
        self.save_current_settings()
        self.clear_registered_hotkeys()
        self.destroy_persistent_border()
        self.cancel_selection()
        if self.popout_window and self.popout_window.winfo_exists():
            self.popout_window.destroy()
        if self.translator is not None:
            self.translator.close()
        self.root.destroy()


def main():
    root = tk.Tk()
    TranslatorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()


