# 📈 BIST Day Trading Asistanı

"Akşam Tarama → Sabah Teyit (10:30 sonrası) → Pozisyon Yönetimi → Gün Sonu
Çıkış" stratejisini uygulayan bir Streamlit uygulaması.

**Kullanım modeli**: Bu uygulama bir broker/aracı kurum API'sine bağlı
değildir ve emir vermez. Akşam bir izleme listesi oluşturur; sabah saat
10:30 civarında her hisse için **"Gerekli Hacim (Şu An)"** rakamını
hesaplar. Siz bu rakamı kendi banka/aracı kurum uygulamanızda gördüğünüz
**gerçek zamanlı (gecikmesiz) hacimle** karşılaştırır, yeterliyse alımı
kendi uygulamanızdan manuel olarak yaparsınız. Böylece Yahoo Finance
verisinin gecikmesi, nihai karara hiç karışmamış olur.

> **Yatırım tavsiyesi değildir.** Bu araç, önceden belirlenmiş bir metodolojiyi
> otomatikleştiren bir karar destek aracıdır; kazanç garanti etmez. Kullanılan
> veri kaynağı (Yahoo Finance / `yfinance`) gecikmeli veya eksik olabilir.
> Gerçek parayla işlem yapmadan önce kendi araştırmanızı yapın.

## Özellikler

- **🌙 Akşam Tarama**: **Tüm BIST evrenini** (634 hisse, `data/bist_all_tickers.csv`)
  toplu (batch) veri indirme ile tarar; göreli güç, hacim artışı, trend
  (MA20/MA50), RSI momentumu ve direnç yakınlığına göre puanlayıp bir izleme
  listesi oluşturur.
- **🌅 Sabah Teyidi (RVOL@Time ile)**: Saat 10:30 sonrası, listedeki her
  hisse için **"Gerekli Hacim (Şu An)"** rakamını (adet ve TL cinsinden)
  hesaplar — bankanızdaki gerçek zamanlı hacimle karşılaştıracağınız ana
  çıktı budur. Ayrıca VWAP, giriş tetiği ve genel piyasa (BIST100) yönüne
  göre uygulamanın kendi verisiyle bir ön/çapraz değerlendirme de sunar.
- **📋 Pozisyon Takip**: Risk bazlı pozisyon büyüklüğü hesaplayıcı ve basit
  bir açık pozisyon takip tablosu.
- **ℹ️ Strateji**: Metodolojinin ve risklerin özeti.

## Proje Yapısı

```
bist-day-trading-app/
├── app.py                     # Streamlit ana uygulaması (4 sekme)
├── config.py                  # Seans saatleri, ağırlıklar, RVOL/risk parametreleri
├── data/
│   └── bist_all_tickers.csv    # Tüm BIST hisse kodları (634 adet, yfinance formatında)
├── scripts/
│   └── build_universe_from_excel.py  # Hisse listesini güncellemek için yardımcı script
├── strategy/
│   ├── __init__.py
│   ├── data.py                 # yfinance ile veri çekme (tekil + toplu, önbellekli)
│   ├── indicators.py           # SMA, RSI, göreli güç, hacim oranı, VWAP
│   ├── relative_volume.py      # RVOL@Time (zamana göre göreli hacim) göstergesi
│   ├── screening.py            # Akşam tarama / puanlama mantığı
│   ├── confirmation.py         # Sabah teyit mantığı
│   └── universe.py             # Tüm BIST hisse listesini okuyan yardımcı modül
├── requirements.txt
├── runtime.txt                 # Streamlit Cloud için Python sürümü
├── .streamlit/config.toml      # Tema
└── .gitignore
```

## Yerelde Çalıştırma

```bash
git clone <repo-url>
cd bist-day-trading-app
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Uygulama varsayılan olarak `http://localhost:8501` adresinde açılır.

## GitHub'a Yükleme

```bash
cd bist-day-trading-app
git init
git add .
git commit -m "BIST day trading asistanı - ilk sürüm"
git branch -M main
git remote add origin https://github.com/<kullanici-adiniz>/<repo-adi>.git
git push -u origin main
```

(Önce GitHub üzerinde boş bir repo oluşturmanız gerekir: github.com → **New
repository**.)

## Streamlit Community Cloud'a Dağıtım

