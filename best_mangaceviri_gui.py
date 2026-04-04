import tkinter as tk
from tkinter import scrolledtext, messagebox, BooleanVar, StringVar, ttk
import threading
import json
import os
from datetime import datetime
from PIL import Image, ImageTk

# NEW: 'keyboard' library added to listen for system-wide hotkeys.
# You need to install this library by typing 'pip install keyboard' in the terminal.
import keyboard

# MAKE SURE THE FILE NAME IS CORRECT
from best_mangaceviri import ScreenTranslator, DEFAULT_LOCAL_GEMMA_MODEL_PATH

# ===================================================================================
# NEW: Collapsible Frame Class
# ===================================================================================
class CollapsibleFrame(tk.Frame):
    """A collapsible Tkinter frame component."""
    def __init__(self, parent, title="", expanded=True, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=parent.cget('bg'))

        self._expanded = expanded

        # Title Frame
        self.title_frame = tk.Frame(self, relief=tk.FLAT, borderwidth=1, bg='#e0e0e0')
        self.title_frame.pack(fill=tk.X)

        self.arrow_var = tk.StringVar(value="▼" if self._expanded else "►")
        tk.Label(self.title_frame, textvariable=self.arrow_var, font=("Arial", 10, "bold"), bg=self.title_frame.cget('bg')).pack(side=tk.LEFT, padx=5)
        tk.Label(self.title_frame, text=title, font=("Arial", 11, "bold"), bg=self.title_frame.cget('bg')).pack(side=tk.LEFT, padx=5)

        # Content Frame
        self.content_frame = tk.Frame(self, relief=tk.FLAT, borderwidth=1, bg=self.cget('bg'))
        if self._expanded:
            self.content_frame.pack(fill=tk.BOTH, padx=5, pady=5, expand=True)

        # Bind click events
        self.title_frame.bind("<Button-1>", self.toggle)
        for child in self.title_frame.winfo_children():
            child.bind("<Button-1>", self.toggle)

    def toggle(self, event=None):
        """Toggles the visibility of the frame."""
        self._expanded = not self._expanded
        if self._expanded:
            self.content_frame.pack(fill=tk.BOTH, padx=5, pady=5, expand=True)
            self.arrow_var.set("▼")
        else:
            self.content_frame.pack_forget()
            self.arrow_var.set("►")

# ===================================================================================
# Settings and Theme Management Classes
# ===================================================================================


# Hatalı olan SettingsManager sınıfının tamamını silip bunu yapıştırın

class SettingsManager:
    """Manages application settings (theme, hotkeys, last used state)."""
    def __init__(self, settings_file="settings.json"):
        self.settings_file = settings_file
        self.defaults = {
            "theme": "light",
            "hotkeys": {
                "translate": "<F1>", "select_area": "<F2>", "history": "<F3>",
                "toggle_persistent_border": "<F4>",
                "overlay": "<F5>",
                "close_overlay": "<Delete>"
            },
            "last_coords": {
                "left": "575", "top": "150", "width": "750", "height": "850"
            },
            "last_langs": {
                "source": "English", "target": "Turkish"
            },
            "last_engines": {
                "ocr": "cloud_vision", "translator": "local_gemma", "gemini_quality": "normal",
                "preprocessing_profile": "normal"
            },
            "local_model": {
                "path": DEFAULT_LOCAL_GEMMA_MODEL_PATH
            },
            "auto_translate": False,
            "layout_mode": "game",
            "window_geometry": "900x800+100+100" ,
            "collapsible_states": {
                "region": False,
                "engine": True,
                "gemini_quality": False,
                "language": False,
                "layout": True,
                "results": False
            }
        }
        self.settings = self.load_settings()

    def load_settings(self):
        if not os.path.exists(self.settings_file):
            self.save_settings(self.defaults)
            return self.defaults.copy()
        try:
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                loaded_settings = json.load(f)
                
                settings = self.defaults.copy()
                # Yüklenen ayarları varsayılanların üzerine yaz
                for key, value in loaded_settings.items():
                    if isinstance(value, dict) and key in settings:
                        settings[key].update(value)
                    else:
                        settings[key] = value
                return settings
        except (json.JSONDecodeError, IOError):
            return self.defaults.copy()

    def save_settings(self, settings):
        self.settings = settings
        with open(self.settings_file, 'w', encoding='utf-8') as f:
            json.dump(self.settings, f, indent=4)

    def get(self, key):
        return self.settings.get(key, self.defaults.get(key))
class SettingsWindow(tk.Toplevel):
    def __init__(self, parent_gui):
        super().__init__(parent_gui.root)
        self.parent_gui = parent_gui
        self.title("Ayarlar")
        self.geometry("400x380")
        self.transient(parent_gui.root)
        self.grab_set()

        self.settings_manager = parent_gui.settings_manager
        self.current_settings = self.settings_manager.get('hotkeys').copy()

        self.setup_ui()
        self.configure(bg=parent_gui.root.cget('bg'))

    def setup_ui(self):
        hotkeys_frame = tk.LabelFrame(self, text="Kısayol Ayarları", padx=10, pady=10)
        hotkeys_frame.pack(padx=10, pady=10, fill=tk.X)
        hotkeys_frame.configure(bg=self.cget('bg'))

        self.hotkey_vars = {}
        for i, (action, default_key) in enumerate(self.settings_manager.defaults['hotkeys'].items()):
            frame = tk.Frame(hotkeys_frame)
            frame.pack(fill=tk.X, pady=2)
            frame.configure(bg=self.cget('bg'))
            display_action = {
                "translate": "Çevir",
                "select_area": "Alan Seç",
                "history": "Geçmişi Aç",
                "toggle_persistent_border": "Çerçeveyi Sürekli Göster/Kapat",
                "overlay": "Overlay Çeviri",
                "close_overlay": "Overlay Kapat"
            }.get(action, action.replace('_', ' ').title())
            tk.Label(frame, text=f"{display_action}:", bg=self.cget('bg')).pack(side=tk.LEFT, padx=(0, 5))
            var = StringVar(value=self.current_settings.get(action, default_key))
            entry = tk.Entry(frame, textvariable=var, width=15)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            # Removed <FocusIn> bind to prevent "Tuşa basın..." from interfering
            entry.bind("<KeyRelease>", lambda event, v=var: self.update_hotkey_entry(event, v))
            self.hotkey_vars[action] = var

        button_frame = tk.Frame(self)
        button_frame.pack(pady=10)
        button_frame.configure(bg=self.cget('bg'))
        tk.Button(button_frame, text="Kaydet", command=self.save_and_apply_settings).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="İptal", command=self.destroy).pack(side=tk.LEFT, padx=5)

    # Removed on_hotkey_entry_focus

    def update_hotkey_entry(self, event, var):
        # Clear the entry before inserting the new key, ensuring no residual text
        event.widget.delete(0, tk.END)

        key_symbol = event.keysym
        # Filter out modifier keys themselves to avoid "Control-" or "Shift-" as stand-alone hotkeys
        if key_symbol in ["Control_L", "Control_R", "Alt_L", "Alt_R", "Shift_L", "Shift_R"]:
            return

        modifier = ""
        # Check for modifier states, Tkinter event.state values are bitmasks
        if event.state & 0x4: # Control key
            modifier += "Control-"
        if event.state & 0x8: # Alt key
            modifier += "Alt-"
        if event.state & 0x1: # Shift key
            modifier += "Shift-"
        
        # Format the final key string for Tkinter hotkey binding
        final_key = f"<{modifier}{key_symbol}>"
        var.set(final_key)
        # Debugging print to see the generated key string for Tkinter
        print(f"DEBUG: Hotkey entry set to: {final_key}")
        # Optionally, move focus away from the entry after a key is set
        self.parent_gui.root.focus_set()

    def save_and_apply_settings(self):
        new_settings = self.parent_gui.settings_manager.settings.copy()
        new_settings["hotkeys"] = {action: var.get() for action, var in self.hotkey_vars.items()}
        self.settings_manager.save_settings(new_settings)
        self.parent_gui.rebind_hotkeys()
        messagebox.showinfo("Ayarlar", "Ayarlar kaydedildi ve uygulandı.")
        self.destroy()

