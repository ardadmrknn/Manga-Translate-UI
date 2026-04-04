# Manga Translate UI

Windows odaklı, masaüstünde seçtiğiniz ekran bölgesinden metin okuyup anında çeviri yapan bir manga ve oyun çeviri aracı.

Uygulama; Tesseract, Google Cloud Vision veya Gemini ile OCR yapabilir, ardından metni Gemini, Google Cloud Translate veya yerel Gemma modeli ile çevirebilir. Sonuçları normal metin alanında gösterebilir veya overlay pencereleri olarak ekranın üstüne yerleştirebilir.

## Özellikler

- Seçili ekran alanından tek tıkla çeviri
- Sistem genelinde çalışan kısayol tuşları
- Manga modu ve oyun modu için farklı metin gruplama davranışı
- Üç OCR seçeneği:
  - Tesseract (local)
  - Google Cloud Vision
  - Gemini Vision
- Üç çeviri seçeneği:
  - Yerel Gemma (LiteRT-LM)
  - Gemini
  - Google Cloud Translate
- Overlay çeviri görünümü
- Çeviri geçmişi arama ve temizleme
- Sonucu dışa aktarma
- Düzeltmeleri BigQuery'ye gönderme desteği
- Kullanıcı ayarlarını saklama

## Ekran Akışı

1. Uygulamayı açın.
2. `F2` ile çevrilecek alanı seçin.
3. OCR ve çeviri motorunu belirleyin.
4. `F1` ile normal çeviri veya `F5` ile overlay çeviri çalıştırın.
5. Gerekirse çeviriyi düzenleyip düzeltme gönderin.

## Desteklenen Motorlar

### OCR

- `tesseract`: Yerel OCR, internet gerektirmez.
- `cloud_vision`: Google Cloud Vision ile daha stabil OCR.
- `gemini`: Görselden yüksek kaliteli metin çıkarımı.

### Çeviri

- `local_gemma`: Yerel model ile gizlilik odaklı çeviri.
- `gemini`: Daha doğal ve bağlama duyarlı çeviri.
- `google`: Hızlı ve düşük maliyetli bulut çevirisi.

## Gereksinimler

- Windows
- Python 3
- Tesseract OCR kurulu olmalı ve `PATH` içinde bulunmalı
- İsteğe bağlı olarak Google Cloud hesabı ve/veya Gemini API erişimi

## Kurulum

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Tesseract ayrıca sisteminize kurulmalıdır. Kurulumdan sonra `tesseract` komutu terminalden çalışmalıdır.

## Ortam Değişkenleri

Bulut servisleri kullanacaksanız anahtarları dosya içine yazmayın. Ortam değişkeni kullanın.

### Gemini

```powershell
$env:GOOGLE_API_KEY="YOUR_GEMINI_API_KEY"
```

### Google Cloud Vision / Translate / BigQuery

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS="C:\path\to\service-account.json"
```

### Yerel Gemma modeli

İsterseniz model yolunu ortam değişkeni ile verebilirsiniz:

```powershell
$env:LOCAL_LITERT_LM_MODEL_PATH="C:\path\to\gemma-4-E2B-it.litertlm"
```

Varsayılan olarak uygulama proje içindeki `models/gemma-4-E2B-it.litertlm` yolunu dener.

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
- `Esc`: Aktif seçim veya bazı overlay işlemlerini iptal et
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

- API key'ler kaynak koda gömülü değildir.
- Gemini anahtarı `GOOGLE_API_KEY` üzerinden okunur.
- Google Cloud kimlik bilgileri `GOOGLE_APPLICATION_CREDENTIALS` ile kullanılır.
- Aşağıdaki dosyalar `.gitignore` ile repodan hariç tutulur:
  - `.venv/`
  - `app.log`
  - `settings.json`
  - `translation_history.json`
  - `.env`
  - olası credential JSON dosyaları

## Notlar

- LiteRT-LM tarafında Windows desteği ortama göre sorun çıkarabilir. Yerel Gemma motoru bazı sistemlerde WSL2 veya Linux isteyebilir.
- Bulut motorları aktif değilse uygulama yine yerel Tesseract ile çalışabilir.
- Google servislerini kullanırken ilgili API'lerin açık olduğundan emin olun.

## Sorun Giderme

### `TesseractNotFoundError`

Tesseract kurulu değildir veya `PATH` içinde değildir.

### OCR çalışıyor ama çeviri boş geliyor

Seçtiğiniz çeviri motoru için gerekli ortam değişkeni tanımlı olmayabilir.

### Yerel Gemma çalışmıyor

Model dosyası yolu yanlış olabilir veya LiteRT-LM ortamınız Windows üzerinde uyumsuz olabilir.

## Lisans

Bu depo için henüz ayrı bir lisans dosyası eklenmemiştir.