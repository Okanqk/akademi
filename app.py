import streamlit as st
import json
import os
import random
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
    return datetime.now()


# Güvenli veri kaydetme fonksiyonu
def safe_save_data():
    try:
        # Önce backup al
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE + ".backup", "w", encoding="utf-8") as f:
                json.dump(kelimeler, f, ensure_ascii=False, indent=2)

        if os.path.exists(SCORE_FILE):
            with open(SCORE_FILE + ".backup", "w", encoding="utf-8") as f:
                json.dump(score_data, f, ensure_ascii=False, indent=2)

        # Asıl dosyaları kaydet
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(kelimeler, f, ensure_ascii=False, indent=2)

        with open(SCORE_FILE, "w", encoding="utf-8") as f:
            json.dump(score_data, f, ensure_ascii=False, indent=2)

        return True
    except Exception as e:
        st.error(f"Veri kaydedilirken hata: {e}")
        return False


# Güvenli veri yükleme fonksiyonu
def safe_load_data():
    kelimeler = []
    score_data = {"score": 0, "daily": {}, "last_check_date": None}

    # Kelimeler dosyasını yükle
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                kelimeler = json.load(f)
        except:
            # Ana dosya bozuksa backup'tan yükle
            if os.path.exists(DATA_FILE + ".backup"):
                try:
                    with open(DATA_FILE + ".backup", "r", encoding="utf-8") as f:
                        kelimeler = json.load(f)
                    st.warning("Ana dosya bozuk, backup'tan yüklendi!")
                except:
                    kelimeler = []

    # Puan dosyasını yükle
    if os.path.exists(SCORE_FILE):
        try:
            with open(SCORE_FILE, "r", encoding="utf-8") as f:
                score_data = json.load(f)
        except:
            # Ana dosya bozuksa backup'tan yükle
            if os.path.exists(SCORE_FILE + ".backup"):
                try:
                    with open(SCORE_FILE + ".backup", "r", encoding="utf-8") as f:
                        score_data = json.load(f)
                    st.warning("Puan dosyası bozuk, backup'tan yüklendi!")
                except:
                    score_data = {"score": 0, "daily": {}, "last_check_date": None}

    return kelimeler, score_data


# Verileri yükle
kelimeler, score_data = safe_load_data()

# İnternet saatini al
current_time = get_internet_time()
today = current_time.date()
today_str = today.strftime("%Y-%m-%d")

# Günlük veri kontrolü
if "daily" not in score_data:
    score_data["daily"] = {}

# Gece yarısı kontrolü
if score_data.get("last_check_date") != today_str:
    yesterday = (today - timedelta(days=1)).strftime("%Y-%m-%d")

    if yesterday in score_data["daily"]:
        if score_data["daily"][yesterday]["yeni_kelime"] < 10:
            penalty = -20
            score_data["score"] += penalty
            score_data["daily"][yesterday]["puan"] += penalty

    score_data["last_check_date"] = today_str

# Bugünün verisini oluştur
if today_str not in score_data["daily"]:
    score_data["daily"][today_str] = {"puan": 0, "yeni_kelime": 0, "dogru": 0, "yanlis": 0}

# Haftalık yanlış kelime cezası
for k in kelimeler:
    if "last_wrong_date" in k and k.get("wrong_count", 0) > 0:
        try:
            last_wrong = datetime.strptime(k["last_wrong_date"], "%Y-%m-%d")
            weeks_passed = (today - last_wrong.date()).days // 7
            if weeks_passed >= 1:
                score_data["score"] -= 2 * weeks_passed
                k["last_wrong_date"] = today.strftime("%Y-%m-%d")
        except:
            pass

safe_save_data()

# Streamlit arayüzü
st.title("📘 Akademi - İngilizce Kelime Uygulaması")
st.sidebar.write(f"💰 Genel Puan: {score_data['score']}")
st.sidebar.write(f"🕐 Güncel Saat: {current_time.strftime('%H:%M:%S')}")
st.sidebar.write(f"📅 Tarih: {today_str}")

