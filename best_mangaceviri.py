# Genel kütüphaneler
import os
import json
import datetime
import platform
import logging
from PIL import Image
import mss
import html
import io
import pytesseract
import cv2
import numpy as np
from functools import lru_cache
from threading import Lock

# --- API Kütüphaneleri (Mevcut haliyle kalacak) ---
try:
    import google.generativeai as genai
except ImportError:
    genai = None
    print("UYARI: 'google.generativeai' kütüphanesi bulunamadı. Gemini API seçenekleri çalışmayacak.")
try:
    from google.cloud import translate_v2 as translate
except ImportError:
    translate = None
    print("UYARI: 'google-cloud-translate' kütüphanesi bulunamadı. Google Cloud Translator seçenekleri çalışmayacak.")
try:
    from google.cloud import vision
except ImportError:
    vision = None
    print("UYARI: 'google-cloud-vision' kütüphanesi bulunamadı. Google Cloud Vision OCR seçeneği çalışmayacak.")
try:
    from google.cloud import bigquery
except ImportError:
    bigquery = None
    print("UYARI: 'google-cloud-bigquery' kütüphanesi bulunamadı. Analiz verileri kaydedilemeyecek.")
try:
    import litert_lm
    LITERT_LM_IMPORT_ERROR = ""
except ImportError as import_error:
    litert_lm = None
    LITERT_LM_IMPORT_ERROR = str(import_error)


# DEBUG MODE
DEBUG_MODE = True
def debug_print(message):
    if DEBUG_MODE:
        print(f"🔍 DEBUG: {message}")

# Avoid leaking machine-specific absolute paths in source control.
DEFAULT_LOCAL_GEMMA_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "models",
    "gemma-4-E2B-it.litertlm",
)

# Suppress credential path debug logs from Google auth internals.
logging.getLogger("google.auth._default").setLevel(logging.WARNING)

# <<< DEĞİŞİKLİK YOK: TranslationHistory sınıfı olduğu gibi kalıyor.
class TranslationHistory:
    """Çeviri geçmişini yönetir"""
    def __init__(self, history_file="translation_history.json"):
        self.history_file = history_file
        self.history = self.load_history()
    
    def load_history(self):
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            debug_print(f"Geçmiş yüklenirken hata: {e}")
        return []
    
    def save_history(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            debug_print(f"Geçmiş kaydedilirken hata: {e}")
    
    def add_translation(self, original, translated, source_lang, target_lang, ocr_method, translator_engine):
        if not original.strip() or not translated.strip():
            return
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "original": original,
            "translated": translated,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "ocr_method": ocr_method,
            "translator_engine": translator_engine
        }
        for i, item in enumerate(self.history):
            if item["original"] == original and item["source_lang"] == source_lang and item["target_lang"] == target_lang:
                self.history[i] = entry
                self.save_history()
                return
        self.history.insert(0, entry)
        if len(self.history) > 100:
            self.history = self.history[:100]
        self.save_history()
    
    def get_history(self, limit=50):
        return self.history[:limit]
    
    def clear_history(self):
        self.history = []
        self.save_history()
    
    def search_history(self, query):
        query = query.lower()
        results = []
        for item in self.history:
            if (query in item["original"].lower() or 
                query in item["translated"].lower()):
                results.append(item)
        return results

