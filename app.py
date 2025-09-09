import streamlit as st
import json
import os
import random
from datetime import datetime, timedelta
import pandas as pd

DATA_FILE = "kelimeler.json"
SCORE_FILE = "puan.json"

# Kelime dosyasını yükle veya oluştur
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        kelimeler = json.load(f)
else:
    kelimeler = []

# Puan dosyasını yükle veya oluştur
if os.path.exists(SCORE_FILE):
    with open(SCORE_FILE, "r", encoding="utf-8") as f:
        score_data = json.load(f)
else:
    score_data = {"score": 0, "daily": {}}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(kelimeler, f, ensure_ascii=False, indent=2)
    with open(SCORE_FILE, "w", encoding="utf-8") as f:
        json.dump(score_data, f, ensure_ascii=False, indent=2)

today = datetime.today()
today_str = today.strftime("%Y-%m-%d")

# Günlük veri kontrolü
if "daily" not in score_data:
    score_data["daily"] = {}
if today_str not in score_data["daily"]:
    score_data["daily"][today_str] = {"puan": 0, "yeni_kelime": 0, "dogru": 0, "yanlis": 0}

# Haftalık ceza
for k in kelimeler:
    if "last_wrong_date" in k and k.get("wrong_count",0) > 0:
        last_wrong = datetime.strptime(k["last_wrong_date"], "%Y-%m-%d")
        weeks_passed = (today - last_wrong).days // 7
        if weeks_passed >= 1:
            score_data["score"] -= 2 * weeks_passed
            k["last_wrong_date"] = today.strftime("%Y-%m-%d")

save_data()

st.title("📘 Akademi - İngilizce Kelime Uygulaması")

# Ana sayfa üstü
st.sidebar.write(f"💰 Genel Puan: {score_data['score']}")

# Menü
menu = st.sidebar.radio(
    "Menü",
    ["🏠 Ana Sayfa", "📝 Testler", "📊 İstatistikler", "➕ Kelime Ekle"],
    key="main_menu"
)

# --- Ana Sayfa ---
if menu == "🏠 Ana Sayfa":
    st.header("🏠 Ana Sayfa")
    st.subheader("📅 Tarih ve Saat")
    st.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    st.subheader(f"💰 Genel Puan: {score_data['score']}")
    st.progress(min(max(score_data['score'],0),100)/100)

# --- Testler ---
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
            soru = random.choice(kelimeler)
            dogru = soru["tr"]

            yanlisler = [k["tr"] for k in kelimeler if k["tr"] != dogru]
            secenekler = random.sample(yanlisler, min(3, len(yanlisler)))
            secenekler.append(dogru)
            random.shuffle(secenekler)

            secim = st.radio(f"{soru['en']} ne demek?", secenekler, key="soru_radio")

            if st.button("Cevapla", key="cevapla_btn"):
                if secim == dogru:
                    st.success("✅ Doğru!")
                    score_data["score"] += 1
                    score_data["daily"][today_str]["puan"] += 1
                    score_data["daily"][today_str]["dogru"] += 1
                    if soru.get("wrong_count", 0) > 0:
                        soru["wrong_count"] -= 1
                        if soru["wrong_count"] <= 0 and "last_wrong_date" in soru:
                            del soru["last_wrong_date"]
                else:
                    st.error(f"❌ Yanlış! Doğru cevap: {dogru}")
                    score_data["score"] -= 2
                    score_data["daily"][today_str]["puan"] -= 2
                    score_data["daily"][today_str]["yanlis"] += 1
                    soru["wrong_count"] = soru.get("wrong_count", 0) + 1
                    soru["last_wrong_date"] = today_str
                save_data()
        else:
            st.info("Henüz kelime yok. Lütfen önce kelime ekleyin.")

    elif test_secim == "Yanlış Kelimeler Testi":
        st.subheader("Yanlış Kelimeler Testi")
        yanlis_kelimeler = [k for k in kelimeler if k.get("wrong_count",0) > 0]
        if yanlis_kelimeler:
            soru = random.choice(yanlis_kelimeler)
            dogru = soru["tr"]
            yanlisler = [k["tr"] for k in kelimeler if k["tr"] != dogru]
            secenekler = random.sample(yanlisler, min(3,len(yanlisler)))
            secenekler.append(dogru)
            random.shuffle(secenekler)

            secim = st.radio(f"{soru['en']} ne demek?", secenekler, key="yanlis_radio")
            if st.button("Cevapla Yanlış Test", key="yanlis_btn"):
                if secim == dogru:
                    st.success("✅ Doğru!")
                    soru["wrong_count"] -= 1
                    if soru["wrong_count"] <= 0:
                        if "last_wrong_date" in soru:
                            del soru["last_wrong_date"]
                        soru["wrong_count"] = 0
                else:
                    st.error(f"❌ Yanlış! Doğru cevap: {dogru}")
                save_data()
        else:
            st.info("Yanlış kelime yok.")

