# Aşama 7 — Sağlamlaştırma ve Ekstralar (Opsiyonel)

Bu aşamadaki maddeler birbirinden bağımsızdır. 🧑 Kullanıcıya hangilerini istediğini sor, sadece onları yap. Her biri için test yaz ve ayrı commit at.

## 7.1 Haftalık "yaşıyorum" mesajı (önerilir)
- Pazar 20:00 civarı (`last_heartbeat` 7 günden eskiyse) bir özet gönder:
  ```
  💚 Kamu İlan Botu çalışıyor
  Son 7 günde: 1.284 ilan tarandı, 9 bildirim gönderildi
  Kaynaklar: ✅ kamuilan ✅ ilan.gov ⚠️ iskur (2 gündür hata) ...
  ```
- Bunun için state'e haftalık sayaçlar ekle.
- Heartbeat state'i değiştirdiği için en az haftada bir commit olur; GitHub'ın 60 gün kuralı tamamen önlenir.

## 7.2 Son başvuru hatırlatması
- Bildirimi gönderilmiş ilanları state'te `notified` altında `deadline` ile sakla.
- Son başvuruya 2 gün kala, günde bir kez: "⏰ Yarın/2 gün sonra kapanıyor: …" hatırlatması.
- Hatırlatma ilan başına bir kez.

## 7.3 Telegram'dan filtre güncelleme (polling'siz)
- Workflow her çalışmada `getUpdates`'i `offset` ile çağırır (state'te `last_update_id`), sadece kayıtlı `chat_id`'den gelen mesajları işler.
- Komutlar: `/durum` (kaynak sağlığı), `/filtre` (mevcut filtreleri göster), `/sessiz 3s` (3 saat bildirim erteleme).
- Not: Yanıt anında değil, bir sonraki çalışmada (≤30 dk) gelir. Kullanıcıya bunu baştan söyle.
- Filtreyi Telegram'dan **değiştirme** bilinçli olarak yok; `config.yaml` tek doğru kaynak kalsın.

## 7.4 Birden çok kişi
- `TELEGRAM_CHAT_ID` virgülle ayrılmış birden çok ID kabul etsin (ör. KPSS'ye giren arkadaşlar). Herkes aynı filtreyi alır.
- Kişi başı farklı filtre istenirse `config.yaml`'a `profiles:` yapısı; bu daha büyük bir değişiklik, önce kullanıcıya sor.

## 7.5 Kaynak yapısı değişikliği alarmı
- Parser'ın döndürdüğü alanların doluluk oranını takip et (ör. kurum alanı önceden %95 doluydu, şimdi %0). Ani düşüşte tek seferlik uyarı gönder: "Site yapısı değişmiş olabilir".

## 7.6 Kod kalitesi
- `mypy --strict` (veya `pyright`) ekle, hataları temizle.
- Test kapsamı raporu (`pytest-cov`), kritik modüllerde (filters, runner, state) ≥%90.

## Kabul kriterleri
- [ ] Seçilen her madde için testler yeşil.
- [ ] `README.md` yeni özelliklerle güncellendi.
- [ ] `docs/ILERLEME.md` son durumu yansıtıyor.
