# Aşama 5 — Filtre, Dedup ve Orkestrasyon

## Amaç
Tüm parçaları `runner.py`'de birleştirmek: kaynakları çalıştır → yenileri bul → filtrele → gönder → state'i güncelle.

## 5.1 `filters.py`
`matches(ilan, filters) -> tuple[bool, str]` (ikinci değer: neden, debug logu için).

Mantık (hepsi VE ile bağlanır; her kural kendi listesi boşsa atlanır):
- **education_levels:** İlanın düzeylerinden en az biri listede olmalı. İlanın düzeyi boşsa → `filtre_belirsizse_gonder`'e göre karar.
- **kpss_types:** Aynı mantık.
- **locations:** Aynı mantık. Ek olarak "Türkiye geneli", "tüm iller" gibi ifadeler her il filtresiyle eşleşir.
- **include_keywords:** Başlık + kurum + özet içinde en az biri (Türkçe-duyarlı, büyük/küçük harf duyarsız).
- **exclude_keywords:** Biri geçerse **her zaman** elenir (belirsizlik kuralı burada uygulanmaz).

## 5.2 `runner.py` akışı

```
state = load_state()
for source in enabled_sources:
    try:
        items = source.list_items(client)          # veya fetch
    except Exception:
        state.sources[name].consecutive_failures += 1
        log; continue
    new = [i for i in items if i.key not in state.seen]

    if not state.sources[name].bootstrapped:       # kural 4: sessiz ilk çalışma
        mark all items seen; bootstrapped = True
        log "X ilan sessizce kaydedildi"; continue

    new = [source.enrich(i) for i in new[:20]]     # gerekiyorsa
    for i in new: mark seen (filtreden geçse de geçmese de)
    to_send += [i for i in new if matches(i)]
    update health (failures=0, last_success, last_count)

send (tek tek ya da digest)
prune; save_state()
```

Önemli ayrıntılar:
- **Gönderim başarısızsa** o ilanları `seen`'den geri al, böylece bir sonraki çalışmada tekrar denenir. (Tersi, yani gönderilmeyen ilanın kaybolması, en kötü sonuçtur.)
- Filtreden geçmeyen ilanlar da `seen`'e yazılır, yoksa her çalışmada tekrar değerlendirilir. Kullanıcı filtreyi değiştirirse eski ilanlar geriye dönük gelmez; bunu `config.yaml` yorumunda belirt.
- Aynı ilanın birden çok kaynakta çıkması (ör. hem kamuilan hem ilan.gov) olağan. **Kaynaklar arası tekrar önleme** için: Kurum adı + başlık normalize edilip (küçük harf, noktalama ve boşluk sadeleştirilmiş) benzerliği yüksek ilanlardan, bu çalışmada gönderilecekler arasında sadece birini gönder; mesaja "ayrıca: ilan.gov.tr" notu ekle. Basit tut: `difflib.SequenceMatcher` oranı ≥ 0.9.
- Gönderim sırası: Son başvuru tarihi en yakın olan önce.

## 5.3 Sağlık takibi
- Bir kaynak art arda **6 çalışma** (≈3 saat) hata verirse ve `warned=false` ise, Telegram'a bir kez uyarı gönder: "⚠️ {kaynak} 3 saattir okunamıyor. Son başarılı: …". `warned=true` yap.
- Kaynak tekrar başarılı olduğunda `warned=false` yap ve "✅ {kaynak} tekrar çalışıyor" mesajı gönder.
- **Sıfır ilan şüphesi:** Kaynak daha önce ≥10 ilan döndürüyordu ve şimdi 0 dönüyorsa, bunu hata gibi say (parser bozulmuş olabilir).

## 5.4 Loglama
`logging` ile, Türkçe, tek satırlık özetler:
```
[kamuilan_sbb] 214 ilan, 3 yeni, 1 filtreden geçti (1.8 sn)
[ilan_gov] HATA: ReadTimeout (art arda 2.)
Toplam: 2 bildirim gönderildi
```
GitHub Actions log'unda okunaklı olsun; token ve chat_id asla loglanmaz.

## 5.5 Testler
- `tests/test_filters.py`: Her kural, belirsizlik durumları, exclude önceliği, Türkçe harf vakaları ("İZMİR"/"izmir", "Öğretmen"/"ÖĞRETMEN").
- `tests/test_runner.py` (sahte kaynaklar ve sahte notifier ile):
  - Bootstrap: ilk çalışmada bildirim yok, hepsi seen.
  - İkinci çalışmada sadece yeni ilan bildiriliyor.
  - Bir kaynak hata verince diğerleri devam ediyor.
  - Gönderim başarısız olunca ilan seen'den çıkarılıyor.
  - `max_messages_per_run` aşılınca digest.
  - Kaynaklar arası tekrar tek mesaja iniyor.
  - 6 ardışık hatada tek uyarı, düzelince tek "tekrar çalışıyor" mesajı.
  - `--dry-run` state'i değiştirmiyor.

## Kabul kriterleri
- [ ] `pytest -q` yeşil.
- [ ] Yerelde `python -m ilanbot` iki kez arka arkaya çalıştırıldığında: ilki sessiz bootstrap, ikincisi 0 bildirim.
- [ ] 🧑 Kullanıcı test için `data/state.json`'dan bir kaynaktaki birkaç `seen` kaydını sildi ve üçüncü çalışmada sadece filtreye uyanlar telefonuna geldi.