class ScreenTranslator:
    def log_correction_to_bigquery(self, original_text, original_translation, corrected_translation, user_id="anonymous"):
        if not bigquery or not self.gcp_project_id:
            print("BigQuery istemcisi yapılandırılmamış. Düzeltme kaydedilemedi.")
            return

        try:
            client = bigquery.Client(project=self.gcp_project_id)
            # Tablonuzun tam yolu
            table_id = f"{self.gcp_project_id}.manga_translator_database.translation_word"

            rows_to_insert = [
                {
                    "original_text": original_text,
                    "original_translation": original_translation,
                    "corrected_translation": corrected_translation,
                    "user_id": user_id,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                }
            ]

            errors = client.insert_rows_json(table_id, rows_to_insert)
            if errors == []:
                print("Yeni çeviri düzeltmesi başarıyla BigQuery'ye kaydedildi.")
            else:
                print(f"BigQuery'ye veri eklenirken hata oluştu: {errors}")
        except Exception as e:
            print(f"BigQuery'ye bağlanırken bir hata oluştu: {e}")

    def __init__(self, local_model_path=None):
        # Önbellek ve hata takibi için değişkenler
        
        self.last_error = ""
        self.local_model_path = local_model_path or os.getenv("LOCAL_LITERT_LM_MODEL_PATH") or DEFAULT_LOCAL_GEMMA_MODEL_PATH
        self.local_llm_engine = None
        self.local_llm_error = ""
        self._local_llm_lock = Lock()
        self._local_llm_cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".litert_cache")
        
        # Çeviri geçmişi
        self.history = TranslationHistory()

        
        self.cloud_vision_client = None
        if vision:
            try:
                self.cloud_vision_client = vision.ImageAnnotatorClient()
                debug_print("✅ Google Cloud Vision istemcisi yapılandırıldı.")
            except Exception as e:
                debug_print(f"❌ Google Cloud Vision hatası: {e}. GOOGLE_APPLICATION_CREDENTIALS ortam değişkenini kontrol edin.")

        # --- Gemini API Kurulumu ---
        self.vision_model = None
        self.text_model = None
        if genai:
            try:
                API_KEY = os.getenv("GOOGLE_API_KEY")
                if not API_KEY: raise ValueError("GOOGLE_API_KEY ortam değişkeni bulunamadı!")
                genai.configure(api_key=API_KEY)
                self.vision_model = genai.GenerativeModel('gemini-1.5-flash')
                self.text_model = genai.GenerativeModel('gemini-1.5-flash')
                debug_print("✅ Gemini API modelleri yapılandırıldı.")
            except Exception as e:
                debug_print(f"❌ Gemini API hatası: {e}")


        # --- Google Cloud Translator Kurulumu ---
        self.google_translator_client = None
        if translate:
            try:
                self.google_translator_client = translate.Client()
                self.google_translator_client.get_languages(target_language='en')
                debug_print("✅ Google Cloud Translate istemcisi yapılandırıldı.")
            except Exception as e:
                debug_print(f"❌ Google Cloud hatası: {e}. GOOGLE_APPLICATION_CREDENTIALS ortam değişkenini kontrol edin.")

    def capture_screen(self, region):
        """Ekran görüntüsü yakalar"""
        try:
            with mss.mss() as sct: 
                sct_img = sct.grab(region)
                return Image.frombytes("RGB", sct_img.size, sct_img.rgb)
        except Exception as e: 
            self.last_error = f"Ekran yakalama hatası: {e}"
            return None


