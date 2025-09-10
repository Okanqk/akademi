import streamlit as st
import json
import os
import random
import time
from datetime import datetime, timedelta
import pandas as pd
import requests

DATA_FILE = "kelimeler.json"
SCORE_FILE = "puan.json"


# İnternet saati alma fonksiyonu
def get_internet_time():
    try:
        response = requests.get("http://worldtimeapi.org/api/timezone/Europe/Istanbul", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return datetime.fromisoformat(data['datetime'].replace('Z', '+00:00')).replace(tzinfo=None)
    except:
        pass
    return datetime.now()  # İnternet bağlantısı yoksa sistem saatini kullan


# Kelime dosyası
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        kelimeler = json.load(f)
else:
    kelimeler = []

# Puan dosyası
if os.path.exists(SCORE_FILE):
    with open(SCORE_FILE, "r", encoding="utf-8") as f:
        score_data = json.load(f)
else:
    score_data = {"score": 0, "daily": {}, "last_check_date": None}


def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(kelimeler, f, ensure_ascii=False, indent=2)
    with open(SCORE_FILE, "w", encoding="utf-8") as f:
        json.dump(score_data, f, ensure_ascii=False, indent=2)


# İnternet saatini al
current_time = get_internet_time()
today = current_time.date()
today_str = today.strftime("%Y-%m-%d")

# Günlük veri kontrolü
if "daily" not in score_data:
    score_data["daily"] = {}

# Gece yarısı kontrolü ve önceki günün kelime ceza kontrolü
if score_data.get("last_check_date") != today_str:
    yesterday = (today - timedelta(days=1)).strftime("%Y-%m-%d")

    # Önceki günün kelime kontrolü
    if yesterday in score_data["daily"]:
        if score_data["daily"][yesterday]["yeni_kelime"] < 10:
            penalty = -20
            score_data["score"] += penalty
            score_data["daily"][yesterday]["puan"] += penalty
            st.warning(f"⚠️ Dün 10 kelime eklemedin! -20 puan cezası uygulandı.")

    score_data["last_check_date"] = today_str

# Bugünün verisini oluştur
if today_str not in score_data["daily"]:
    score_data["daily"][today_str] = {"puan": 0, "yeni_kelime": 0, "dogru": 0, "yanlis": 0}

# Haftalık yanlış kelime cezası
for k in kelimeler:
    if "last_wrong_date" in k and k.get("wrong_count", 0) > 0:
        last_wrong = datetime.strptime(k["last_wrong_date"], "%Y-%m-%d")
        weeks_passed = (today - last_wrong.date()).days // 7
        if weeks_passed >= 1:
            score_data["score"] -= 2 * weeks_passed
            k["last_wrong_date"] = today.strftime("%Y-%m-%d")

save_data()

st.title("📘 Akademi - İngilizce Kelime Uygulaması")
st.sidebar.write(f"💰 Genel Puan: {score_data['score']}")

# Güncel saat gösterimi (internet saati)
st.sidebar.write(f"🕐 Güncel Saat: {current_time.strftime('%H:%M:%S')}")
st.sidebar.write(f"📅 Tarih: {today_str}")

# Menü
menu = st.sidebar.radio(
    "Menü",
    ["🏠 Ana Sayfa", "📝 Testler", "📊 İstatistikler", "➕ Kelime Ekle"],
    key="main_menu"
)

# --- Ana Sayfa ---
if menu == "🏠 Ana Sayfa":
    st.header("🏠 Ana Sayfa")
    st.subheader("📅 Tarih ve Saat (İnternet Saati)")
    st.write(current_time.strftime("%Y-%m-%d %H:%M:%S"))
    st.subheader(f"💰 Genel Puan: {score_data['score']}")
    st.progress(min(max(score_data['score'], 0), 100) / 100)

# --- Testler ---
elif menu == "📝 Testler":
    st.header("📝 Testler")
    test_secim = st.radio(
        "Bir test seçin:",
        ["Yeni Test", "Yanlış Kelimeler Testi", "Tekrar Test"],
        key="test_menu"
    )

    # ✅ Yeni Test mantığı düzeltildi
    if test_secim == "Yeni Test":
        st.subheader("Yeni Test")
        if kelimeler:
            # Session state başlatma
            if "soru" not in st.session_state:
                st.session_state.soru = random.choice(kelimeler)
                st.session_state.secenekler = None
                st.session_state.cevaplandi = False
                st.session_state.cevap_gosteriliyor = False

            # Eğer seçenekler henüz oluşturulmadıysa oluştur
            if st.session_state.secenekler is None:
                soru = st.session_state.soru
                dogru = soru["tr"]
                yanlislar = [k["tr"] for k in kelimeler if k["tr"] != dogru]
                secenekler = random.sample(yanlislar, min(3, len(yanlisler)))
                secenekler.append(dogru)
                random.shuffle(secenekler)
                st.session_state.secenekler = secenekler

            soru = st.session_state.soru
            dogru = soru["tr"]

            # Cevap gösteriliyorsa, sadece sonucu göster ve bekle
            if st.session_state.cevap_gosteriliyor:
                if st.session_state.son_cevap_dogru:
                    st.success("✅ Doğru!")
                else:
                    st.error(f"❌ Yanlış! Doğru cevap: {dogru}")

                # 3 saniye bekle ve yeni soruya geç
                time.sleep(3)
                st.session_state.soru = random.choice(kelimeler)
                st.session_state.secenekler = None
                st.session_state.cevaplandi = False
                st.session_state.cevap_gosteriliyor = False
                st.rerun()
            else:
                # Normal soru gösterimi
                secim = st.radio(f"{soru['en']} ne demek?", st.session_state.secenekler,
                                 key=f"secenek_radio_{id(soru)}")

                if st.button("Cevapla", key="cevapla_btn") and not st.session_state.cevaplandi:
                    st.session_state.cevaplandi = True
                    st.session_state.cevap_gosteriliyor = True

                    if secim == dogru:
                        st.session_state.son_cevap_dogru = True
                        score_data["score"] += 1
                        score_data["daily"][today_str]["puan"] += 1
                        score_data["daily"][today_str]["dogru"] += 1
                    else:
                        st.session_state.son_cevap_dogru = False
                        score_data["score"] -= 2
                        score_data["daily"][today_str]["puan"] -= 2
                        score_data["daily"][today_str]["yanlis"] += 1
                        soru["wrong_count"] = soru.get("wrong_count", 0) + 1
                        soru["last_wrong_date"] = today_str

                    save_data()
                    st.rerun()
        else:
            st.info("Henüz kelime yok. Lütfen önce kelime ekleyin.")

    elif test_secim == "Yanlış Kelimeler Testi":
        st.subheader("Yanlış Kelimeler Testi")
        yanlis_kelimeler = [k for k in kelimeler if k.get("wrong_count", 0) > 0]
        if yanlis_kelimeler:
            if "yanlis_soru" not in st.session_state:
                st.session_state.yanlis_soru = random.choice(yanlis_kelimeler)
                st.session_state.yanlis_secenekler = None
                st.session_state.yanlis_cevaplandi = False
                st.session_state.yanlis_cevap_gosteriliyor = False

            if st.session_state.yanlis_secenekler is None:
                soru = st.session_state.yanlis_soru
                dogru = soru["tr"]
                yanlislar = [k["tr"] for k in kelimeler if k["tr"] != dogru]
                secenekler = random.sample(yanlislar, min(3, len(yanlisler)))
                secenekler.append(dogru)
                random.shuffle(secenekler)
                st.session_state.yanlis_secenekler = secenekler

            soru = st.session_state.yanlis_soru
            dogru = soru["tr"]

            if st.session_state.yanlis_cevap_gosteriliyor:
                if st.session_state.yanlis_son_cevap_dogru:
                    st.success("✅ Doğru!")
                else:
                    st.error(f"❌ Yanlış! Doğru cevap: {dogru}")

                time.sleep(3)
                st.session_state.yanlis_soru = random.choice(yanlis_kelimeler)
                st.session_state.yanlis_secenekler = None
                st.session_state.yanlis_cevaplandi = False
                st.session_state.yanlis_cevap_gosteriliyor = False
                st.rerun()
            else:
                secim = st.radio(f"{soru['en']} ne demek?", st.session_state.yanlis_secenekler,
                                 key=f"yanlis_radio_{id(soru)}")

                if st.button("Cevapla", key="yanlis_cevapla_btn") and not st.session_state.yanlis_cevaplandi:
                    st.session_state.yanlis_cevaplandi = True
                    st.session_state.yanlis_cevap_gosteriliyor = True

                    if secim == dogru:
                        st.session_state.yanlis_son_cevap_dogru = True
                        soru["wrong_count"] -= 1
                        if soru["wrong_count"] <= 0:
                            if "last_wrong_date" in soru:
                                del soru["last_wrong_date"]
                            soru["wrong_count"] = 0
                    else:
                        st.session_state.yanlis_son_cevap_dogru = False

                    save_data()
                    st.rerun()
        else:
            st.info("Yanlış kelime yok.")

    # ✅ TEKRAR TEST KISMI DÜZELTİLDİ - elif yerine if kullanıldı
    elif test_secim == "Tekrar Test":
        st.subheader("Tekrar Test")
        if kelimeler:
            if "tekrar_soru" not in st.session_state:
                st.session_state.tekrar_soru = random.choice(kelimeler)
                st.session_state.tekrar_soru_tipi = random.choice(['en_to_tr', 'tr_to_en'])
                st.session_state.tekrar_secenekler = None
                st.session_state.tekrar_cevaplandi = False
                st.session_state.tekrar_cevap_gosteriliyor = False
                st.session_state.tekrar_son_cevap_dogru = False

            if st.session_state.tekrar_secenekler is None:
                soru = st.session_state.tekrar_soru
                soru_tipi = st.session_state.tekrar_soru_tipi

                if soru_tipi == 'en_to_tr':  # İngilizce kelime, Türkçe seçenekler
                    dogru = soru["tr"]
                    yanlislar = [k["tr"] for k in kelimeler if k["tr"] != dogru]
                else:  # Türkçe kelime, İngilizce seçenekler
                    dogru = soru["en"]
                    yanlislar = [k["en"] for k in kelimeler if k["en"] != dogru]

                secenekler = random.sample(yanlislar, min(3, len(yanlislar)))
                secenekler.append(dogru)
                random.shuffle(secenekler)
                st.session_state.tekrar_secenekler = secenekler
                st.session_state.tekrar_dogru_cevap = dogru

            soru = st.session_state.tekrar_soru
            soru_tipi = st.session_state.tekrar_soru_tipi
            dogru = st.session_state.tekrar_dogru_cevap

            if st.session_state.tekrar_cevap_gosteriliyor:
                if st.session_state.tekrar_son_cevap_dogru:
                    st.success("✅ Doğru!")
                else:
                    st.error(f"❌ Yanlış! Doğru cevap: {dogru}")

                time.sleep(3)
                st.session_state.tekrar_soru = random.choice(kelimeler)
                st.session_state.tekrar_soru_tipi = random.choice(['en_to_tr', 'tr_to_en'])
                st.session_state.tekrar_secenekler = None
                st.session_state.tekrar_cevaplandi = False
                st.session_state.tekrar_cevap_gosteriliyor = False
                st.rerun()
            else:
                # Soru tipine göre soru metnini oluştur
                if soru_tipi == 'en_to_tr':
                    soru_metni = f"🇺🇸 '{soru['en']}' kelimesi ne demek?"
                else:
                    soru_metni = f"🇹🇷 '{soru['tr']}' kelimesinin İngilizcesi nedir?"

                secim = st.radio(soru_metni, st.session_state.tekrar_secenekler,
                                 key=f"tekrar_radio_{id(soru)}_{soru_tipi}")

                if st.button("Cevapla", key="tekrar_cevapla_btn") and not st.session_state.tekrar_cevaplandi:
                    st.session_state.tekrar_cevaplandi = True
                    st.session_state.tekrar_cevap_gosteriliyor = True

                    if secim == dogru:
                        st.session_state.tekrar_son_cevap_dogru = True
                        # Tekrar testinde puan verme isteğe bağlı
                        # score_data["score"] += 1
                    else:
                        st.session_state.tekrar_son_cevap_dogru = False
                        # Tekrar testinde puan kesme isteğe bağlı
                        # score_data["score"] -= 1

                    save_data()
                    st.rerun()
        else:
            st.info("Henüz kelime yok. Lütfen önce kelime ekleyin.")

# --- İstatistikler ---
elif menu == "📊 İstatistikler":
    st.header("📊 İstatistikler")
    secim = st.radio("Bir seçenek seçin:", ["Günlük İstatistik", "Genel İstatistik", "Yanlış Kelimeler"],
                     key="istat_menu")

    if secim == "Günlük İstatistik":
        st.subheader("📅 Günlük İstatistik")
        daily_df = pd.DataFrame.from_dict(score_data["daily"], orient="index")
        st.dataframe(daily_df)
        st.bar_chart(daily_df["puan"])

    elif secim == "Genel İstatistik":
        st.subheader("📊 Genel İstatistik")
        st.write(f"💰 Genel Puan: {score_data['score']}")
        total_dogru = sum([v.get("dogru", 0) for v in score_data["daily"].values()])
        total_yanlis = sum([v.get("yanlis", 0) for v in score_data["daily"].values()])
        st.write(f"✅ Toplam Doğru: {total_dogru}")
        st.write(f"❌ Toplam Yanlış: {total_yanlis}")
        daily_df = pd.DataFrame.from_dict(score_data["daily"], orient="index")
        st.line_chart(daily_df["puan"].cumsum())

    elif secim == "Yanlış Kelimeler":
        st.subheader("❌ Yanlış Kelimeler")
        yanlis_kelimeler = [k for k in kelimeler if k.get("wrong_count", 0) > 0]
        if yanlis_kelimeler:
            for k in yanlis_kelimeler:
                color = "red" if k.get("wrong_count", 0) >= 3 else "orange" if k.get("wrong_count", 0) == 2 else "black"
                st.markdown(
                    f"<span style='color:{color}'>{k['en']} → {k['tr']} | Yanlış sayısı: {k.get('wrong_count', 0)} | Son yanlış: {k.get('last_wrong_date', '-')}</span>",
                    unsafe_allow_html=True)
        else:
            st.info("Yanlış kelime yok.")

# --- Kelime Ekle ---
elif menu == "➕ Kelime Ekle":
    st.header("➕ Kelime Ekle")
    kelime_secim = st.radio("Bir seçenek seçin:", ["Yeni Kelime Ekle", "Kelime Listesi"], key="kelime_menu")

    if kelime_secim == "Yeni Kelime Ekle":
        st.subheader("Yeni Kelime Ekle")
        ing = st.text_input("İngilizce Kelime", key="ing_input")
        tr = st.text_input("Türkçe Karşılığı", key="tr_input")
        if st.button("Kaydet", key="save_btn"):
            if ing.strip() != "" and tr.strip() != "":
                # Aynı kelime var mı kontrol et
                existing_word = any(k["en"].lower() == ing.strip().lower() for k in kelimeler)
                if existing_word:
                    st.warning("⚠️ Bu kelime zaten mevcut!")
                else:
                    kelimeler.append({"en": ing.strip(), "tr": tr.strip(), "wrong_count": 0})
                    score_data["daily"][today_str]["yeni_kelime"] += 1
                    score_data["score"] += 1  # ✅ her eklenen kelime +1 puan
                    score_data["daily"][today_str]["puan"] += 1  # Günlük puana da ekle

                    # Veriyi kaydet
                    save_data()
                    st.success(f"✅ Kelime kaydedildi: {ing} → {tr}")
                    # Input alanlarını temizle
                    time.sleep(0.5)  # Kısa bekleme
                    st.rerun()
            else:
                st.warning("⚠️ İngilizce ve Türkçe kelimeyi doldurun.")

    elif kelime_secim == "Kelime Listesi":
        st.subheader("Kelime Listesi")
        if kelimeler:
            for i, k in enumerate(kelimeler):
                st.write(f"{i + 1}. {k['en']} → {k['tr']} (Yanlış sayısı: {k.get('wrong_count', 0)})")
        else:
            st.info("Henüz eklenmiş kelime yok.")

# Bugünün kelime eklenme durumunu göster
bugun_kelime = score_data["daily"][today_str]["yeni_kelime"]
st.sidebar.write(f"📚 Bugün eklenen kelime: {bugun_kelime}/10")
if bugun_kelime < 10:
    st.sidebar.warning(f"⚠️ Daha {10 - bugun_kelime} kelime eklemelisin!")