# --- İstatistikler ---
elif menu == "📊 İstatistikler":
    st.header("📊 İstatistikler")
    secim = st.radio("Bir seçenek seçin:", ["Günlük İstatistik", "Genel İstatistik", "Yanlış Kelimeler"], key="istat_menu")

    if secim == "Günlük İstatistik":
        st.subheader("📅 Günlük İstatistik")
        daily_df = pd.DataFrame.from_dict(score_data["daily"], orient="index")
        st.dataframe(daily_df)

        # Günlük puan grafiği - Streamlit bar_chart
        puanlar = daily_df["puan"]
        st.bar_chart(puanlar)

    elif secim == "Genel İstatistik":
        st.subheader("📊 Genel İstatistik")
        st.write(f"💰 Genel Puan: {score_data['score']}")
        total_dogru = sum([v.get("dogru",0) for v in score_data["daily"].values()])
        total_yanlis = sum([v.get("yanlis",0) for v in score_data["daily"].values()])
        st.write(f"✅ Toplam Doğru: {total_dogru}")
        st.write(f"❌ Toplam Yanlış: {total_yanlis}")

        # Toplam puan grafiği - Streamlit line_chart
        daily_cumsum = daily_df["puan"].cumsum()
        st.line_chart(daily_cumsum)

    elif secim == "Yanlış Kelimeler":
        st.subheader("❌ Yanlış Kelimeler")
        yanlis_kelimeler = [k for k in kelimeler if k.get("wrong_count",0) > 0]
        if yanlis_kelimeler:
            for k in yanlis_kelimeler:
                color = "red" if k.get("wrong_count",0)>=3 else "orange" if k.get("wrong_count",0)==2 else "black"
                st.markdown(f"<span style='color:{color}'>{k['en']} → {k['tr']} | Yanlış sayısı: {k.get('wrong_count',0)} | Son yanlış: {k.get('last_wrong_date','-')}</span>", unsafe_allow_html=True)
        else:
            st.info("Yanlış kelime yok.")

# --- Kelime Ekle ---
elif menu == "➕ Kelime Ekle":
    st.header("➕ Kelime Ekle")
    kelime_secim = st.radio(
        "Bir seçenek seçin:",
        ["Yeni Kelime Ekle", "Kelime Listesi"],
        key="kelime_menu"
    )

    if kelime_secim == "Yeni Kelime Ekle":
        st.subheader("Yeni Kelime Ekle")
        ing = st.text_input("İngilizce Kelime", key="ing_input")
        tr = st.text_input("Türkçe Karşılığı", key="tr_input")
        if st.button("Kaydet", key="save_btn"):
            if ing.strip() != "" and tr.strip() != "":
                kelimeler.append({"en": ing.strip(), "tr": tr.strip(), "wrong_count": 0})
                score_data["daily"][today_str]["yeni_kelime"] += 1
                save_data()
                st.success(f"Kelime kaydedildi: {ing} → {tr}")
            else:
                st.warning("İngilizce ve Türkçe kelimeyi doldurun.")

    elif kelime_secim == "Kelime Listesi":
        st.subheader("Kelime Listesi")
        if kelimeler:
            for k in kelimeler:
                st.write(f"{k['en']} → {k['tr']} (Yanlış sayısı: {k.get('wrong_count',0)})")
        else:
            st.info("Henüz eklenmiş kelime yok.")