1. [share.streamlit.io](https://share.streamlit.io) adresine GitHub
   hesabınızla giriş yapın.
2. **New app** → yukarıda push ettiğiniz repoyu, `main` dalını ve
   `app.py` dosyasını seçin.
3. **Deploy** butonuna basın. Streamlit, `requirements.txt` dosyasındaki
   bağımlılıkları otomatik olarak kurar.
4. Uygulama birkaç dakika içinde `https://<uygulama-adi>.streamlit.app`
   adresinde canlıya alınır. Kod deposuna her `git push` yaptığınızda
   uygulama otomatik olarak güncellenir.

## RVOL@Time: Veri Gecikmesi Handikabını Aşma

Yahoo Finance (yfinance) verisi BIST için ~15 dakika gecikmeli gelebilir; bu
yüzden uygulamanın **kendi** anlık hacim okuması güvenilir bir karar girdisi
değildir. Uygulama bu sorunu, veriyi "düzeltmeye" çalışarak değil, **sizin
zaten erişiminiz olan daha iyi bir kaynağı** (banka/aracı kurum
uygulamanızdaki gerçek zamanlı hacim ekranı) kullanmanızı sağlayarak çözer:

1. Son ~20-40 işlem gününün 5 dakikalık barlarından, gün içindeki her zaman
   dilimi için **ortalama kümülatif hacim eğrisini** (taban çizgisini) çıkarır
   (`strategy/relative_volume.py::build_volume_time_profile`).
2. Bu taban çizgisinden, **tam olarak şu an** (duvar saatiyle, "şu an"ı
   sabit kabul ederek) için, seçtiğiniz RVOL eşiğini (`RVOL_THRESHOLD`,
   varsayılan 1.2×) tutturmak üzere oluşması gereken kümülatif hacmi
   hesaplar → **"Gerekli Hacim (Şu An)"** (hem adet/lot hem de yaklaşık TL
   cinsinden, son bilinen fiyatla çarpılarak).
3. Siz "Sabah Teyit" sekmesindeki bu rakamı, bankanızda **o an gördüğünüz
   gerçek hacimle** karşılaştırırsınız. Gerçek hacim bu eşiğin üzerindeyse,
   hisse tipik günlerin ortalamasının üzerinde bir ilgiyle işlem görüyor
   demektir.

Bu akışta veri gecikmesi sorunu **tamamen devre dışı kalır**: nihai kıyas
uygulamanın (gecikmeli olabilecek) verisiyle değil, sizin kendi
uygulamanızda gördüğünüz gerçek veriyle yapılır. Uygulamanın kendi verisine
dayanan "RVOL (uygulamanın kendi verisine göre)" ve "Ön Değerlendirme"
sütunları yalnızca bir çapraz kontrol amaçlıdır. "Sabah Teyit" sekmesindeki
ilgili açılır kutuda aynı açıklama uygulama içinde de yer alır.

## Hisse Listesini Güncelleme

`data/bist_all_tickers.csv`, yüklediğiniz tüm-hisse Excel dosyasından
üretilmiş bir anlık görüntüdür (634 BIST hissesi). BIST'e yeni şirketler
kote olduğunda veya hisseler kottan çıktığında listeyi güncellemek için:

```bash
python scripts/build_universe_from_excel.py yeni_tumhisse.xlsx
```

Script, "Hisse" sütunu bulunan herhangi bir .xlsx dosyasını kabul eder (sayfa
adı/sütun adı farklıysa `--sheet` ve `--column` parametreleriyle belirtin) ve
`data/bist_all_tickers.csv` dosyasını otomatik olarak yeniden üretir.

## Kendi Veri Kaynağınızı Bağlamak

Varsayılan olarak uygulama ücretsiz `yfinance` verisini kullanır. Gerçek
zamanlı/profesyonel bir veri sağlayıcısına (aracı kurum API'si, Matriks,
Foreks vb.) geçmek için yalnızca `strategy/data.py` içindeki
`get_daily_history` ve `get_intraday_history` fonksiyonlarının içini
değiştirmeniz yeterlidir; geri kalan tüm modüller aynı arayüzü kullanmaya
devam eder.

## Evreni, Ağırlıkları ve RVOL Ayarlarını Özelleştirme

Uygulamanın sol panelinden (sidebar):
- **Taranacak evren**: "Tüm BIST hisseleri" (634, varsayılan), "İlk N hisse"
  (hızlı test için) veya "Özel liste" (kendi ticker listenizi yapıştırarak)
  arasında seçim yapabilirsiniz.
- İzleme listesine alınacak hisse sayısını ayarlayabilirsiniz.
- Skor bileşenlerinin (göreli güç, hacim, trend, RSI, direnç yakınlığı)
  ağırlıklarını kendi tercihinize göre kaydırabilirsiniz.
- **RVOL@Time eşiğini** (varsayılan 1.2) ve taban çizgisi için kaç geçmiş
  günün kullanılacağını (varsayılan 20) ayarlayabilirsiniz.

**Performans notu**: 634 hissenin tamamını taramak, toplu indirme sayesinde
tekil sorgulardan çok daha hızlıdır, ama yine de ilk çalıştırmada (önbellek
boşken) birkaç dakika sürebilir. Hızlı denemeler için "İlk N hisse" modunu
kullanmanız önerilir.

## Sorumluluk Reddi

Bu yazılım "olduğu gibi" sunulmaktadır, herhangi bir kâr veya doğruluk
garantisi içermez. Geliştirici(ler), bu aracın kullanımından doğabilecek
finansal kayıplardan sorumlu değildir. Day trading yüksek risk içerir;
akademik çalışmalar bireysel day traderların büyük çoğunluğunun zarar
ettiğini göstermektedir.
