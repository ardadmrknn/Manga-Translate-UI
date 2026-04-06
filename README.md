# Manga Çevirici

Masaüstünde seçtiğiniz bir ekran alanından metni okuyup hızlıca çeviren, Windows odaklı bir manga ve oyun çeviri uygulaması.

Uygulama; Tesseract, Google Cloud Vision veya Gemini ile OCR yapar. Ardından metni Gemini, Google Cloud Translate ya da uygun olduğunda Yerel Gemma (LiteRT-LM veya Ollama Gemma) ile çevirir. Sonuçlar metin panellerinde gösterilebilir veya overlay olarak ekran üstüne yerleştirilebilir.

## Öne Çıkan Özellikler

- Seçili ekran alanından tek tıkla çeviri
- Pencereye sığmayan ayar/kontrol bölümleri için dikey kaydırma (scroll)
- Global kısayollar (keyboard paketi kuruluysa)
- Manga ve oyun modu için farklı metin gruplama davranışı
- Üç OCR motoru: Tesseract, Cloud Vision, Gemini Vision
- Üç çeviri motoru: Yerel Gemma, Gemini, Google Cloud Translate
- Yerel Gemma kullanılabilirlik kontrolü:
  - Önce LiteRT-LM + `.litertlm` model dosyası denenir
  - LiteRT uygun değilse Ollama API üzerinden Gemma modeline otomatik fallback yapılır
  - Çeviri motoru otomatik olarak Gemini (öncelik) veya Google Cloud seçeneğine geçirilir
- Overlay çeviri görünümü
- Çeviri geçmişi (arama/temizleme)
- Sonuç dışa aktarma
- Düzeltmeleri BigQuery'ye gönderme desteği
- Kullanıcı ayarlarını kalıcı saklama

## Hızlı Kullanım

1. Uygulamayı başlatın.
2. `F2` ile çevrilecek alanı seçin.
3. OCR ve çeviri motorunu belirleyin.
4. `F1` ile normal çeviri, `F5` ile overlay çeviri çalıştırın.
5. Gerekirse çeviriyi düzenleyip düzeltme gönderin.

## Desteklenen Motorlar

### OCR

- `tesseract`: Yerel OCR, internet gerektirmez.
- `cloud_vision`: Google Cloud Vision ile daha kararlı OCR.
- `gemini`: Görselden yüksek kaliteli metin çıkarımı.

### Çeviri

- `local_gemma`: Yerel model ile gizlilik odaklı çeviri.
  - LiteRT-LM modeli varsa onu kullanır.
  - Yoksa Ollama'daki Gemma modeli ile çalışır.
- `gemini`: Bağlama duyarlı, akıcı çeviri.
- `google`: Hızlı ve düşük maliyetli bulut çevirisi.

## Gereksinimler

- Windows
- Python 3
- Tesseract OCR (sisteme kurulu ve `PATH` içinde olmalı)
- Yerel Gemma için (Windows'ta önerilen): Ollama + bir Gemma modeli
- İsteğe bağlı olarak Google Cloud hesabı ve/veya Gemini API erişimi

## Kurulum

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Tesseract ayrıca sisteme kurulmalıdır. Kurulumdan sonra `tesseract` komutunun terminalde çalıştığını doğrulayın.

## Ortam Değişkenleri

Bulut servislerini kullanıyorsanız anahtarları kaynak koda yazmak yerine ortam değişkenleri üzerinden verin.

### Gemini

```powershell
$env:GOOGLE_API_KEY="YOUR_GEMINI_API_KEY"
```

### Google Cloud Vision / Translate / BigQuery

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS="C:\path\to\service-account.json"
```

### Yerel Gemma modeli

Model yolunu isterseniz ortam değişkeniyle belirtebilirsiniz:

```powershell
$env:LOCAL_LITERT_LM_MODEL_PATH="C:\path\to\gemma-4-E2B-it.litertlm"
```

Varsayılan konum: `models/gemma-4-E2B-it.litertlm`

Windows'ta Ollama fallback kullanacaksanız:

```powershell
ollama pull gemma3:1b
```

İsteğe bağlı ortam değişkenleri:

```powershell
$env:OLLAMA_BASE_URL="http://127.0.0.1:11434"
$env:OLLAMA_MODEL="gemma3:1b"
```

## Çalıştırma

```powershell
py best_mangaceviri_gui.py
```

## Varsayılan Kısayollar

- `F1`: Çevir
- `F2`: Alan seç
- `F3`: Geçmişi aç
- `F4`: Sürekli çerçeveyi aç/kapat
- `F5`: Overlay çeviri
- `Delete`: Overlay penceresini kapat
- `Esc`: Aktif seçim veya overlay işlemlerini iptal et
- `Ctrl+Q`: Uygulamadan çık

## Proje Yapısı

```text
best_mangaceviri.py       Çekirdek OCR ve çeviri mantığı
best_mangaceviri_gui.py   Tkinter arayüzü
requirements.txt          Python bağımlılıkları
settings.json             Yerel kullanıcı ayarları (repoya girmez)
translation_history.json  Yerel çeviri geçmişi (repoya girmez)
app.log                   Yerel log dosyası (repoya girmez)
```

## Güvenlik

- API anahtarları kaynak koda gömülü değildir.
- Gemini anahtarı `GOOGLE_API_KEY` üzerinden okunur.
- Google Cloud kimlik bilgileri `GOOGLE_APPLICATION_CREDENTIALS` üzerinden kullanılır.
- `.venv`, ayar/geçmiş dosyaları ve olası kimlik bilgileri dosyaları repoya dahil edilmez.

## Notlar

- `requirements.txt` içinde `litert-lm`, Windows için bilinçli olarak hariç tutulmuştur (`platform_system != "Windows"`).
- Windows'ta Yerel Gemma varsayılan olarak Ollama fallback ile çalışır.
- Ollama'da bir Gemma modeli yoksa `local_gemma` seçeneği devre dışı kalır.

## Sorun Giderme

### `TesseractNotFoundError`

Tesseract kurulu değildir veya `PATH` içinde değildir.

### OCR çalışıyor ama çeviri boş geliyor

Seçtiğiniz çeviri motoru için gerekli ortam değişkeni tanımlı olmayabilir.

### Yerel Gemma seçeneği devre dışı görünüyor

Muhtemel nedenler:

- `litert-lm` paketi kurulu değil veya import edilemiyor
- Model dosyası bulunamıyor
- Ollama kurulu değil, çalışmıyor veya `PATH` içinde değil
- Ollama içinde Gemma modeli yok (ör: `ollama pull gemma3:1b`)

## Lisans

Bu depo için henüz ayrı bir lisans dosyası eklenmemiştir.
