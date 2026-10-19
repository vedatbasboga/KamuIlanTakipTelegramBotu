# Aşama 6 — GitHub Actions ile Yayına Alma

## Amaç
Botu GitHub Actions'ta cron ile çalıştırmak, state'i repoda tutmak ve yurt dışı IP sorununu erken tespit etmek.

## 6.1 Erişim testi — İLK İŞ (`.github/workflows/access-test.yml`)
Asıl workflow'dan önce, GitHub runner'larının (yurt dışı IP) kaynaklara ulaşıp ulaşamadığını ölç.

- Tetikleyici: sadece `workflow_dispatch`.
- `docs/kaynaklar.md`'deki her liste uç noktasına bir istek atan küçük bir script (`scripts/access_test.py`): HTTP durum kodu, yanıt boyutu, süre, gövdede "captcha / challenge / erişim engellendi" gibi işaretler var mı.
- Sonucu `$GITHUB_STEP_SUMMARY`'ye tablo olarak yaz.

**🧑 KULLANICI:** Repoyu GitHub'a push'la → Actions → "Erişim testi" → "Run workflow". Sonuç tablosunu Claude Code'a yapıştır.

Karar:
- Tümü erişilebilir → 6.2'ye geç.
- Bazıları engelli → İki seçenek, kullanıcıya sor:
  - **A)** Engelli kaynakları `config.yaml`'da kapat, kalanlarla devam et.
  - **B)** Kendi bilgisayarında **self-hosted runner** kur (Settings → Actions → Runners → New self-hosted runner; GitHub'ın verdiği komutlarla). Sonra `runs-on: self-hosted` kullanılır. Bilgisayar kapalıyken çalışmayacağını belirt. İstersen sadece engelli kaynaklar için ayrı bir job/workflow `self-hosted` üzerinde çalışabilir; ama her iki job aynı `state.json`'a yazacağı için `concurrency` ile sıralanmalı.

## 6.2 Ana workflow (`.github/workflows/check.yml`)

Gereksinimler:
- **Tetikleyiciler:**
  - `schedule`: TR saatiyle 07:00–23:30 arası her 30 dakikada bir. GitHub cron UTC'dir (TR = UTC+3): `cron: "7,37 4-20 * * *"` (dakika 0/30 yerine 7/37 kullan; tam saatlerde GitHub kuyruğu yoğun ve gecikme artar).
  - `workflow_dispatch` (elle tetikleme, `dry_run` boolean input'u ile).
- **`permissions: contents: write`** (state commit'i için).
- **`concurrency: { group: ilanbot, cancel-in-progress: false }`**: İki çalışma aynı anda state'e yazmasın.
- `timeout-minutes: 10`.
- Adımlar:
  1. `actions/checkout`
  2. `actions/setup-python` (3.12, `cache: pip`)
  3. `pip install -r requirements.txt`
  4. `PYTHONPATH=src python -m ilanbot` — env: `TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}`, `TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}`
  5. State commit'i (**`if: always()`**, böylece bot kısmen hata verse de görülen ilanlar kaybolmaz):
     ```bash
     git config user.name "ilanbot"
     git config user.email "ilanbot@users.noreply.github.com"
     git add data/state.json
     git diff --cached --quiet || git commit -m "state: $(date -u +%FT%TZ)"
     git pull --rebase && git push
     ```
- Dry-run modunda commit adımı atlanır.

## 6.3 CI workflow (`.github/workflows/test.yml`)
- `push` ve `pull_request`'te: `ruff check .`, `ruff format --check .`, `pytest -q`.

## 6.4 🧑 KULLANICI — Secrets ve ilk çalışma
1. Repo → Settings → Secrets and variables → Actions → **New repository secret**:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
2. Settings → Actions → General → Workflow permissions → **Read and write permissions**.
3. Actions → "İlan kontrolü" → Run workflow → önce `dry_run: true`, log'u kontrol et.
4. Sonra `dry_run: false` ile bir kez çalıştır (bootstrap; bildirim gelmemesi normal).
5. Sonraki zamanlanmış çalışmaları bekle.

## 6.5 Notlar (README'ye de yaz)
- **60 gün kuralı:** GitHub, 60 gün boyunca hiç commit almayan repolarda zamanlanmış workflow'ları durdurur. State commit'leri bu sorunu çoğu zaman çözer, ama hiç yeni ilan olmayan uzun dönemlerde state değişmeyebilir. Aşama 7'deki haftalık heartbeat state'e yazdığı için bunu kesin olarak önler.
- **Dakika kotası:** Her çalışma yaklaşık 30–60 sn sürer. Private repoda aylık ücretsiz kotaya göre sıklığı ayarla; Settings → Billing'den kullanımı izle.
- **Zamanlama gecikmesi:** GitHub cron'u birkaç dakika (yoğun saatlerde daha fazla) gecikebilir; ilan takibi için önemsiz.
- `README.md` oluştur: Projenin ne yaptığı, kurulum, `config.yaml` açıklaması, sorun giderme.

## Kabul kriterleri
- [ ] Erişim testi sonuçları `docs/kaynaklar.md`'ye işlendi.
- [ ] Ana workflow en az 3 zamanlanmış çalışmayı hatasız tamamladı; state commit'leri repoda görünüyor.
- [ ] Test workflow'u yeşil.
- [ ] 🧑 Kullanıcı gerçek bir yeni ilan bildiriminin telefonuna geldiğini onayladı (ya da Aşama 5'teki "seen silme" yöntemiyle Actions üzerinden test edildi).