# MEVCUT _preprocess_image_for_ocr METODUNU SİLİN VE YERİNE AŞAĞIDAKİNİ EKLEYİN

    def _preprocess_image_for_ocr(self, image_cv, profile='normal'):
        """
        Seçilen profile göre geliştirilmiş görüntü ön işleme fonksiyonu.
        """
        if len(image_cv.shape) == 3:
            gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
        else:
            gray = image_cv.copy()

        debug_print(f"Ön işleme profili uygulanıyor: {profile}")
        processed = gray

        # Seçilen ön işleme profiline göre filtreleme
        if profile == 'denoise':
            # Çok grenli görüntüler için medyan filtre uygula
            processed = cv2.medianBlur(processed, 5)

        elif profile == 'sharpen':
            # Metinleri keskinleştirmek için
            kernel = np.array([[-1,-1,-1], 
                               [-1, 9,-1],
                               [-1,-1,-1]])
            processed = cv2.filter2D(processed, -1, kernel)

        elif profile == 'high_contrast':
            # Kontrastı artırmak için histogram eşitlemesi
            processed = cv2.equalizeHist(processed)

        # Temel gürültü azaltma işlemi her zaman uygulanır
        processed = cv2.fastNlMeansDenoising(processed, h=12, templateWindowSize=7, searchWindowSize=21)

        # Görüntü boyutlandırma (mevcut kodunuzdaki gibi)
        height, width = processed.shape
        if height < 300 or width < 300:
            scale_factor = max(300 / height, 300 / width, 1.5)
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            debug_print(f"Görüntü boyutu {scale_factor:.2f}x kadar artırılıyor.")
            processed = cv2.resize(processed, (new_width, new_height), interpolation=cv2.INTER_CUBIC)

        # İkili eşikleme (binary thresholding)
        _, processed = cv2.threshold(processed, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        if np.mean(processed) > 127:
            processed = cv2.bitwise_not(processed)
            debug_print("Görüntü, siyah metin / beyaz arka plan için ters çevrildi.")

        return processed

    def _ocr_with_cloud_vision(self, pil_image):
        """
        Google Cloud Vision API kullanarak OCR yapar ve Tesseract/EasyOCR'a benzer bir dict döndürür.
        """
        if not self.cloud_vision_client:
            debug_print("❌ Google Cloud Vision istemcisi başlatılamadı.")
            return {'level': [], 'left': [], 'top': [], 'width': [], 'height': [], 'text': [], 'conf': []}

        buffered = io.BytesIO()
        pil_image.save(buffered, format="PNG")
        image_bytes = buffered.getvalue()

        image = vision.Image(content=image_bytes)

        debug_print("Google Cloud Vision API çağrılıyor (DOCUMENT_TEXT_DETECTION)...")
        try:
            response = self.cloud_vision_client.document_text_detection(image=image)
            ocr_data = {'level': [], 'left': [], 'top': [], 'width': [], 'height': [], 'text': [], 'conf': []}

            if response.full_text_annotation:
                debug_print(f"Cloud Vision tam metin: {response.full_text_annotation.text[:100]}...")
                for page in response.full_text_annotation.pages:
                    for block in page.blocks:
                        for paragraph in block.paragraphs:
                            for word in paragraph.words:
                                word_text = ''.join([symbol.text for symbol in word.symbols])
                                vertices = word.bounding_box.vertices
                                x_coords, y_coords = [v.x for v in vertices], [v.y for v in vertices]
                                x, y = min(x_coords), min(y_coords)
                                w, h = max(x_coords) - x, max(y_coords) - y
                                confidence = word.confidence * 100

                                if word_text.strip():
                                    ocr_data['level'].append(5)
                                    ocr_data['left'].append(x)
                                    ocr_data['top'].append(y)
                                    ocr_data['width'].append(w)
                                    ocr_data['height'].append(h)
                                    ocr_data['text'].append(word_text)
                                    ocr_data['conf'].append(int(confidence))
            
            debug_print(f"Cloud Vision toplam {len(ocr_data['text'])} metin parçası çıkardı.")
            return ocr_data

        except Exception as e:
            debug_print(f"❌ Cloud Vision API hatası: {e}")
            import traceback
            debug_print(f"❌ Cloud Vision detaylı hata: {traceback.format_exc()}")
            return {'level': [], 'left': [], 'top': [], 'width': [], 'height': [], 'text': [], 'conf': []}
# BU YENİ FONKSİYONU ScreenTranslator SINIFININ İÇİNE EKLEYİN

    def _find_and_ocr_bubbles(self, pil_image, ocr_method, preprocessing_profile, lang_code, gemini_quality):
        """
        Geliştirilmiş konuşma balonu tespit etme ve OCR işlemi.
        Manga sayfalarındaki beyaz konuşma balonlarını daha etkili şekilde bulur.
        """
        debug_print("Geliştirilmiş konuşma balonu tespit ve OCR işlemi başlatıldı.")
        open_cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)

        # Çoklu threshold yaklaşımı ile balonları tespit et
        results = []
        
        # 1. Yöntem: Adaptif threshold
        adaptive_thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 15, 10)
        
        # 2. Yöntem: Otsu threshold
        _, otsu_thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # 3. Yöntem: Sabit threshold (beyaz alanlar için)
        _, fixed_thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        
        # Tüm threshold sonuçlarını birleştir
        combined = cv2.bitwise_or(cv2.bitwise_or(adaptive_thresh, otsu_thresh), fixed_thresh)
        
        # Morfolojik işlemler ile gürültüyü azalt
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)
        combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN, kernel)
        
        # Konturları bul
        contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        debug_print(f"Toplam {len(contours)} kontur bulundu.")
        
        # Konturları filtrele ve sırala
        valid_contours = []
        image_area = pil_image.width * pil_image.height
        
        for contour in contours:
            area = cv2.contourArea(contour)
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / h if h > 0 else 0
            
            # Filtreleme kriterleri
            min_area = 800  # Minimum balon boyutu
            max_area = image_area * 0.6  # Maksimum balon boyutu
            min_width = 30
            min_height = 20
            max_aspect_ratio = 8  # Çok uzun/ince balonları filtrele
            
            if (min_area < area < max_area and 
                w > min_width and h > min_height and 
                aspect_ratio < max_aspect_ratio):
                
                # Konuşma balonu olma olasılığını kontrol et
                if self._is_likely_speech_bubble(gray, x, y, w, h):
                    valid_contours.append((contour, area, x, y, w, h))
        
        debug_print(f"Filtreleme sonrası {len(valid_contours)} geçerli balon bulundu.")
        
        # Manga okuma sırasına göre sırala (sağdan sola, yukarıdan aşağıya)
        valid_contours.sort(key=lambda item: (item[3], -item[2]))  # y koordinatı, sonra -x koordinatı
        
        for i, (contour, area, x, y, w, h) in enumerate(valid_contours):
            debug_print(f"Balon {i+1}/{len(valid_contours)} işleniyor: [{x},{y},{w},{h}]")
            
            # Balonu biraz genişlet (padding)
            padding = 5
            x_pad = max(0, x - padding)
            y_pad = max(0, y - padding)
            w_pad = min(pil_image.width - x_pad, w + 2*padding)
            h_pad = min(pil_image.height - y_pad, h + 2*padding)
            
            # Balonun içeriğini kırp
            bubble_image_pil = pil_image.crop((x_pad, y_pad, x_pad + w_pad, y_pad + h_pad))
            
            # OCR işlemi
            original_text = ""
            try:
                if ocr_method == 'tesseract':
                    bubble_cv = cv2.cvtColor(np.array(bubble_image_pil), cv2.COLOR_RGB2BGR)
                    processed_img = self._preprocess_image_for_ocr(bubble_cv, profile=preprocessing_profile)
                    
                    # Manga için özel Tesseract konfigürasyonu
                    custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,!?-:;\'\" '
                    original_text = pytesseract.image_to_string(processed_img, lang=lang_code, config=custom_config).strip()
                    
                elif ocr_method == 'gemini':
                    original_text = self.get_text_from_image_gemini(bubble_image_pil, quality=gemini_quality)
                    
                elif ocr_method == 'cloud_vision':
                    ocr_data = self._ocr_with_cloud_vision(bubble_image_pil)
                    original_text = " ".join(ocr_data.get('text', [])).strip()
                    
            except Exception as e:
                debug_print(f"OCR hatası balon {i+1} için: {e}")
                continue
            
            # Metin temizleme
            original_text = self._clean_ocr_text(original_text)
            
            if original_text and len(original_text.strip()) > 1:  # En az 2 karakter
                debug_print(f"✅ Balon {i+1} başarılı: '{original_text[:50]}...'")
                results.append({
                    'original': original_text, 
                    'bbox': (x_pad, y_pad, x_pad + w_pad, y_pad + h_pad),
                    'confidence': self._calculate_text_confidence(original_text)
                })
            else:
                debug_print(f"⚠️ Balon {i+1} boş veya geçersiz metin")
        
        debug_print(f"Toplam {len(results)} balon başarıyla işlendi.")
        return results

    def _is_likely_speech_bubble(self, gray_image, x, y, w, h):
        """Verilen bölgenin konuşma balonu olma olasılığını değerlendirir"""
        try:
            # Bölgeyi kırp
            roi = gray_image[y:y+h, x:x+w]
            if roi.size == 0:
                return False
            
            # Ortalama parlaklık (beyaz alanlar daha parlak)
            mean_brightness = np.mean(roi)
            
            # Kenar yoğunluğu (balonların genelde belirgin kenarları var)
            edges = cv2.Canny(roi, 50, 150)
            edge_density = np.sum(edges > 0) / (w * h)
            
            # Değerlendirme kriterleri
            brightness_threshold = 180  # Beyaz alanlar için
            edge_density_threshold = 0.05  # Minimum kenar yoğunluğu
            
            return mean_brightness > brightness_threshold and edge_density > edge_density_threshold
            
        except Exception as e:
            debug_print(f"Balon değerlendirme hatası: {e}")
            return False

    def _clean_ocr_text(self, text):
        """OCR sonucunu temizler"""
        if not text:
            return ""
        
        # Gereksiz karakterleri temizle
        import re
        # Sadece harf, rakam ve temel noktalama işaretlerini tut
        cleaned = re.sub(r'[^\w\s.,!?\'\":;-]', '', text)
        
        # Çoklu boşlukları tek boşluğa dönüştür
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        return cleaned.strip()

    def _calculate_text_confidence(self, text):
        """Metnin kalitesini değerlendirir"""
        if not text:
            return 0
        
        # Basit güven skoru hesaplama
        score = 50  # Başlangıç skoru
        
        # Uzunluk bonusu
        if len(text) > 5:
            score += 20
        
        # Harf oranı
        alpha_ratio = sum(c.isalpha() for c in text) / len(text)
        score += alpha_ratio * 30
        
        # Kelime sayısı
        word_count = len(text.split())
        if word_count > 1:
            score += min(word_count * 5, 20)
        
        return min(score, 100)
    def _group_text_blocks(self, ocr_data, line_threshold_ratio=0.7, mode='game'):
        """
        Akıllı Metin Gruplama Algoritması.
        'game' (soldan sağa) veya 'manga' (sağdan sola) modu için ayrı mantıklar içerir.
        """
        debug_print(f"Akıllı Metin Gruplama başlıyor (Mod: {mode})...")
        blocks = []
        
        # 1. Adım: OCR verisinden geçerli blokları filtrele ve oluştur (Değişiklik yok)
        for i in range(len(ocr_data.get('text', []))):
            text = ocr_data['text'][i].strip()
            conf = int(ocr_data['conf'][i]) if ocr_data['conf'][i] != -1 else 0
            if conf > 30 and text:
                x, y, w, h = ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i]
                if w > 5 and h > 5:
                    blocks.append({'text': text, 'bbox': (x, y, x + w, y + h), 'conf': conf})

        if not blocks:
            debug_print("Filtrelemeden sonra işlenecek blok bulunamadı.")
            return []

        # 2. Adım: Blokları okuma sırasına göre sırala (Değişiklik yok)
        if mode == 'manga':
            blocks.sort(key=lambda b: (b['bbox'][1], -b['bbox'][0]))
        else:
            blocks.sort(key=lambda b: (b['bbox'][1], b['bbox'][0]))

        # 3. Adım: Blokları satırlara ayır (Değişiklik yok)
        lines = []
        if not blocks: return []
        current_line = [blocks[0]]
        for block in blocks[1:]:
            prev_block_bbox = current_line[-1]['bbox']
            vertical_distance = abs(block['bbox'][1] - prev_block_bbox[1])
            prev_block_height = prev_block_bbox[3] - prev_block_bbox[1]
            if vertical_distance < (prev_block_height * line_threshold_ratio):
                current_line.append(block)
            else:
                lines.append(current_line)
                current_line = [block]
        if current_line: lines.append(current_line)

        for i, line in enumerate(lines):
            if mode == 'manga':
                lines[i] = sorted(line, key=lambda b: b['bbox'][0], reverse=True)
            else:
                lines[i] = sorted(line, key=lambda b: b['bbox'][0])
        
        # 4. Adım: Satırları paragraflara/konuşma balonlarına grupla (YENİ VE FARKLI MANTIK)
        if not lines: return []
        paragraphs = []
        current_paragraph = [lines[0]]

        if mode == 'manga':
            # --- MANGA MODU İÇİN ÖZEL, KATI GRUPLAMA MANTIĞI ---
            debug_print("Manga modu için katı gruplama uygulanıyor...")
            for i in range(1, len(lines)):
                prev_line_blocks = current_paragraph[-1]
                current_line_blocks = lines[i]

                avg_height_prev = sum(b['bbox'][3] - b['bbox'][1] for b in prev_line_blocks) / len(prev_line_blocks)
                prev_bottom = max(b['bbox'][3] for b in prev_line_blocks)
                current_top = min(b['bbox'][1] for b in current_line_blocks)
                vertical_gap = current_top - prev_bottom

                prev_left = min(b['bbox'][0] for b in prev_line_blocks)
                prev_right = max(b['bbox'][2] for b in prev_line_blocks)
                current_left = min(b['bbox'][0] for b in current_line_blocks)
                current_right = max(b['bbox'][2] for b in current_line_blocks)
                
                horizontal_overlap = max(0, min(prev_right, current_right) - max(prev_left, current_left))
                min_width = min(prev_right - prev_left, current_right - current_left)
                
                # Birleştirme Koşulu: Dikey olarak çok yakın OLMALI VE yatay olarak ciddi şekilde üst üste binmeli.
                is_vertically_close = vertical_gap < (avg_height_prev * 1.5)
                has_strong_overlap = (horizontal_overlap / min_width) > 0.5 if min_width > 0 else False

                if is_vertically_close and has_strong_overlap:
                    current_paragraph.append(lines[i])
                else:
                    paragraphs.append(current_paragraph)
                    current_paragraph = [lines[i]]
        else:
            # --- OYUN MODU İÇİN ESKİ, DAHA ESNEK GRUPLAMA MANTIĞI ---
            debug_print("Oyun modu için esnek gruplama uygulanıyor...")
            for i in range(1, len(lines)):
                prev_line = lines[i-1]
                current_line = lines[i]
                avg_height_prev_line = sum(b['bbox'][3] - b['bbox'][1] for b in prev_line) / len(prev_line)
                prev_line_bottom = max(b['bbox'][3] for b in prev_line)
                current_line_top = min(b['bbox'][1] for b in current_line)
                vertical_gap = current_line_top - prev_line_bottom
                is_vertically_close = vertical_gap < (avg_height_prev_line * 1.8)
                if is_vertically_close:
                    current_paragraph.append(current_line)
                else:
                    paragraphs.append(current_paragraph)
                    current_paragraph = [current_line]

        if current_paragraph:
            paragraphs.append(current_paragraph)
        debug_print(f"{len(paragraphs)} adet paragraf/konuşma balonu tespit edildi.")

        # 5. Adım: Her paragraftaki metinleri birleştirerek nihai grupları oluştur (Değişiklik yok)
        final_groups = []
        for i, paragraph in enumerate(paragraphs):
            all_blocks_in_paragraph = [block for line in paragraph for block in line]
            if not all_blocks_in_paragraph: continue
            combined_text = ' '.join(b['text'] for b in all_blocks_in_paragraph)
            if not combined_text: continue
            min_x = min(b['bbox'][0] for b in all_blocks_in_paragraph)
            min_y = min(b['bbox'][1] for b in all_blocks_in_paragraph)
            max_x = max(b['bbox'][2] for b in all_blocks_in_paragraph)
            max_y = max(b['bbox'][3] for b in all_blocks_in_paragraph)
            final_groups.append({'original': combined_text, 'bbox': (min_x, min_y, max_x, max_y)})
            debug_print(f"✅ Final Grup {i+1} oluşturuldu: '{combined_text}'")
            
        return final_groups
    def capture_and_translate_with_text_detection(self, monitor_region, source_lang, target_lang, ocr_method, gemini_quality, translator_engine, preprocessing_profile='normal', layout_mode='game'):
        """Ekran görüntüsü alır, seçilen moda göre metin bloklarını bulur, çevirir ve sonuçları döndürür."""
        img_pil = self.capture_screen(monitor_region)
        if not img_pil:
            return [{'original': self.last_error, 'translated': '', 'bbox': (0,0,0,0)}]

        grouped_blocks = []

        if layout_mode == 'manga':
            # --- YENİ MANGA MODU MANTIĞI ---
            # Önce konuşma balonlarını bul, sonra içlerini tek tek OCR'dan geçir.
            lang_code_map = {"English": "eng", "Japanese": "jpn+eng", "Korean": "kor+eng", "Chinese": "chi_sim+eng"}
            lang_code = lang_code_map.get(source_lang, 'eng')

            grouped_blocks = self._find_and_ocr_bubbles(
                img_pil, ocr_method, preprocessing_profile, lang_code, gemini_quality
            )
        else:
            # --- ESKİ OYUN MODU MANTIĞI (DEĞİŞİKLİK YOK) ---
            img_cv = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
            ocr_data = {}
            if ocr_method == 'tesseract':
                processed_img = self._preprocess_image_for_ocr(img_cv, profile=preprocessing_profile)
                lang_code_map = {"English": "eng", "Japanese": "jpn+eng", "Korean": "kor+eng", "Chinese": "chi_sim+eng"}
                lang_code = lang_code_map.get(source_lang, 'eng')
                custom_config = r'--oem 3 --psm 11'
                ocr_data = pytesseract.image_to_data(processed_img, lang=lang_code, config=custom_config, output_type=pytesseract.Output.DICT)
            elif ocr_method == 'cloud_vision':
                ocr_data = self._ocr_with_cloud_vision(img_pil)
            elif ocr_method == 'gemini':
                text = self.get_text_from_image_gemini(img_pil, quality=gemini_quality)
                # Gemini tüm metni tek blokta verdiği için direkt çevirip dönüyoruz
                translated_text = self.translate_text(text, source_lang, target_lang, translator_engine)
                if text:
                    self.history.add_translation(text, translated_text, source_lang, target_lang, ocr_method, translator_engine)
                return [{'original': text, 'translated': translated_text, 'bbox': (0,0,monitor_region['width'],monitor_region['height'])}]

            grouped_blocks = self._group_text_blocks(ocr_data, mode=layout_mode)

        debug_print(f"Toplam {len(grouped_blocks)} mantıksal metin bloğu bulundu.")

        # Çeviri işlemi her iki mod için de ortaktır
        results = []
        for block in grouped_blocks:
            original_text = block['original']
            if not original_text.strip():
                continue
            translated_text = self.translate_text(original_text, source_lang, target_lang, translator_engine)
            if translated_text:
                block['translated'] = translated_text
                results.append(block)
                self.history.add_translation(original_text, translated_text, source_lang, target_lang, ocr_method, translator_engine)

        debug_print(f"Toplam {len(results)} blok başarıyla çevrildi.")
        return results
    @lru_cache(maxsize=1000)
    def translate_text(self, text, source_lang, target_lang, engine='gemini'):
        """
        Metni belirtilen motor ile çevirir. 
        Son 1000 çeviriyi LRU önbelleğinde saklar.
        """
        if not text: 
            return ""

        # Not: Eski manuel cache kontrolü (if cache_key in self.translation_cache...)
        # @lru_cache dekoratörü sayesinde artık gerekli değil.

        translated = ""
       
        if engine == 'google':
            translated = self.translate_text_with_google(text, source_lang, target_lang)
        elif engine in ('local_gemma', 'mediapipe_local'):
            translated = self.translate_text_with_local_gemma(text, source_lang, target_lang)
        else: # Varsayılan Gemini
            translated = self.translate_text_with_gemini(text, source_lang, target_lang)
        
        # Not: Önbelleğe manuel ekleme (self.translation_cache[cache_key] = translated)
        # @lru_cache dekoratörü sayesinde artık gerekli değil.
        
        return translated

    def _build_local_llm_error_message(self, error):
        message = f"Yerel Gemma modeli başlatılamadı veya yanıt üretemedi: {error}"
        if platform.system() == 'Windows':
            message += " LiteRT-LM Python tarafında Windows desteği resmi olarak tam oturmadığı için WSL2 ya da Linux ortamı gerekebilir."
        return message

    def get_local_gemma_availability(self):
        if litert_lm is None:
            reason = "litert-lm paketi kurulu değil."
            if LITERT_LM_IMPORT_ERROR:
                reason += f" Import hatası: {LITERT_LM_IMPORT_ERROR}"
            return False, reason
        if not os.path.exists(self.local_model_path):
            return False, f"Model dosyası bulunamadı: {self.local_model_path}"
        return True, ""

    def _ensure_local_litert_engine(self):
        if self.local_llm_engine is not None:
            return self.local_llm_engine

        with self._local_llm_lock:
            if self.local_llm_engine is not None:
                return self.local_llm_engine

            local_gemma_available, unavailable_reason = self.get_local_gemma_availability()
            if not local_gemma_available:
                raise RuntimeError(unavailable_reason)

            os.makedirs(self._local_llm_cache_dir, exist_ok=True)

            try:
                if hasattr(litert_lm, 'set_min_log_severity') and hasattr(litert_lm, 'LogSeverity'):
                    litert_lm.set_min_log_severity(litert_lm.LogSeverity.ERROR)

                self.local_llm_engine = litert_lm.Engine(
                    self.local_model_path,
                    backend=litert_lm.Backend.CPU,
                    max_num_tokens=256,
                    cache_dir=self._local_llm_cache_dir,
                )
                self.local_llm_error = ""
                debug_print(f"✅ Yerel Gemma modeli hazır: {self.local_model_path}")
            except Exception as e:
                self.local_llm_error = self._build_local_llm_error_message(e)
                raise RuntimeError(self.local_llm_error) from e

        return self.local_llm_engine

    def _extract_litert_text(self, response):
        parts = []
        for item in response.get('content', []):
            if item.get('type') == 'text' and item.get('text'):
                parts.append(item['text'])
        return ''.join(parts).strip()

    def translate_text_with_local_gemma(self, text, source_lang, target_lang):
        if not text:
            return ""

        engine = self._ensure_local_litert_engine()
        system_messages = [
            {
                'role': 'system',
                'content': [
                    {
                        'type': 'text',
                        'text': 'You are an expert manga and game translator. Reply with translation only.'
                    }
                ]
            }
        ]
        prompt = (
            f"Translate the following text from {source_lang} to {target_lang}. "
            "Return only the translated text. Preserve tone, names, and speech bubble brevity when possible.\n\n"
            f"{text}"
        )

        try:
            with engine.create_conversation(messages=system_messages) as conversation:
                response = conversation.send_message(
                    {
                        'role': 'user',
                        'content': [
                            {
                                'type': 'text',
                                'text': prompt,
                            }
                        ],
                    }
                )
            translated_text = self._extract_litert_text(response)
            if not translated_text:
                raise RuntimeError('Model boş yanıt döndürdü.')
            return translated_text
        except Exception as e:
            self.local_llm_error = self._build_local_llm_error_message(e)
            raise RuntimeError(self.local_llm_error) from e
    
    def get_text_from_image_gemini(self, pil_image, quality='normal'):
        if not self.vision_model: return "GEMINI_API_ERROR"
        try:
            img_to_send = pil_image.copy()
            if quality == 'normal': img_to_send.thumbnail((1560, 1080), Image.Resampling.LANCZOS)
            prompt = "Bu görüntüdeki tüm metni çıkar. Yanıtında sadece ve sadece bu görüntüden çıkardığın metin olsun, başka hiçbir ek açıklama veya cümle kullanma."
            response = self.vision_model.generate_content([prompt, img_to_send])
            return response.text.strip()
        except Exception as e:
            debug_print(f"❌ Gemini OCR hatası: {e}")
            return ""

    def get_text_from_image_tesseract(self, pil_image, source_lang='English'):
        lang_code_map = {
            "English": "eng", "Japanese": "jpn+eng", "Korean": "kor+eng", 
            "Chinese": "chi_sim+eng", "Spanish": "spa+eng", "French": "fra+eng"
        }
        lang_code = lang_code_map.get(source_lang, 'eng')
        
        try:
            img_cv = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            processed_img = self._preprocess_image_for_ocr(img_cv, method='adaptive')
            
            # psm 11 (dağınık metin) manga için daha iyi sonuçlar verebilir.
            custom_config = r'--oem 3 --psm 11'
            
            return pytesseract.image_to_string(processed_img, lang=lang_code, config=custom_config).strip()
            
        except pytesseract.TesseractNotFoundError:
            return "TESSERACT_ERROR"
        except Exception as e:
            debug_print(f"❌ Lokal OCR hatası: {e}")
            return ""


    def translate_text_with_gemini(self, text, source_lang, target_lang):
        if not text or not self.text_model: return ""
        try:
            prompt = f"Bu metni '{source_lang}' dilinden '{target_lang}' diline çevir. Yanıtında sadece ve sadece çevrilmiş metin bulunsun. Manga, anime, oyun diline uygun, doğal ve akıcı çevir:\n\n{text}"
            response = self.text_model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            debug_print(f"❌ Gemini Çeviri hatası: {e}")
            return ""


    def translate_text_with_google(self, text, source_lang, target_lang):
        if not text or not self.google_translator_client: return ""
        target_lang_map = {"Turkish": "tr", "English": "en", "Spanish": "es", "French": "fr", "German": "de", "Italian": "it", "Portuguese": "pt", "Russian": "ru", "Arabic": "ar"}
        source_lang_map = {"English": "en", "Japanese": "ja", "Korean": "ko", "Chinese": "zh-CN", "Spanish": "es", "French": "fr"}
        target_lang_code, source_lang_code = target_lang_map.get(target_lang, "tr"), source_lang_map.get(source_lang)
        if not source_lang_code: return f"Google için desteklenmeyen kaynak dil: {source_lang}"
        
        try:
            result = self.google_translator_client.translate(text, target_language=target_lang_code, source_language=source_lang_code)
            translated_text = result['translatedText']
            unescaped_text = html.unescape(translated_text)
            return unescaped_text
        except Exception as e:
            return f"Google Çeviri Hatası: {str(e)}"

    # MEVCUT capture_and_translate_with_text_detection METODUNU SİLİN VE YERİNE AŞAĞIDAKİNİ EKLEYİN