# Menü
menu = st.sidebar.radio(
    "Menü",
    ["🏠 Ana Sayfa", "📝 Testler", "📊 İstatistikler", "➕ Kelime Ekle"],
    key="main_menu"
)

# Ana Sayfa
if menu == "🏠 Ana Sayfa":
    st.header("🏠 Ana Sayfa")
    st.subheader("📅 Tarih ve Saat (İnternet Saati)")
    st.write(current_time.strftime("%Y-%m-%d %H:%M:%S"))
    st.subheader(f"💰 Genel Puan: {score_data['score']}")
    st.progress(min(max(score_data['score'], 0), 100) / 100)

# Testler
elif menu == "📝 Testler":
    st.header("📝 Testler")
    test_secim = st.radio(
        "Bir test seçin:",
        ["Yeni Test", "Yanlış Kelimeler Testi", "Tekrar Test"],
        key="test_menu"
    )

    if test_secim == "Yeni Test":
        st.subheader("Yeni Test")
        if kelimeler:
            # Session state başlatma
            if "test_soru" not in st.session_state:
                st.session_state.test_soru = None
                st.session_state.test_secenekler = None
                st.session_state.test_cevap_verildi = False
                st.session_state.test_sonuc_gosteriliyor = False
                st.session_state.test_sonuc_mesaji = ""

            # Yeni soru oluştur
            if st.session_state.test_soru is None:
                st.session_state.test_soru = random.choice(kelimeler)
                soru = st.session_state.test_soru
                dogru = soru["tr"]
                yanlislar = [k["tr"] for k in kelimeler if k["tr"] != dogru]
                secenekler = random.sample(yanlislar, min(3, len(yanlislar))) if len(yanlislar) >= 3 else yanlislar
                secenekler.append(dogru)
                random.shuffle(secenekler)
                st.session_state.test_secenekler = secenekler
                st.session_state.test_cevap_verildi = False
                st.session_state.test_sonuc_gosteriliyor = False

            soru = st.session_state.test_soru
            dogru = soru["tr"]

            # Sonuç gösteriliyorsa
            if st.session_state.test_sonuc_gosteriliyor:
                if "✅" in st.session_state.test_sonuc_mesaji:
                    st.success(st.session_state.test_sonuc_mesaji)
                else:
                    st.error(st.session_state.test_sonuc_mesaji)

                if st.button("Sonraki Soru", key="sonraki_soru"):
                    st.session_state.test_soru = None
                    st.rerun()
            else:
                # Soru göster
                st.write(f"**{soru['en']}** ne demek?")

                secim = st.radio("Seçenekler:", st.session_state.test_secenekler, key="test_radio")

                if st.button("Cevapla", key="test_cevapla") and not st.session_state.test_cevap_verildi:
                    st.session_state.test_cevap_verildi = True
                    st.session_state.test_sonuc_gosteriliyor = True

                    if secim == dogru:
                        st.session_state.test_sonuc_mesaji = "✅ Doğru!"
                        score_data["score"] += 1
                        score_data["daily"][today_str]["puan"] += 1
                        score_data["daily"][today_str]["dogru"] += 1
                    else:
                        st.session_state.test_sonuc_mesaji = f"❌ Yanlış! Doğru cevap: {dogru}"
                        score_data["score"] -= 2
                        score_data["daily"][today_str]["puan"] -= 2
                        score_data["daily"][today_str]["yanlis"] += 1
                        soru["wrong_count"] = soru.get("wrong_count", 0) + 1
                        soru["last_wrong_date"] = today_str

                    safe_save_data()
                    st.rerun()
        else:
            st.info("Henüz kelime yok. Lütfen önce kelime ekleyin.")

    elif test_secim == "Yanlış Kelimeler Testi":
        st.subheader("Yanlış Kelimeler Testi")
        yanlis_kelimeler = [k for k in kelimeler if k.get("wrong_count", 0) > 0]
        if yanlis_kelimeler:
            # Session state başlatma
            if "yanlis_test_soru" not in st.session_state:
                st.session_state.yanlis_test_soru = None
                st.session_state.yanlis_test_secenekler = None
                st.session_state.yanlis_test_cevap_verildi = False
                st.session_state.yanlis_test_sonuc_gosteriliyor = False
                st.session_state.yanlis_test_sonuc_mesaji = ""

            # Yeni soru oluştur
            if st.session_state.yanlis_test_soru is None:
                st.session_state.yanlis_test_soru = random.choice(yanlis_kelimeler)
                soru = st.session_state.yanlis_test_soru
                dogru = soru["tr"]
                yanlislar = [k["tr"] for k in kelimeler if k["tr"] != dogru]
                secenekler = random.sample(yanlislar, min(3, len(yanlislar))) if len(yanlislar) >= 3 else yanlislar
                secenekler.append(dogru)
                random.shuffle(secenekler)
                st.session_state.yanlis_test_secenekler = secenekler
                st.session_state.yanlis_test_cevap_verildi = False
                st.session_state.yanlis_test_sonuc_gosteriliyor = False

            soru = st.session_state.yanlis_test_soru
            dogru = soru["tr"]

            # Sonuç gösteriliyorsa
            if st.session_state.yanlis_test_sonuc_gosteriliyor:
                if "✅" in st.session_state.yanlis_test_sonuc_mesaji:
                    st.success(st.session_state.yanlis_test_sonuc_mesaji)
                else:
                    st.error(st.session_state.yanlis_test_sonuc_mesaji)

                if st.button("Sonraki Soru", key="yanlis_sonraki_soru"):
                    st.session_state.yanlis_test_soru = None
                    st.rerun()
            else:
                # Soru göster
                st.write(f"**{soru['en']}** ne demek?")
                st.write(f"(Yanlış sayısı: {soru.get('wrong_count', 0)})")

                secim = st.radio("Seçenekler:", st.session_state.yanlis_test_secenekler, key="yanlis_test_radio")

                if st.button("Cevapla", key="yanlis_test_cevapla") and not st.session_state.yanlis_test_cevap_verildi:
                    st.session_state.yanlis_test_cevap_verildi = True
                    st.session_state.yanlis_test_sonuc_gosteriliyor = True

                    if secim == dogru:
                        st.session_state.yanlis_test_sonuc_mesaji = "✅ Doğru! Yanlış sayısı azaldı."
                        soru["wrong_count"] = max(0, soru.get("wrong_count", 0) - 1)
                        if soru["wrong_count"] == 0 and "last_wrong_date" in soru:
                            del soru["last_wrong_date"]
                    else:
                        st.session_state.yanlis_test_sonuc_mesaji = f"❌ Yanlış! Doğru cevap: {dogru}"
                        soru["wrong_count"] = soru.get("wrong_count", 0) + 1
                        soru["last_wrong_date"] = today_str

                    safe_save_data()
                    st.rerun()
        else:
            st.info("Yanlış kelime yok.")

    elif test_secim == "Tekrar Test":
        st.subheader("Tekrar Test")
        if kelimeler:
            # Session state başlatma
            if "tekrar_test_soru" not in st.session_state:
                st.session_state.tekrar_test_soru = None
                st.session_state.tekrar_test_tipi = None
                st.session_state.tekrar_test_secenekler = None
                st.session_state.tekrar_test_cevap_verildi = False
                st.session_state.tekrar_test_sonuc_gosteriliyor = False
                st.session_state.tekrar_test_sonuc_mesaji = ""

            # Yeni soru oluştur
            if st.session_state.tekrar_test_soru is None:
                st.session_state.tekrar_test_soru = random.choice(kelimeler)
                st.session_state.tekrar_test_tipi = random.choice(['en_to_tr', 'tr_to_en'])
                soru = st.session_state.tekrar_test_soru
                soru_tipi = st.session_state.tekrar_test_tipi

                if soru_tipi == 'en_to_tr':
                    dogru = soru["tr"]
                    yanlislar = [k["tr"] for k in kelimeler if k["tr"] != dogru]
                else:
                    dogru = soru["en"]
                    yanlislar = [k["en"] for k in kelimeler if k["en"] != dogru]

                secenekler = random.sample(yanlislar, min(3, len(yanlislar))) if len(yanlislar) >= 3 else yanlislar
                secenekler.append(dogru)
                random.shuffle(secenekler)
                st.session_state.tekrar_test_secenekler = secenekler
                st.session_state.tekrar_test_dogru_cevap = dogru
                st.session_state.tekrar_test_cevap_verildi = False
                st.session_state.tekrar_test_sonuc_gosteriliyor = False

            soru = st.session_state.tekrar_test_soru
            soru_tipi = st.session_state.tekrar_test_tipi
            dogru = st.session_state.tekrar_test_dogru_cevap

            # Sonuç gösteriliyorsa
            if st.session_state.tekrar_test_sonuc_gosteriliyor:
                if "✅" in st.session_state.tekrar_test_sonuc_mesaji:
                    st.success(st.session_state.tekrar_test_sonuc_mesaji)
                else:
                    st.error(st.session_state.tekrar_test_sonuc_mesaji)

                if st.button("Sonraki Soru", key="tekrar_sonraki_soru"):
                    st.session_state.tekrar_test_soru = None
                    st.rerun()
            else:
                # Soru göster
                if soru_tipi == 'en_to_tr':
                    soru_metni = f"🇺🇸 **{soru['en']}** ne demek?"
                else:
                    soru_metni = f"🇹🇷 **{soru['tr']}** kelimesinin İngilizcesi nedir?"

                st.write(soru_metni)

                secim = st.radio("Seçenekler:", st.session_state.tekrar_test_secenekler, key="tekrar_test_radio")

                if st.button("Cevapla", key="tekrar_test_cevapla") and not st.session_state.tekrar_test_cevap_verildi:
                    st.session_state.tekrar_test_cevap_verildi = True
                    st.session_state.tekrar_test_sonuc_gosteriliyor = True

                    if secim == dogru:
                        st.session_state.tekrar_test_sonuc_mesaji = "✅ Doğru!"
                        score_data["score"] += 1
                        score_data["daily"][today_str]["puan"] += 1
                        score_data["daily"][today_str]["dogru"] += 1
                    else:
                        st.session_state.tekrar_test_sonuc_mesaji = f"❌ Yanlış! Doğru cevap: {dogru}"
                        score_data["score"] -= 1
                        score_data["daily"][today_str]["puan"] -= 1
                        score_data["daily"][today_str]["yanlis"] += 1

                    safe_save_data()
                    st.rerun()
        else:
            st.info("Henüz kelime yok. Lütfen önce kelime ekleyin.")

