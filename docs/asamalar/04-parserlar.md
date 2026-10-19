# Aşama 4 — Parser'lar

## Amaç
Aşama 3'te belgelenen her kaynak için `Source` uygulamasını ve saf `parse` fonksiyonunu yazmak, fixture testleriyle doğrulamak.

## Genel kurallar
- Her kaynak dosyası şu yapıda:
  ```python
  def parse(raw) -> list[Ilan]: ...  # saf, ağ yok


  class KamuIlanSbbSource:
      name = "kamuilan_sbb"
      display_name = "kamuilan.sbb.gov.tr"

      def fetch(self, client) -> list[Ilan]: ...  # çek → parse
  ```
- `sources/__init__.py` içinde `REGISTRY: dict[str, Source]`.
- Uç noktalar ve parametreler **`docs/kaynaklar.md`'den** alınır, uydurulmaz.
- Parser bir ilanı parse edemezse o ilanı atlar ve uyarı loglar; tüm listeyi düşürmez. Ama listede **hiç** ilan parse edilemediyse `ParseError` fırlatır (site yapısı değişmiş demektir, sessizce "0 ilan" dönmek tehlikelidir).
- Tarihleri `Europe/Istanbul` timezone'lu `datetime`'a çevir. "28.10.2026", "28 Ekim 2026", ISO formatları desteklensin (ortak bir `parse_tr_date` yardımcısı yaz, Türkçe ay adlarıyla).
- Öğrenim, KPSS ve il alanları yapılandırılmış veri olarak gelmiyorsa başlık + özet metninden Aşama 1'deki normalize fonksiyonlarıyla çıkarılır.
- Detay sayfası gerekiyorsa: Sadece **yeni** (state'te olmayan) ilanların detayı çekilir. Bunun için `fetch` iki adıma ayrılır: `list_items()` ve `enrich(ilan)`. Runner önce listeyi alır, dedup yapar, sonra sadece yenileri zenginleştirir. Çalışma başına kaynak başına en fazla 20 detay isteği.

## Sıra
En değerliden başla, her biri bitince test et ve commit at:
1. `kamuilan_sbb`
2. `ilan_gov`
3. `kariyer_kapisi`
4. `iskur`
5. `yerel_yonetimler`
6. `resmi_gazete` (en karmaşık; personel ilanlarını ilan bölümünden ayıklamak gerekiyor)

## Testler (`tests/test_source_<kaynak>.py`)
Her kaynak için:
- Fixture'dan parse edilen ilan sayısı beklenen değer.
- İlk ilanın tüm dolu alanları tek tek doğrulanır (id, title, url mutlak mı, institution, tarihler tz-aware mı).
- ID'ler benzersiz.
- Bozuk/boş yanıtta `ParseError`.
- `fetch`, `respx` ile mock'lanmış uç noktayla çalışıyor (doğru URL ve parametreler çağrılıyor).

## Canlı duman testi (elle, test paketinin dışında)
Her parser bitince:
```bash
PYTHONPATH=src python -m ilanbot --source <kaynak> --dry-run
```
Çıktıdaki ilk 5 ilanı sitedeki listeyle karşılaştır, `ILERLEME.md`'ye "canlı doğrulandı: tarih" yaz.

## Kabul kriterleri
- [ ] Kullanılabilir her kaynak için parser ve testler var, `pytest -q` yeşil.
- [ ] Her kaynak için canlı `--dry-run` başarılı ve sonuçlar sitedekiyle uyumlu.
- [ ] `ruff check .` temiz.
