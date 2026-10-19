"""BIST Day Trading Asistanı - Konfigürasyon

Bu dosyadaki değerler uygulamanın varsayılanlarıdır; arayüzdeki (sidebar)
ayarlardan kullanıcı tarafından geçici olarak değiştirilebilir.
"""

# Varsayılan hisse evreni artık data/bist_all_tickers.csv dosyasından (tüm
# BIST, ~634 hisse) okunur; bkz. strategy/universe.py::load_all_bist_tickers().
# Bu dosya, o liste bulunamazsa kullanılacak küçük bir yedek içindir (BIST30
# ağırlıklı). yfinance üzerinde Borsa İstanbul kodları ".IS" soneki ile
# sorgulanır.
FALLBACK_UNIVERSE = [
    "AKBNK.IS", "GARAN.IS", "ISCTR.IS", "YKBNK.IS", "VAKBN.IS", "HALKB.IS",
    "THYAO.IS", "PGSUS.IS", "TAVHL.IS",
    "BIMAS.IS", "MGROS.IS", "SOKM.IS", "ULKER.IS",
    "EREGL.IS", "KRDMD.IS", "SASA.IS", "PETKM.IS", "TUPRS.IS", "GUBRF.IS",
    "KCHOL.IS", "SAHOL.IS", "DOHOL.IS", "ALARK.IS", "ENKAI.IS",
    "ASELS.IS", "OTKAR.IS", "FROTO.IS", "TOASO.IS", "ARCLK.IS", "VESTL.IS",
    "TCELL.IS", "TTKOM.IS",
    "SISE.IS", "KOZAL.IS", "KOZAA.IS", "EKGYO.IS", "ISGYO.IS",
    "ASTOR.IS", "ENJSA.IS", "AKSEN.IS", "ODAS.IS", "BRSAN.IS",
]

# Toplu veri indirmede bir seferde kaç hisse sorgulanacağı (634 hisseyi tek
# seferde değil, bu boyutta parçalar hâlinde indirmek daha güvenilirdir)
SCREEN_CHUNK_SIZE = 100

# RVOL@Time (zamana göre göreli hacim) göstergesi varsayılanları — bkz.
# strategy/relative_volume.py. Veri gecikmesi handikabını, "şu an" yerine
# "elimizdeki en son verinin kendi zaman damgası" baz alınarak aşar.
RVOL_LOOKBACK_DAYS = 20     # Taban çizgisi için kaç geçmiş günün ortalaması alınsın
RVOL_THRESHOLD = 1.2        # Sabah teyidinde aranan minimum RVOL@Time (1.0 = tipik gün)

# BIST 100 endeksi (göreli güç ve piyasa yönü referansı için)
BIST_INDEX_TICKER = "XU100.IS"

# Borsa İstanbul seans saatleri (Europe/Istanbul yerel saati, bilgi amaçlı)
MARKET_OPEN_AUCTION = "09:40"
CONTINUOUS_TRADING_START = "10:00"
CONFIRMATION_TIME = "10:30"
MARKET_CLOSE = "18:00"
FORCED_EXIT_TIME = "17:45"  # Kapanış seansına girmeden önce pozisyonları kapatma hedefi

# Akşam tarama skor ağırlıkları (toplamı 100 olacak şekilde tasarlanmıştır,
# ama kod herhangi bir toplam için normalize eder)
DEFAULT_WEIGHTS = {
    "relative_strength": 25,
    "volume": 25,
    "trend": 20,
    "momentum_rsi": 15,
    "breakout_proximity": 15,
}

# Risk yönetimi varsayılanları
DEFAULT_RISK_PER_TRADE_PCT = 1.5   # Sermayenin yüzde kaçı tek işlemde riske atılır
DEFAULT_TARGET_RR = 2.0            # Hedef risk/ödül oranı (stop mesafesinin kaç katı)

# BIST günlük fiyat marjı (çoğu pay için yaklaşık ±%10; bazı kategorilerde farklıdır)
DAILY_PRICE_BAND_PCT = 10.0
CEILING_WARNING_THRESHOLD_PCT = 1.5  # Tavana bu yüzdeden daha yakınsa likidite uyarısı ver