# İstatistikler
elif menu == "📊 İstatistikler":
    st.header("📊 İstatistikler")
    secim = st.radio("Bir seçenek seçin:", ["Günlük İstatistik", "Genel İstatistik", "Yanlış Kelimeler"],
                     key="istat_menu")

    if secim == "Günlük İstatistik":
        st.subheader("📅 Günlük İstatistik")
        if score_data["daily"]:
            daily_df = pd.DataFrame.from_dict(score_data["daily"], orient="index")
            st.dataframe(daily_df)
            st.bar_chart(daily_df["puan"])
        else:
            st.info("Henüz günlük veri yok.")

    elif secim == "Genel İstatistik":
        st.subheader("📊 Genel İstatistik")
        st.write(f"💰 Genel Puan: {score_data['score']}")
        total_dogru = sum([v.get("dogru", 0) for v in score_data["daily"].values()])
        total_yanlis = sum([v.get("yanlis", 0) for v in score_data["daily"].values()])
        st.write(f"✅ Toplam Doğru: {total_dogru}")
        st.write(f"❌ Toplam Yanlış: {total_yanlis}")
        if score_data["daily"]:
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

# Kelime Ekle
elif menu == "➕ Kelime Ekle":
    st.header("➕ Kelime Ekle")
    kelime_secim = st.radio("Bir seçenek seçin:", ["Yeni Kelime Ekle", "Kelime Listesi"], key="kelime_menu")

    if kelime_secim == "Yeni Kelime Ekle":
        st.subheader("Yeni Kelime Ekle")

        with st.form("kelime_form"):
            ing = st.text_input("İngilizce Kelime")
            tr = st.text_input("Türkçe Karşılığı")
            submitted = st.form_submit_button("Kaydet")

            if submitted:
                if ing.strip() and tr.strip():
                    # Aynı kelime var mı kontrol et
                    existing_word = any(k["en"].lower() == ing.strip().lower() for k in kelimeler)
                    if existing_word:
                        st.warning("⚠️ Bu kelime zaten mevcut!")
                    else:
                        # Yeni kelime ekle
                        kelimeler.append({"en": ing.strip(), "tr": tr.strip(), "wrong_count": 0})
                        score_data["daily"][today_str]["yeni_kelime"] += 1
                        score_data["score"] += 1
                        score_data["daily"][today_str]["puan"] += 1

                        if safe_save_data():
                            st.success(f"✅ Kelime kaydedildi: {ing} → {tr}")
                        else:
                            st.error("❌ Kelime kaydedilemedi!")
                else:
                    st.warning("⚠️ İngilizce ve Türkçe kelimeyi doldurun.")

    elif kelime_secim == "Kelime Listesi":
        st.subheader(f"Kelime Listesi (Toplam: {len(kelimeler)})")
        if kelimeler:
            # Sayfalama
            sayfa_basina = 20
            toplam_sayfa = (len(kelimeler) - 1) // sayfa_basina + 1

            if toplam_sayfa > 1:
                sayfa = st.selectbox("Sayfa seçin:", range(1, toplam_sayfa + 1)) - 1
                baslangic = sayfa * sayfa_basina
                bitis = min(baslangic + sayfa_basina, len(kelimeler))
                gosterilecek_kelimeler = kelimeler[baslangic:bitis]
                st.write(f"Sayfa {sayfa + 1}/{toplam_sayfa} - Kelimeler {baslangic + 1}-{bitis}")
            else:
                gosterilecek_kelimeler = kelimeler

            for i, k in enumerate(gosterilecek_kelimeler, 1):
                wrong_count = k.get('wrong_count', 0)
                color = "🔴" if wrong_count >= 3 else "🟡" if wrong_count >= 1 else "🟢"
                st.write(f"{color} {i}. **{k['en']}** → {k['tr']} (Yanlış: {wrong_count})")
        else:
            st.info("Henüz eklenmiş kelime yok.")

# Sidebar - Günlük durum
bugun_kelime = score_data["daily"][today_str]["yeni_kelime"]
st.sidebar.write(f"📚 Bugün eklenen kelime: {bugun_kelime}/10")
if bugun_kelime < 10:
    st.sidebar.warning(f"⚠️ Daha {10 - bugun_kelime} kelime eklemelisin!")
else:
    st.sidebar.success("✅ Günlük kelime hedefi tamamlandı!")

# Toplam kelime sayısı
st.sidebar.write(f"📖 Toplam kelime sayısı: {len(kelimeler)}")

# Yanlış kelime sayısı
yanlis_kelime_sayisi = len([k for k in kelimeler if k.get("wrong_count", 0) > 0])
if yanlis_kelime_sayisi > 0:
    st.sidebar.warning(f"⚠️ {yanlis_kelime_sayisi} yanlış kelime var!")