# MEVCUT capture_and_translate_with_text_detection METODUNU SİLİN VE YERİNE AŞAĞIDAKİNİ EKLEYİN

    def capture_and_translate_with_text_detection(self, monitor_region, source_lang, target_lang, ocr_method, gemini_quality, translator_engine, preprocessing_profile='normal', layout_mode='game'):
        """Ekran görüntüsü alır, metin bloklarını gruplar, çevirir ve sonuçları döndürür."""
        img_pil = self.capture_screen(monitor_region)
        if not img_pil:
            return [{'original': self.last_error, 'translated': '', 'bbox': (0,0,0,0)}]

        img_cv = None
        if ocr_method == 'tesseract':
            img_cv = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

        debug_print(f"Seçilen OCR Yöntemi: {ocr_method}. Metinler okunuyor...")
        ocr_data = {}

        if ocr_method == 'tesseract':
            if img_cv is None:
                img_cv = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
            processed_img = self._preprocess_image_for_ocr(img_cv, profile=preprocessing_profile)

            lang_code_map = {
                "English": "eng", "Japanese": "jpn+eng", "Korean": "kor+eng",
                "Chinese": "chi_sim+eng", "Spanish": "spa+eng", "French": "fra+eng",
                "Turkish": "tur+eng"
            }
            lang_code = lang_code_map.get(source_lang, 'eng')

            custom_config = r'--oem 3 --psm 11'

            debug_print(f"Tesseract başlıyor: dil={lang_code}, config={custom_config}")
            ocr_data = pytesseract.image_to_data(processed_img, lang=lang_code, config=custom_config, output_type=pytesseract.Output.DICT)

            valid_texts = [text for text, conf in zip(ocr_data['text'], ocr_data['conf']) if text.strip() and int(conf) > 0]
            debug_print(f"Tesseract {len(valid_texts)} geçerli metin buldu: {valid_texts[:5]}")

        elif ocr_method == 'cloud_vision':
            ocr_data = self._ocr_with_cloud_vision(img_pil)

        elif ocr_method == 'gemini':
            text = self.get_text_from_image_gemini(img_pil, quality=gemini_quality)
            translated_text = self.translate_text(text, source_lang, target_lang, translator_engine)
            if text:
                 self.history.add_translation(text, translated_text, source_lang, target_lang, ocr_method, translator_engine)
            return [{'original': text, 'translated': translated_text, 'bbox': (0,0,monitor_region['width'],monitor_region['height'])}]
        else:
            debug_print(f"Bilinmeyen OCR yöntemi: {ocr_method}")
            return []

        debug_print(f"{len(ocr_data.get('text', []))} metin parçası bulundu. Gruplama başlıyor...")

        # YENİ KOD: Layout modunu metin gruplama fonksiyonuna iletiyoruz
        grouped_blocks = self._group_text_blocks(ocr_data, mode=layout_mode)

        debug_print(f"{len(grouped_blocks)} mantıksal metin bloğu oluşturuldu.")

        results = []
        for block in grouped_blocks:
            original_text = block['original']
            if not original_text.strip():
                continue

            translated_text = self.translate_text(original_text, source_lang, target_lang, translator_engine)
            if translated_text:
                block['translated'] = translated_text
                results.append(block)
                self.history.add_translation(original_text, translated_text, source_lang, target_lang, ocr_method, translator_engine)

        debug_print(f"Toplam {len(results)} blok başarıyla çevrildi.")
        return results
    def get_translation_history(self, limit=50):
        """Çeviri geçmişini döndürür"""
        return self.history.get_history(limit)
    
    def clear_translation_history(self):
        """Çeviri geçmişini temizler"""
        self.history.clear_history()
    
    def search_translation_history(self, query):
        """Çeviri geçmişinde arama yapar"""
        return self.history.search_history(query)

    def close(self):
        with self._local_llm_lock:
            if self.local_llm_engine is None:
                return

            exit_method = getattr(self.local_llm_engine, '__exit__', None)
            if callable(exit_method):
                exit_method(None, None, None)
            self.local_llm_engine = None