# ===================================================================================
# Translation History Class
# ===================================================================================

class TranslationHistoryWindow:
    def __init__(self, parent, translator):
        self.parent = parent
        self.translator = translator
        self.window = tk.Toplevel(parent.root)
        self.window.title("Çeviri Geçmişi")
        self.window.geometry("900x600")
        self.window.transient(parent.root)
        self.window.grab_set()

        self.setup_ui()
        self.load_history()
        self.window.configure(bg=parent.root.cget('bg'))

    def setup_ui(self):
        search_frame = tk.Frame(self.window)
        search_frame.pack(fill=tk.X, padx=10, pady=5)
        search_frame.configure(bg=self.window.cget('bg'))

        tk.Label(search_frame, text="Arama:", bg=self.window.cget('bg')).pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = StringVar()
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.search_entry.bind('<KeyRelease>', self.on_search)

        tk.Button(search_frame, text="🔍 Ara", command=self.search_history).pack(side=tk.LEFT, padx=5)
        tk.Button(search_frame, text="🔄 Yenile", command=self.load_history).pack(side=tk.LEFT, padx=5)
        tk.Button(search_frame, text="🗑️ Temizle", command=self.clear_history).pack(side=tk.LEFT, padx=5)

        list_frame = tk.Frame(self.window)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        list_frame.configure(bg=self.window.cget('bg'))

        columns = ('Tarih', 'Kaynak Dil', 'Hedef Dil', 'Orijinal', 'Çeviri', 'OCR', 'Çevirici')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.tree.heading(col, text=col)
            if col in ('Orijinal', 'Çeviri'): self.tree.column(col, width=200)
            elif col == 'Tarih': self.tree.column(col, width=120)
            else: self.tree.column(col, width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind('<Double-1>', self.show_detail)

        detail_frame = tk.LabelFrame(self.window, text="Seçili Çeviri Detayı")
        detail_frame.pack(fill=tk.X, padx=10, pady=5)
        detail_frame.configure(bg=self.window.cget('bg'))
        self.detail_text = scrolledtext.ScrolledText(detail_frame, height=8, wrap=tk.WORD)
        self.detail_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.detail_text.config(state='disabled')

    def load_history(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        history = self.translator.get_translation_history(100)
        for entry in history:
            try: date_str = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M')
            except: date_str = entry['timestamp'][:16]
            original_short = (entry['original'][:50] + '...') if len(entry['original']) > 50 else entry['original']
            translated_short = (entry['translated'][:50] + '...') if len(entry['translated']) > 50 else entry['translated']
            self.tree.insert('', 'end', values=(date_str, entry['source_lang'], entry['target_lang'], original_short, translated_short, entry.get('ocr_method', 'N/A'), entry.get('translator_engine', 'N/A')), tags=(json.dumps(entry),))

    def on_search(self, event=None):
        if len(self.search_var.get()) >= 2 or len(self.search_var.get()) == 0: self.search_history()

    def search_history(self):
        query = self.search_var.get()
        for item in self.tree.get_children(): self.tree.delete(item)
        results = self.translator.search_translation_history(query) if query else self.translator.get_translation_history(100)
        for entry in results:
            try: date_str = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M')
            except: date_str = entry['timestamp'][:16]
            original_short = (entry['original'][:50] + '...') if len(entry['original']) > 50 else entry['original']
            translated_short = (entry['translated'][:50] + '...') if len(entry['translated']) > 50 else entry['translated']
            self.tree.insert('', 'end', values=(date_str, entry['source_lang'], entry['target_lang'], original_short, translated_short, entry.get('ocr_method', 'N/A'), entry.get('translator_engine', 'N/A')), tags=(json.dumps(entry),))

    def show_detail(self, event=None):
        selection = self.tree.selection()
        if not selection: return
        try:
            entry = json.loads(self.tree.item(selection[0], 'tags')[0])
            detail_text = f"📅 Tarih: {entry.get('timestamp', 'N/A')}\n🌐 Kaynak Dil: {entry.get('source_lang', 'N/A')} → {entry.get('target_lang', 'N/A')}\n🔍 OCR Yöntemi: {entry.get('ocr_method', 'N/A')}\n🔄 Çevirici: {entry.get('translator_engine', 'N/A')}\n\n📝 Orijinal Metin:\n{entry.get('original', 'N/A')}\n\n✨ Çevrilmiş Metin:\n{entry.get('translated', 'N/A')}".strip()
            self.detail_text.config(state='normal')
            self.detail_text.delete(1.0, tk.END)
            self.detail_text.insert(1.0, detail_text)
            self.detail_text.config(state='disabled')
        except (ValueError, IndexError, json.JSONDecodeError):
            self.detail_text.config(state='normal')
            self.detail_text.delete(1.0, tk.END)
            self.detail_text.insert(1.0, "Detay verisi okunamadı.")
            self.detail_text.config(state='disabled')

    def clear_history(self):
        if messagebox.askyesno("Geçmişi Temizle", "Tüm çeviri geçmişi silinecek. Emin misiniz?"):
            self.translator.clear_translation_history(); self.load_history()
            messagebox.showinfo("Başarılı", "Çeviri geçmişi temizlendi.")

# ===================================================================================
# Main GUI Class
# ===================================================================================

class TranslatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Manga Çevirici v3.8")
        
        self.settings_manager = SettingsManager()
        saved_geometry = self.settings_manager.get("window_geometry")
        if saved_geometry:
            try: self.root.geometry(saved_geometry)
            except tk.TclError: self.root.geometry("900x800"); self.center_window()
        else: self.root.geometry("900x800"); self.center_window()

        self.root.minsize(600, 700)
        self.root.attributes('-topmost', False)
        self.persistent_border_window = None
        self.show_persistent_border_var = BooleanVar(value=True)
        self.pop_out_window = None
        self.local_model_path = self.settings_manager.get("local_model").get("path", DEFAULT_LOCAL_GEMMA_MODEL_PATH)
        
        # BIGQUERY IÇIN YENI DEĞIŞKEN
        self.last_original_translation = ""

        try:
            self.translator = ScreenTranslator(local_model_path=self.local_model_path)
        except Exception as e:
            messagebox.showerror("Başlatma Hatası", f"Çevirici başlatılamadı: {e}")
            self.root.destroy(); return

        self.setup_ui()
        self.setup_global_hotkeys()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.configure(bg='#f0f0f0')
        self.toggle_persistent_border()

    def center_window(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def save_current_settings(self):
        collapsed_states = {
            "region": self.region_collapsible._expanded,
            "engine": self.engine_collapsible._expanded,
            "gemini_quality": self.gemini_collapsible._expanded,
            "language": self.lang_collapsible._expanded,
            "layout": self.layout_collapsible._expanded,
            "results": self.results_collapsible._expanded
        }

        current_settings = {
            "theme": self.settings_manager.get("theme"),
            "hotkeys": self.settings_manager.get("hotkeys"),
            "window_geometry": self.root.geometry(), 
            "last_coords": {
                "left": self.left_var.get(), "top": self.top_var.get(),
                "width": self.width_var.get(), "height": self.height_var.get()
            },
            "last_langs": {
                "source": self.source_lang_var.get(), "target": self.lang_var.get()
            },
            "last_engines": {
                "ocr": self.ocr_method_var.get(), "translator": self.translator_engine_var.get(),
                "gemini_quality": self.gemini_quality_var.get(),
                "preprocessing_profile": self.preprocessing_profile_var.get()
            },
            "local_model": {
                "path": self.local_model_path
            },
            "auto_translate": self.auto_translate_var.get(),
            "layout_mode": self.layout_mode_var.get(),
            "collapsible_states": collapsed_states
        }
        self.settings_manager.save_settings(current_settings)
        print("Ayarlar başarıyla kaydedildi.")

    def on_closing(self):
        self.save_current_settings()
        keyboard.remove_all_hotkeys()
        self.translator.close()
        if self.persistent_border_window: self.persistent_border_window.destroy()
        if self.pop_out_window and self.pop_out_window.winfo_exists(): self.pop_out_window.destroy()
        self.root.destroy()

    def convert_key_format(self, tk_hotkey):
        if not tk_hotkey or not isinstance(tk_hotkey, str): return ""
        if tk_hotkey.startswith('<') and tk_hotkey.endswith('>'):
            key = tk_hotkey[1:-1].lower()
            parts = key.split('-')
            modifier_map = {'control': 'ctrl', 'alt': 'alt', 'shift': 'shift'}
            converted_parts = [modifier_map.get(part, part) for part in parts]
            return '+'.join(converted_parts)
        else: return tk_hotkey.lower()

    def setup_global_hotkeys(self):
        hotkeys = self.settings_manager.get('hotkeys')
        actions = {
            'translate': self.perform_single_translation, 'select_area': self.start_area_selection,
            'history': self.open_history, 'toggle_persistent_border': self.toggle_persistent_border,
            'overlay': self.perform_overlay_translation
        }
        for action, method in actions.items():
            tk_hotkey = hotkeys.get(action)
            if tk_hotkey:
                try:
                    global_hotkey = self.convert_key_format(tk_hotkey)
                    if global_hotkey: keyboard.add_hotkey(global_hotkey, lambda m=method: self.root.after(0, m))
                except Exception as e: print(f"Hata: {tk_hotkey} kısayolu atanamadı: {e}")
        try:
            keyboard.add_hotkey('ctrl+q', lambda: self.root.after(0, self.on_closing))
            keyboard.add_hotkey('esc', lambda: self.root.after(0, self.cancel_operations))
        except Exception as e: print(f"Hata: Sabit kısayollar atanamadı: {e}")

    def rebind_hotkeys(self):
        keyboard.remove_all_hotkeys()
        self.setup_global_hotkeys()
        print("Tüm global kısayollar yeniden yüklendi.")

    def open_settings_window(self):
        SettingsWindow(self)

    def setup_ui(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ayarlar", menu=settings_menu)
        settings_menu.add_command(label="Kısayolları Düzenle...", command=self.open_settings_window)
        settings_menu.add_separator()
        settings_menu.add_command(label="Çıkış", command=self.on_closing)

        style = ttk.Style()
        style.theme_use('clam')
        
        main_frame = tk.Frame(self.root); main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        main_frame.configure(bg=self.root.cget('bg'))

        title_frame = tk.Frame(main_frame); title_frame.pack(fill=tk.X, pady=(0, 10))
        title_frame.configure(bg=self.root.cget('bg'))
        tk.Label(title_frame, text="🌟 Manga Çevirici", font=("Arial", 16, "bold"), bg=self.root.cget('bg'), fg='#2c3e50').pack()
        tk.Label(title_frame, text="Kısayollar: F1=Çevir | F2=Alan Seç | F3=Geçmiş | F4=Çerçeveyi Göster/Kapat | F5=Overlay | Ctrl+Q=Çıkış", font=("Arial", 9), bg=self.root.cget('bg'), fg='#7f8c8d').pack()

        settings = self.settings_manager.load_settings()
        last_coords = settings.get('last_coords')
        last_engines = settings.get('last_engines')
        last_langs = settings.get('last_langs')
        auto_translate_setting = settings.get('auto_translate')
        collapsed_states = settings.get('collapsed_states', self.settings_manager.defaults['collapsible_states'])

        self.region_collapsible = CollapsibleFrame(main_frame, title="📍 Ekran Bölgesi Ayarları", expanded=collapsed_states.get("region", True))
        self.region_collapsible.pack(fill=tk.X, pady=(0, 5))
        region_frame = self.region_collapsible.content_frame

        coords_frame = tk.Frame(region_frame); coords_frame.pack(fill=tk.X, padx=10, pady=5)
        coords_frame.configure(bg=self.root.cget('bg'))
        self.left_var = StringVar(value=last_coords.get("left", "575"))
        self.top_var = StringVar(value=last_coords.get("top", "150"))
        self.width_var = StringVar(value=last_coords.get("width", "750"))
        self.height_var = StringVar(value=last_coords.get("height", "850"))
        for var in [self.left_var, self.top_var, self.width_var, self.height_var]: var.trace_add("write", self.on_coords_changed)
        left_coords = tk.Frame(coords_frame); left_coords.pack(side=tk.LEFT, fill=tk.X, expand=True); left_coords.configure(bg=self.root.cget('bg'))
        tk.Label(left_coords, text="Sol (X):", bg=self.root.cget('bg')).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        tk.Entry(left_coords, width=12, textvariable=self.left_var).grid(row=0, column=1, padx=5, pady=2)
        tk.Label(left_coords, text="Üst (Y):", bg=self.root.cget('bg')).grid(row=0, column=2, sticky="w", padx=5, pady=2)
        tk.Entry(left_coords, width=12, textvariable=self.top_var).grid(row=0, column=3, padx=5, pady=2)
        tk.Label(left_coords, text="Genişlik:", bg=self.root.cget('bg')).grid(row=1, column=0, sticky="w", padx=5, pady=2)
        tk.Entry(left_coords, width=12, textvariable=self.width_var).grid(row=1, column=1, padx=5, pady=2)
        tk.Label(left_coords, text="Yükseklik:", bg=self.root.cget('bg')).grid(row=1, column=2, sticky="w", padx=5, pady=2)
        tk.Entry(left_coords, width=12, textvariable=self.height_var).grid(row=1, column=3, padx=5, pady=2)
        right_coords = tk.Frame(coords_frame); right_coords.pack(side=tk.RIGHT, padx=10); right_coords.configure(bg=self.root.cget('bg'))
        tk.Button(right_coords, text="Fareyle Seç", command=self.start_area_selection, bg="#3498db", fg="white", font=("Arial", 10, "bold")).pack(pady=2, fill=tk.X)
        tk.Button(right_coords, text="Çerçeveyi Sürekli?", command=self.toggle_persistent_border, bg="#9b59b6", fg="white", font=("Arial", 10, "bold")).pack(pady=2, fill=tk.X)
        bottom_frame = tk.Frame(region_frame); bottom_frame.pack(fill=tk.X, padx=10, pady=5); bottom_frame.configure(bg=self.root.cget('bg'))
        self.auto_translate_var = BooleanVar(value=auto_translate_setting)
        tk.Checkbutton(bottom_frame, text="✨ Seçimden sonra otomatik çevir", variable=self.auto_translate_var, bg=self.root.cget('bg'), font=("Arial", 10)).pack(side=tk.LEFT)

        self.engine_collapsible = CollapsibleFrame(main_frame, title="⚙️ Motor Ayarları (OCR ve Çeviri)", expanded=collapsed_states.get("engine", True))
        self.engine_collapsible.pack(fill=tk.X, pady=(0, 5))
        engine_frame = self.engine_collapsible.content_frame
        engine_inner_frame = tk.Frame(engine_frame, bg=self.root.cget('bg')); engine_inner_frame.pack(fill=tk.X)
        preprocessing_frame = tk.LabelFrame(engine_inner_frame, text="🎨 Görüntü Ön İşleme", font=("Arial", 10)); preprocessing_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5)); preprocessing_frame.configure(bg=self.root.cget('bg'))
        self.preprocessing_profile_var = StringVar(value=last_engines.get("preprocessing_profile", "normal"))
        ttk.Combobox(preprocessing_frame, textvariable=self.preprocessing_profile_var, values=["Normal", "Gürültü Azalt", "Keskinleştir", "Yüksek Kontrast"], state="readonly").pack(padx=10, pady=5, fill=tk.X)
        ocr_frame = tk.LabelFrame(engine_inner_frame, text="🔍 Metin Okuma (OCR)", font=("Arial", 10)); ocr_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5)); ocr_frame.configure(bg=self.root.cget('bg'))
        self.ocr_method_var = StringVar(value=last_engines.get("ocr", "cloud_vision"))
        tk.Radiobutton(ocr_frame, text="Tesseract (Local)", variable=self.ocr_method_var, value="tesseract", command=self.toggle_options, bg=self.root.cget('bg')).pack(anchor="w", padx=10, pady=2)
        tk.Radiobutton(ocr_frame, text="Gemini Vision (Kaliteli)", variable=self.ocr_method_var, value="gemini", command=self.toggle_options, bg=self.root.cget('bg')).pack(anchor="w", padx=10, pady=2)
        tk.Radiobutton(ocr_frame, text="Cloud Vision (Verimli)", variable=self.ocr_method_var, value="cloud_vision", command=self.toggle_options, bg=self.root.cget('bg')).pack(anchor="w", padx=10, pady=2)
        translator_frame = tk.LabelFrame(engine_inner_frame, text="🌐 Çeviri Servisi", font=("Arial", 10)); translator_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0)); translator_frame.configure(bg=self.root.cget('bg'))
        self.translator_engine_var = StringVar(value=last_engines.get("translator", "local_gemma"))
        tk.Radiobutton(translator_frame, text="🖥️ Yerel Gemma (LiteRT-LM)", variable=self.translator_engine_var, value="local_gemma", bg=self.root.cget('bg')).pack(anchor="w", padx=10, pady=2)
        tk.Radiobutton(translator_frame, text="🌙 Gemini (Kaliteli)", variable=self.translator_engine_var, value="gemini", bg=self.root.cget('bg')).pack(anchor="w", padx=10, pady=2)
        tk.Radiobutton(translator_frame, text="🌟 Google Cloud (Verimli)", variable=self.translator_engine_var, value="google", bg=self.root.cget('bg')).pack(anchor="w", padx=10, pady=2)
        tk.Label(translator_frame, text=f"Model: {os.path.basename(self.local_model_path)}", bg=self.root.cget('bg'), fg='#555555', wraplength=220, justify=tk.LEFT).pack(anchor="w", padx=10, pady=(2, 0))

        self.gemini_collapsible = CollapsibleFrame(main_frame, title="💎 Gemini OCR Kalite Ayarı", expanded=collapsed_states.get("gemini_quality", False))
        self.gemini_quality_frame = self.gemini_collapsible.content_frame
        self.gemini_quality_var = StringVar(value=last_engines.get("gemini_quality", "normal"))
        tk.Radiobutton(self.gemini_quality_frame, text="💰 Normal (Düşük Maliyet)", variable=self.gemini_quality_var, value="normal", bg=self.root.cget('bg')).pack(side=tk.LEFT, padx=10, pady=5)
        tk.Radiobutton(self.gemini_quality_frame, text="💎 Yüksek (Premium Kalite)", variable=self.gemini_quality_var, value="high", bg=self.root.cget('bg')).pack(side=tk.LEFT, padx=10, pady=5)

        self.lang_collapsible = CollapsibleFrame(main_frame, title="🗣️ Dil Ayarları", expanded=collapsed_states.get("language", True))
        self.lang_collapsible.pack(fill=tk.X, pady=(0, 5))
        lang_frame = self.lang_collapsible.content_frame
        
        self.layout_collapsible = CollapsibleFrame(main_frame, title="🕹️ Metin Yerleşim Modu", expanded=collapsed_states.get("layout", True))
        self.layout_collapsible.pack(fill=tk.X, pady=(0, 5))
        layout_frame = self.layout_collapsible.content_frame
        self.layout_mode_var = StringVar(value=self.settings_manager.get("layout_mode"))
        tk.Radiobutton(layout_frame, text="Oyun Modu (Soldan Sağa)", variable=self.layout_mode_var, value="game", bg=self.root.cget('bg')).pack(anchor="w", padx=10, pady=2)
        tk.Radiobutton(layout_frame, text="Manga Modu (Sağdan Sola)", variable=self.layout_mode_var, value="manga", bg=self.root.cget('bg')).pack(anchor="w", padx=10, pady=2)
        
        lang_inner = tk.Frame(lang_frame); lang_inner.pack(fill=tk.X, padx=10, pady=5); lang_inner.configure(bg=self.root.cget('bg'))
        tk.Label(lang_inner, text="📥 Kaynak Dil:", bg=self.root.cget('bg'), font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        self.source_lang_var = StringVar(value=last_langs.get("source", "English"))
        ttk.Combobox(lang_inner, textvariable=self.source_lang_var, values=["English", "Japanese", "Korean", "Chinese", "Spanish", "French"], state="readonly", width=12).pack(side=tk.LEFT, padx=(0, 20))
        tk.Label(lang_inner, text="📤 Hedef Dil:", bg=self.root.cget('bg'), font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        self.lang_var = StringVar(value=last_langs.get("target", "Turkish"))
        ttk.Combobox(lang_inner, textvariable=self.lang_var, values=["Turkish", "English", "Spanish", "French", "German", "Italian", "Portuguese", "Russian", "Arabic"], state="readonly", width=12).pack(side=tk.LEFT)
        
        self.gemini_collapsible.pack(fill=tk.X, pady=(0, 5), after=self.engine_collapsible)
        self.toggle_options()

        control_frame = tk.Frame(main_frame); control_frame.pack(fill=tk.X, pady=(5, 10)); control_frame.configure(bg=self.root.cget('bg'))
        self.translate_button = tk.Button(control_frame, text="🚀 ŞİMDİ ÇEVİR (F1)", command=self.perform_single_translation, bg="#27ae60", fg="white", font=("Arial", 14, "bold")); self.translate_button.pack(fill=tk.X, pady=5)
        self.overlay_button = tk.Button(control_frame, text="✨ OVERLAY ÇEVİRİ (F5)", command=self.perform_overlay_translation, bg="#3498db", fg="white", font=("Arial", 12, "bold")); self.overlay_button.pack(fill=tk.X, pady=(0, 5))
        button_frame = tk.Frame(control_frame); button_frame.pack(fill=tk.X, pady=5); button_frame.configure(bg=self.root.cget('bg'))
        tk.Button(button_frame, text="Geçmişi Aç (F3)", command=self.open_history, bg="#e67e22", fg="white", font=("Arial", 11, "bold")).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        tk.Button(button_frame, text="Temizle", command=self.clear_results, bg="#95a5a6", fg="white", font=("Arial", 11, "bold")).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        tk.Button(button_frame, text="Export", command=self.export_results, bg="#8e44ad", fg="white", font=("Arial", 11, "bold")).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))

        self.results_collapsible = CollapsibleFrame(main_frame, title="📝 Çeviri Sonuçları", expanded=collapsed_states.get("results", True))
        self.results_collapsible.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        results_container = self.results_collapsible.content_frame

        title_frame_results = tk.Frame(results_container, bg=self.root.cget('bg'))
        title_frame_results.pack(fill=tk.X, padx=5, pady=(0,5))
        pop_out_button = tk.Button(title_frame_results, text="↗", font=("Arial", 10, "bold"), command=self.pop_out_results_window, width=3)
        pop_out_button.pack(side=tk.RIGHT, anchor='ne')
        
        paned_window = ttk.PanedWindow(results_container, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        left_pane = tk.Frame(paned_window, bg=self.root.cget('bg')); paned_window.add(left_pane, weight=1)
        tk.Label(left_pane, text="📝 Orijinal Metin:", font=("Arial", 10, "bold"), bg=self.root.cget('bg')).pack(anchor="w", padx=5)
        self.text_area_original = scrolledtext.ScrolledText(left_pane, height=8, wrap=tk.WORD, font=("Arial", 11), relief="sunken", bd=2)
        self.text_area_original.pack(fill=tk.BOTH, expand=True, padx=(5, 2), pady=(0, 5))
        self.text_area_original.config(state='disabled') # Başlangıçta kilitli

        right_pane = tk.Frame(paned_window, bg=self.root.cget('bg')); paned_window.add(right_pane, weight=1)
        
        # --- BIGQUERY ENTEGRASYONU: BUTON EKLENDI ---
        translated_title_frame = tk.Frame(right_pane, bg=self.root.cget('bg'))
        translated_title_frame.pack(fill=tk.X, padx=2, pady=(0,0))
        tk.Label(translated_title_frame, text="✨ Çevrilmiş Metin:", font=("Arial", 10, "bold"), bg=self.root.cget('bg')).pack(side=tk.LEFT, anchor="w")
        self.correction_button = tk.Button(translated_title_frame, text="🔄 Düzeltmeyi Gönder", command=self.submit_correction, bg="#f39c12", fg="white", font=("Arial", 9, "bold"))
        self.correction_button.pack(side=tk.RIGHT, padx=5)
        # --- ENTEGRASYON SONU ---
        
        self.text_area_translated = scrolledtext.ScrolledText(right_pane, height=8, wrap=tk.WORD, font=("Arial", 11), bg="#f8f9fa", relief="sunken", bd=2)
        self.text_area_translated.pack(fill=tk.BOTH, expand=True, padx=(2, 5), pady=(0, 5))
        # Çeviri alanı artık başlangıçtan itibaren düzenlenebilir

        status_frame = tk.Frame(main_frame, bg=self.root.cget('bg')); status_frame.pack(fill=tk.X)
        self.status_label = tk.Label(status_frame, text="🟢 Durum: Hazır - Global kısayol tuşları aktif", anchor="w", relief=tk.SUNKEN, bg="#ecf0f1", font=("Arial", 10)); self.status_label.pack(fill=tk.X, pady=2)

    # --- BIGQUERY ENTEGRASYONU: YENI FONKSIYON ---
    def submit_correction(self):
        """Metin kutularındaki verileri alıp BigQuery'ye gönderir."""
        self.text_area_original.config(state='normal')
        original_text = self.text_area_original.get("1.0", tk.END).strip()
        self.text_area_original.config(state='disabled')

        corrected_translation = self.text_area_translated.get("1.0", tk.END).strip()

        if not original_text or not corrected_translation:
            messagebox.showwarning("Eksik Veri", "Düzeltmeyi göndermek için hem orijinal hem de çevrilmiş metin alanları dolu olmalıdır.")
            return
        
        if not self.last_original_translation:
            messagebox.showwarning("Eksik Veri", "Henüz bir çeviri yapılmadı veya orijinal çeviri bulunamadı.")
            return

        self.status_label.config(text="📤 Düzeltme BigQuery'ye gönderiliyor...")
        self.root.update_idletasks() # Arayüzün güncellenmesini sağla

        # Arka planda gönderme işlemi
        threading.Thread(target=self._submit_correction_worker, args=(original_text, corrected_translation), daemon=True).start()

    def _submit_correction_worker(self, original_text, corrected_translation):
        """BigQuery'ye gönderme işlemini ayrı bir thread'de yapar."""
        try:
            self.translator.log_correction_to_bigquery(
                original_text=original_text,
                original_translation=self.last_original_translation,
                corrected_translation=corrected_translation
            )
            self.root.after(0, lambda: self.status_label.config(text="✅ Düzeltme gönderildi!"))
            self.root.after(0, lambda: messagebox.showinfo("Başarılı", "Çeviri düzeltmeniz analiz için başarıyla gönderildi. Teşekkürler!"))
        except Exception as e:
            # --- DEĞİŞİKLİK BURADA ---
            # Hata değişkeni 'e'yi, lambda'ya 'err' adında bir argüman olarak bağlıyoruz.
            self.root.after(0, lambda err=e: self.status_label.config(text=f"❌ Düzeltme gönderme hatası: {err}"))
            self.root.after(0, lambda err=e: messagebox.showerror("Hata", f"Düzeltme gönderilirken bir hata oluştu:\n{err}"))
            # --- DEĞİŞİKLİK SONU ---
    # --- ENTEGRASYON SONU ---

    def get_coords(self):
        try: return { "left": int(self.left_var.get()), "top": int(self.top_var.get()), "width": int(self.width_var.get()), "height": int(self.height_var.get()) }
        except (ValueError, tk.TclError): return None

    def pop_out_results_window(self):
        if self.pop_out_window and self.pop_out_window.winfo_exists():
            self.pop_out_window.lift(); self.pop_out_window.focus_force(); return
        self.pop_out_window = tk.Toplevel(self.root)
        self.pop_out_window.title("Çeviri Sonuçları"); self.pop_out_window.geometry("800x400")
        self.pop_out_window.configure(bg=self.root.cget('bg'))
        self.pop_out_window.protocol("WM_DELETE_WINDOW", self.on_pop_out_close)
        paned_window = ttk.PanedWindow(self.pop_out_window, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        left_pane = tk.Frame(paned_window, bg=self.root.cget('bg')); paned_window.add(left_pane, weight=1)
        tk.Label(left_pane, text="📝 Orijinal Metin:", font=("Arial", 10, "bold"), bg=self.root.cget('bg')).pack(anchor="w", padx=5)
        pop_out_original = scrolledtext.ScrolledText(left_pane, wrap=tk.WORD, font=("Arial", 11), relief="sunken", bd=2)
        pop_out_original.pack(fill=tk.BOTH, expand=True, padx=(5, 2), pady=(0, 5))
        right_pane = tk.Frame(paned_window, bg=self.root.cget('bg')); paned_window.add(right_pane, weight=1)
        tk.Label(right_pane, text="✨ Çevrilmiş Metin:", font=("Arial", 10, "bold"), bg=self.root.cget('bg')).pack(anchor="w", padx=5)
        pop_out_translated = scrolledtext.ScrolledText(right_pane, wrap=tk.WORD, font=("Arial", 11), relief="sunken", bd=2, bg="#f8f9fa")
        pop_out_translated.pack(fill=tk.BOTH, expand=True, padx=(2, 5), pady=(0, 5))
        self.pop_out_window.original_text_area = pop_out_original
        self.pop_out_window.translated_text_area = pop_out_translated
        self.update_text_areas()

    def on_pop_out_close(self):
        if self.pop_out_window: self.pop_out_window.destroy(); self.pop_out_window = None

    def update_text_areas(self, result=None):
        original_content, translated_content = "", ""
        if result:
            original_content, translated_content = result.get('original', ''), result.get('translated', '')
            self.last_original_translation = translated_content # Orijinal çeviriyi sakla
            self.text_area_original.config(state='normal'); self.text_area_original.delete(1.0, tk.END); self.text_area_original.insert(tk.END, original_content); self.text_area_original.config(state='disabled')
            self.text_area_translated.config(state='normal'); self.text_area_translated.delete(1.0, tk.END); self.text_area_translated.insert(tk.END, translated_content)
        else:
            self.text_area_original.config(state='normal'); original_content = self.text_area_original.get(1.0, tk.END); self.text_area_original.config(state='disabled')
            self.text_area_translated.config(state='normal'); translated_content = self.text_area_translated.get(1.0, tk.END)
        
        if self.pop_out_window and self.pop_out_window.winfo_exists():
            self.pop_out_window.original_text_area.config(state='normal'); self.pop_out_window.translated_text_area.config(state='normal')
            self.pop_out_window.original_text_area.delete(1.0, tk.END); self.pop_out_window.original_text_area.insert(1.0, original_content)
            self.pop_out_window.translated_text_area.delete(1.0, tk.END); self.pop_out_window.translated_text_area.insert(1.0, translated_content)
            self.pop_out_window.original_text_area.config(state='disabled')
        elif self.pop_out_window: self.pop_out_window = None

    def toggle_persistent_border(self):
        self.show_persistent_border_var.set(not self.show_persistent_border_var.get())
        if self.show_persistent_border_var.get(): self.update_persistent_border(); self.status_label.config(text="✅ Sürekli Çerçeve Açık")
        elif self.persistent_border_window: self.persistent_border_window.destroy(); self.persistent_border_window = None; self.status_label.config(text="❌ Sürekli Çerçeve Kapalı")

    def update_persistent_border(self):
        if self.persistent_border_window: self.persistent_border_window.destroy()
        coords = self.get_coords()
        if not coords: return
        self.persistent_border_window = tk.Toplevel(self.root)
        win = self.persistent_border_window
        win.overrideredirect(True); win.geometry(f"{coords['width']}x{coords['height']}+{coords['left']}+{coords['top']}")
        win.attributes('-topmost', True); transparent_color = 'grey1'; win.attributes('-transparentcolor', transparent_color)
        canvas = tk.Canvas(win, bg=transparent_color, highlightthickness=0)
        canvas.create_rectangle(0, 0, coords['width']-1, coords['height']-1, outline="red", width=3); canvas.pack(fill=tk.BOTH, expand=True)

    def on_coords_changed(self, *args):
        if self.show_persistent_border_var.get(): self.update_persistent_border()

    def perform_single_translation(self):
        if self.translate_button['state'] == tk.DISABLED: return
        monitor_region = self.get_coords()
        if not monitor_region: messagebox.showerror("Geçersiz Giriş", "Lütfen bölge ayarları için geçerli sayılar girin."); return
        self.translate_button.config(state=tk.DISABLED); self.overlay_button.config(state=tk.DISABLED)
        self.status_label.config(text=f"🔄 İşleniyor: {self.ocr_method_var.get().upper()} → {self.translator_engine_var.get().upper()}")
        threading.Thread(target=self._translation_worker, args=(monitor_region, self.layout_mode_var.get()), daemon=True).start()
    
    def _translation_worker(self, monitor_region, layout_mode='game'):
        try:
            results = self.translator.capture_and_translate_with_text_detection(
                monitor_region, self.source_lang_var.get(), self.lang_var.get(), self.ocr_method_var.get(),
                self.gemini_quality_var.get(), self.translator_engine_var.get(),
                self.preprocessing_profile_var.get(), layout_mode
            )
            if results:
                original_full_text = "\n\n".join([res.get('original', '') for res in results])
                translated_full_text = "\n\n".join([res.get('translated', '') for res in results])
                self.root.after(0, self.update_text_areas, {'original': original_full_text, 'translated': translated_full_text})
                self.root.after(0, lambda: self.status_label.config(text="✅ Çeviri tamamlandı!"))
            else: 
                self.root.after(0, lambda: self.status_label.config(text="⚠️ Metin bulunamadı veya çeviri yapılamadı"))
        except Exception as e: 
            self.root.after(0, lambda err=e: self.status_label.config(text=f"❌ Hata: {str(err)}"))
        finally: 
            self.root.after(0, lambda: self.translate_button.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.overlay_button.config(state=tk.NORMAL))

    def perform_overlay_translation(self):
        if self.overlay_button['state'] == tk.DISABLED: return
        region = self.get_coords()
        if not region: messagebox.showerror("Geçersiz Giriş", "Lütfen bölge ayarları için geçerli sayılar girin."); return
        self.overlay_button.config(state='disabled'); self.translate_button.config(state='disabled')
        is_manga_mode = (self.layout_mode_var.get() == 'manga')
        
        def overlay_thread():
            try:
                self.root.after(0, lambda: self.status_label.config(text="📄 Overlay için ekran yakalanıyor..."))
                img = self.translator.capture_screen(region)
                if not img: raise Exception("Ekran görüntüsü alınamadı.")
                status_text = "📄 Konuşma balonları algılanıyor..." if is_manga_mode else "📄 Metinler algılanıyor..."
                self.root.after(0, lambda: self.status_label.config(text=status_text))
                
                results = self.translator.capture_and_translate_with_text_detection(
                    monitor_region=region, source_lang=self.source_lang_var.get(), target_lang=self.lang_var.get(),
                    ocr_method=self.ocr_method_var.get(), gemini_quality=self.gemini_quality_var.get(), 
                    translator_engine=self.translator_engine_var.get(), preprocessing_profile=self.preprocessing_profile_var.get(), 
                    layout_mode=self.layout_mode_var.get()
                )
                
                status_text = f"✨ {len(results)} balon için overlay oluşturuluyor..." if is_manga_mode else "✨ Overlay oluşturuluyor..."
                self.root.after(0, lambda: self.status_label.config(text=status_text))
                self.root.after(0, lambda: DirectOverlayWindow(self, img, results, region, is_manga_mode))
            except Exception as e: 
                self.root.after(0, lambda err=e: messagebox.showerror("Overlay Hatası", str(err)))
            finally:
                self.root.after(0, lambda: self.overlay_button.config(state='normal'))
                self.root.after(0, lambda: self.translate_button.config(state='normal'))
                self.root.after(0, lambda: self.status_label.config(text="🟢 Durum: Hazır"))
        
        threading.Thread(target=overlay_thread, daemon=True).start()

    def start_area_selection(self):
        self.selection_window = tk.Toplevel(self.root)
        self.selection_window.attributes("-fullscreen", True, "-alpha", 0.3); self.selection_window.attributes("-topmost", True)
        self.selection_window.configure(cursor="crosshair", bg="black")
        self.selection_canvas = tk.Canvas(self.selection_window, bg="black", highlightthickness=0); self.selection_canvas.pack(fill=tk.BOTH, expand=True)
        self.selection_canvas.create_text(self.selection_window.winfo_screenwidth()//2, 50, text="🖱️ Fareyle çevirmek istediğiniz alanı seçin | ESC: İptal", fill="white", font=("Arial", 16, "bold"))
        self.rect = None; self.start_x, self.start_y = None, None
        self.selection_canvas.bind("<ButtonPress-1>", self.on_mouse_down); self.selection_canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.selection_canvas.bind("<ButtonRelease-1>", self.on_mouse_up); self.selection_window.bind("<Escape>", lambda e: self.cancel_selection())
        self.selection_window.focus_force()

    def on_mouse_down(self, event):
        self.start_x = self.selection_canvas.canvasx(event.x); self.start_y = self.selection_canvas.canvasy(event.y)
        if not self.rect: self.rect = self.selection_canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='#e74c3c', width=3, dash=(5, 5))

    def on_mouse_drag(self, event):
        cur_x, cur_y = self.selection_canvas.canvasx(event.x), self.selection_canvas.canvasy(event.y)
        self.selection_canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)
        width, height = abs(cur_x - self.start_x), abs(cur_y - self.start_y)
        if hasattr(self, 'size_text'): self.selection_canvas.delete(self.size_text)
        self.size_text = self.selection_canvas.create_text(cur_x, cur_y - 20, text=f"{int(width)} x {int(height)}", fill="yellow", font=("Arial", 12, "bold"))

    def on_mouse_up(self, event):
        end_x, end_y = self.selection_canvas.canvasx(event.x), self.selection_canvas.canvasy(event.y)
        left, top = min(self.start_x, end_x), min(self.start_y, end_y)
        width, height = abs(end_x - self.start_x), abs(end_y - self.start_y)
        self.selection_window.destroy()
        if width < 10 or height < 10: messagebox.showwarning("Küçük Alan", "Seçilen alan çok küçük."); return
        self.left_var.set(str(int(left))); self.top_var.set(str(int(top))); self.width_var.set(str(int(width))); self.height_var.set(str(int(height)))
        if self.show_persistent_border_var.get(): self.update_persistent_border()
        if self.auto_translate_var.get(): self.root.after(100, self.perform_single_translation)

    def cancel_selection(self):
        if hasattr(self, 'selection_window') and self.selection_window.winfo_exists(): self.selection_window.destroy()
    def cancel_operations(self):
        if hasattr(self, 'selection_window') and self.selection_window.winfo_exists(): self.cancel_selection()
    def open_history(self): TranslationHistoryWindow(self, self.translator)
    def toggle_options(self):
        if self.ocr_method_var.get() == "gemini":
            if not self.gemini_collapsible.winfo_manager(): self.gemini_collapsible.pack(fill=tk.X, pady=(0, 5), after=self.engine_collapsible)
        else: self.gemini_collapsible.pack_forget()
    def clear_results(self):
        self.text_area_original.config(state='normal'); self.text_area_original.delete(1.0, tk.END); self.text_area_original.config(state='disabled')
        self.text_area_translated.config(state='normal'); self.text_area_translated.delete(1.0, tk.END) # Artık kilitli değil
        self.status_label.config(text="🔄 Sonuçlar temizlendi")
        if self.pop_out_window and self.pop_out_window.winfo_exists():
            self.pop_out_window.original_text_area.config(state='normal'); self.pop_out_window.original_text_area.delete(1.0, tk.END); self.pop_out_window.original_text_area.config(state='disabled')
            self.pop_out_window.translated_text_area.config(state='normal'); self.pop_out_window.translated_text_area.delete(1.0, tk.END)

    def export_results(self):
        self.text_area_original.config(state='normal'); original = self.text_area_original.get(1.0, tk.END).strip(); self.text_area_original.config(state='disabled')
        translated = self.text_area_translated.get(1.0, tk.END).strip()
        if not original and not translated: messagebox.showwarning("Boş Sonuç", "Dışa aktarılacak çeviri bulunamadı."); return
        from tkinter import filedialog
        filename = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Metin dosyaları", "*.txt"), ("Tüm dosyalar", "*.*")])
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("... Orijinal Metin ...\n{original}\n\n... Çevrilmiş Metin ...\n{translated}\n")
                messagebox.showinfo("Başarılı", f"Sonuç şuraya kaydedildi:\n{filename}")
            except Exception as e: messagebox.showerror("Hata", f"Dosya kaydedilemedi: {e}")

class DirectOverlayWindow:
    def __init__(self, parent_gui, image, results, region, is_manga_mode=False):
        self.parent_gui = parent_gui
        self.is_manga_mode = is_manga_mode
        self.overlay_windows = []
        if is_manga_mode and results: self.create_multiple_overlays(image, results, region)
        else: self.create_single_overlay(image, results, region)
    
    def create_multiple_overlays(self, image, results, region):
        self.overlay_windows = []
        for i, result in enumerate(results):
            try:
                if 'translated' not in result or 'bbox' not in result: continue
                overlay_window = tk.Toplevel(); overlay_window.overrideredirect(True)
                overlay_window.attributes('-topmost', True); overlay_window.attributes('-alpha', 0.92)
                overlay_window.configure(bg='white')
                left, top, right, bottom = result['bbox']; width, height = right - left, bottom - top
                if width < 50 or height < 30: overlay_window.destroy(); continue
                screen_width, screen_height = overlay_window.winfo_screenwidth(), overlay_window.winfo_screenheight()
                x = max(0, min(region['left'] + left, screen_width - width)); y = max(0, min(region['top'] + top, screen_height - height))
                overlay_window.geometry(f"{width}x{height}+{x}+{y}")
                canvas = tk.Canvas(overlay_window, width=width, height=height, bg='white', highlightthickness=0); canvas.pack(fill=tk.BOTH, expand=True)
                canvas.create_rectangle(0, 0, width, height, fill='#FFFFFF', outline='#CCCCCC', width=1)
                font_size = self.calculate_optimal_font_size(result['translated'], width, height)
                self.draw_multiline_text(canvas, width//2, height//2, result['translated'], font_size, width-10, height-10)
                self.overlay_windows.append(overlay_window); self.bind_close_events(overlay_window)
                overlay_window.after(20000, lambda w=overlay_window: self.safe_close_window(w))
            except Exception as e: debug_print(f"Balon {i+1} overlay hatası: {e}")
        if self.overlay_windows: self.overlay_windows[0].focus_force(); self.setup_global_close_hotkeys()
    
    def calculate_optimal_font_size(self, text, width, height):
        if not text: return 12
        base_size = min(width, height) // 8
        char_count = len(text)
        if char_count > 100: base_size = max(8, base_size - 2)
        elif char_count > 50: base_size = max(10, base_size - 1)
        return max(8, min(16, base_size))
    
    def draw_multiline_text(self, canvas, x, y, text, font_size, max_width, max_height):
        import textwrap
        font = ('Segoe UI', font_size, 'bold')
        words = text.split();
        if not words: return
        char_width = font_size * 0.6; chars_per_line = max(1, int(max_width / char_width))
        lines = textwrap.wrap(text, width=chars_per_line);
        if not lines: lines = [text]
        line_height = font_size + 4; total_height = len(lines) * line_height
        start_y = y - (total_height / 2)
        for i, line in enumerate(lines):
            line_y = start_y + (i * line_height)
            canvas.create_text(x, line_y, text=line, fill='black', font=font, anchor='center')
    
    def bind_close_events(self, window):
        try:
            window.bind('<Escape>', lambda e, w=window: self.safe_close_window(w)); window.bind('<Delete>', lambda e, w=window: self.safe_close_window(w))
            window.bind('<Button-1>', lambda e, w=window: self.safe_close_window(w)); window.focus_set()
        except Exception as e: debug_print(f"Event binding hatası: {e}")
    
    def setup_global_close_hotkeys(self):
        try:
            import keyboard
            def close_all(): self.parent_gui.root.after(0, self.close_all_windows)
            keyboard.add_hotkey('esc', close_all); keyboard.add_hotkey('delete', close_all)
        except Exception as e: debug_print(f"Global hotkey hatası: {e}")
    
    def safe_close_window(self, window):
        try:
            if window and hasattr(window, 'winfo_exists') and window.winfo_exists():
                window.destroy()
                if window in self.overlay_windows: self.overlay_windows.remove(window)
        except Exception as e: debug_print(f"Pencere kapatma hatası: {e}")
    
    def close_all_windows(self):
        windows_to_close = self.overlay_windows.copy()
        for window in windows_to_close: self.safe_close_window(window)
        self.overlay_windows.clear()
    
    def create_single_overlay(self, image, results, region):
        try:
            self.window = tk.Toplevel(); self.window.overrideredirect(True)
            self.window.attributes('-topmost', True); self.window.attributes('-alpha', 0.95)
            self.window.configure(bg='white')
            x, y, w, h = region['left'], region['top'], region['width'], region['height']
            self.window.geometry(f"{w}x{h}+{x}+{y}")
            self.canvas = tk.Canvas(self.window, width=w, height=h, bg='white', highlightthickness=0); self.canvas.pack(fill=tk.BOTH, expand=True)
            self.tk_image = ImageTk.PhotoImage(image.resize((w, h))); self.canvas.create_image(0, 0, anchor='nw', image=self.tk_image)
            for result in results:
                if 'translated' in result and 'bbox' in result:
                    left, top, right, bottom = result['bbox']
                    self.canvas.create_rectangle(left, top, right, bottom, fill='white', outline='gray')
                    self.canvas.create_text(left + 4, top + 2, anchor='nw', text=result['translated'], fill='black', font=('Comic Sans MS', 13, 'bold italic'), width=(right - left - 8))
            self.window.after(20000, self.window.destroy); self.window.bind('<Escape>', lambda e: self.window.destroy()); self.window.bind('<Delete>', lambda e: self.window.destroy()); self.window.focus_force()
        except Exception as e: debug_print(f"Single overlay hatası: {e}")
def debug_print(message):
    print(f"🔍 DEBUG: {message}")
def main():
    try:
        root = tk.Tk()
        app = TranslatorGUI(root)
        root.mainloop()
    except Exception as e:
        if "admin" in str(e).lower() or "permission" in str(e).lower():
            print("❌ Uygulama başlatılamadı: Yönetici izni gerekiyor olabilir.")
            print("Lütfen programı yönetici olarak çalıştırmayı deneyin (sağ tık -> Yönetici olarak çalıştır).")
        else: print(f"❌ Uygulama başlatılamadı: {e}")
        input("Çıkmak için Enter'a basın...")

if __name__ == "__main__":
    main()


