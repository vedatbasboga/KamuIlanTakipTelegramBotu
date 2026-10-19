# Aşama 2 — Telegram Bildirimi

## Amaç
Bot oluşturmak ve `notifier.py` ile Telegram'a düzgün biçimlendirilmiş mesaj göndermek.

## 🧑 KULLANICI — Bot oluşturma (Claude Code bu adımda durur ve bekler)
1. Telegram'da **@BotFather**'a `/newbot` yaz, bota bir ad ve `_bot` ile biten bir kullanıcı adı ver. Verilen **token**'ı sakla.
2. Oluşturduğun bota Telegram'dan herhangi bir mesaj at (`/start` yeterli).
3. Tarayıcıda `https://api.telegram.org/bot<TOKEN>/getUpdates` adresini aç. Yanıttaki `"chat":{"id": ...}` değeri senin **chat_id**'n.
4. Yerelde test için repo kökünde `.env` dosyası oluştur (git'e girmez):
   ```
   TELEGRAM_BOT_TOKEN=123456:ABC...
   TELEGRAM_CHAT_ID=123456789
   ```
5. Claude Code'a "token ve chat_id hazır, .env'de" de. **Token'ı sohbete yapıştırma.**

## Görevler (Claude Code)

### 2.1 `notifier.py`
- `TelegramNotifier(token, chat_id, client)`.
- `send(text: str) -> bool`: `POST https://api.telegram.org/bot{token}/sendMessage`, gövde: `chat_id`, `text`, `parse_mode="HTML"`, `disable_web_page_preview=True`.
- **HTML escape:** Başlık, kurum vb. tüm dinamik metinleri `html.escape` ile kaçır. Kurum adlarında `&`, `<` sık geçer.
- **429 (rate limit):** Yanıttaki `parameters.retry_after` kadar bekle, bir kez yeniden dene.
- **Mesaj uzunluğu:** Telegram sınırı 4096 karakter; aşan mesajı satır sınırından böl.
- Mesajlar arasında ~1 sn bekle (aynı sohbete art arda gönderim sınırı).
- Token **hiçbir log satırında görünmesin**; hata loglarken URL'yi maskele.
- `.env` desteği: Ek bağımlılık eklemeden, `__main__.py` içinde basit bir `.env` okuyucu (sadece ortam değişkeni yoksa doldurur).

### 2.2 Mesaj biçimi
Tek ilan:

```
🆕 <b>{kurum}</b>
{başlık}

🎓 Lisans · 📊 KPSS P3 · 📍 İZMİR
👥 12 kadro
⏳ Son başvuru: 28.10.2026 (9 gün kaldı)

🔗 <a href="{url}">İlana git</a> · <i>kamuilan.sbb.gov.tr</i>
```

- Boş alanların satırı/öğesi hiç gösterilmez.
- Son başvuruya ≤3 gün kaldıysa `⏳` yerine `⚠️`.
- Özet mesajı (ilan sayısı `max_messages_per_run`'ı aşınca): "📋 23 yeni ilan" başlığı altında `• kurum — başlık (link)` satırları, kaynağa göre gruplanmış.

### 2.3 Format fonksiyonları
`format_ilan(ilan, now) -> str` ve `format_digest(ilanlar, now) -> str` saf fonksiyonlar olsun (test edilebilir).

### 2.4 Test komutu
`python -m ilanbot --test-telegram`: "✅ Kamu İlan Botu bağlantı testi" mesajı ve örnek (sahte) bir ilan kartı gönderir.

### 2.5 Testler
- `tests/test_notifier.py`: `respx` ile sendMessage mock'u; 429 sonrası retry; HTML escape; 4096 bölme; token'ın log çıktısında olmadığı (caplog).
- Format testleri: boş alanlar, `⚠️` eşiği, digest gruplama.

## Kabul kriterleri
- [ ] `pytest -q` yeşil.
- [ ] 🧑 Kullanıcı `--test-telegram` ile telefonuna iki mesaj geldiğini onayladı.
- [ ] Token hiçbir dosyada, logda veya commit'te yok (`git grep` ile kontrol).
