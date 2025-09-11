import streamlit as st
import json
import os
import random
import shutil
from datetime import datetime, timedelta
import pandas as pd
import requests

DATA_FILE = "kelimeler.json"
SCORE_FILE = "puan.json"
BACKUP_DATA_FILE = "kelimeler_backup.json"
BACKUP_SCORE_FILE = "puan_backup.json"


# -------------------- Yardımcı Fonksiyonlar --------------------

def get_internet_time():
    """İnternet üzerinden güncel zamanı al, başarısız olursa sistem zamanını kullan"""
    try:
        response = requests.get("http://worldtimeapi.org/api/timezone/Europe/Istanbul", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return datetime.fromisoformat(data['datetime'].replace('Z', '+00:00')).replace(tzinfo=None)
    except:
        pass
    return datetime.now()


def create_backup():
    """Veri dosyalarının backup'ını oluştur"""
    try:
        if os.path.exists(DATA_FILE):
            shutil.copy2(DATA_FILE, BACKUP_DATA_FILE)
        if os.path.exists(SCORE_FILE):
            shutil.copy2(SCORE_FILE, BACKUP_SCORE_FILE)
        return True
    except Exception as e:
        st.error(f"Backup oluşturulamadı: {e}")
        return False


def restore_from_backup():
    """Backup dosyalarından verileri geri yükle"""
    try:
        if os.path.exists(BACKUP_DATA_FILE):
            shutil.copy2(BACKUP_DATA_FILE, DATA_FILE)
        if os.path.exists(BACKUP_SCORE_FILE):
            shutil.copy2(BACKUP_SCORE_FILE, SCORE_FILE)
        return True
    except Exception as e:
        st.error(f"Backup'tan geri yükleme başarısız: {e}")
        return False


def safe_save_data():
    """Verileri güvenli bir şekilde kaydet"""
    try:
        # Önce backup oluştur
        create_backup()

        if kelimeler is not None:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(kelimeler, f, ensure_ascii=False, indent=2)
        if score_data is not None:
            with open(SCORE_FILE, "w", encoding="utf-8") as f:
                json.dump(score_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"Veri kaydedilirken hata: {e}")
        # Hata durumunda backup'tan geri yükle
        if restore_from_backup():
            st.warning("Backup'tan geri yükleme yapıldı.")
        return False


def initialize_default_data():
    """Varsayılan veri yapısı oluştur"""
    default_kelimeler = [
        {"en": "abundance", "tr": "bolluk", "wrong_count": 0, "added_date": "2025-01-15"},
        {"en": "acquire", "tr": "edinmek", "wrong_count": 0, "added_date": "2025-01-15"},
        {"en": "ad", "tr": "reklam", "wrong_count": 0, "added_date": "2025-01-15"},
        {"en": "affluence", "tr": "zenginlik", "wrong_count": 0, "added_date": "2025-01-15"},
        {"en": "alliance", "tr": "ortaklık", "wrong_count": 0, "added_date": "2025-01-15"},
    ]

    default_score_data = {
        "score": 25, "daily": {
            "2025-01-15": {"puan": 5, "yeni_kelime": 5, "dogru": 0, "yanlis": 0}
        },
        "last_check_date": "2025-01-15", "answered_today": 0,
        "correct_streak": 0, "wrong_streak": 0, "combo_multiplier": 1.0
    }

    return default_kelimeler, default_score_data


def safe_load_data():
    """Verileri güvenli bir şekilde yükle - Acil durum koruması ile"""
    kelimeler = []
    score_data = {
        "score": 0, "daily": {}, "last_check_date": None, "answered_today": 0,
        "correct_streak": 0, "wrong_streak": 0, "combo_multiplier": 1.0
    }

    # Ana dosyaları yüklemeyi dene
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                kelimeler = json.load(f)
                if not kelimeler:  # Boş dosya kontrolü
                    st.warning("⚠️ Kelimeler dosyası boş, varsayılan veriler yükleniyor...")
                    kelimeler, _ = initialize_default_data()
        else:
            st.info("📝 İlk kez açılıyor, varsayılan veriler yükleniyor...")
            kelimeler, _ = initialize_default_data()

        if os.path.exists(SCORE_FILE):
            with open(SCORE_FILE, "r", encoding="utf-8") as f:
                loaded_score = json.load(f)
                for key in score_data.keys():
                    if key in loaded_score:
                        score_data[key] = loaded_score[key]
        else:
            _, score_data = initialize_default_data()

    except Exception as e:
        st.error(f"Ana dosyalar yüklenirken hata: {e}")

        # Backup'tan yüklemeyi dene
        try:
            if os.path.exists(BACKUP_DATA_FILE):
                with open(BACKUP_DATA_FILE, "r", encoding="utf-8") as f:
                    kelimeler = json.load(f)
                st.success("✅ Kelimeler backup'tan yüklendi!")
            else:
                # Son çare: Varsayılan veriler
                kelimeler, score_data = initialize_default_data()
                st.info("🔄 Varsayılan veriler yüklendi.")

            if os.path.exists(BACKUP_SCORE_FILE):
                with open(BACKUP_SCORE_FILE, "r", encoding="utf-8") as f:
                    loaded_score = json.load(f)
                    for key in score_data.keys():
                        if key in loaded_score:
                            score_data[key] = loaded_score[key]
                st.success("✅ Puan verileri backup'tan yüklendi!")

        except Exception as backup_error:
            st.error(f"Backup'tan yükleme de başarısız: {backup_error}")
            # En son çare: Tamamen yeni başlangıç
            kelimeler, score_data = initialize_default_data()
            st.warning("🆕 Yeni başlangıç verileri oluşturuldu.")

    # Veri doğrulama
    if not isinstance(kelimeler, list):
        kelimeler = []
    if not isinstance(score_data, dict):
        score_data = initialize_default_data()[1]

    return kelimeler, score_data


def get_word_age_days(word):
    """Kelimenin kaç gün önce eklendiğini hesapla"""
    if "added_date" not in word:
        return 0
    try:
        added_date = datetime.strptime(word["added_date"], "%Y-%m-%d").date()
        return (today - added_date).days
    except:
        return 0


def calculate_word_points(word, is_correct):
    """Kelime yaşına göre puan hesapla"""
    age_days = get_word_age_days(word)

    if is_correct:
        if age_days >= 30:  # 1 ay ve üzeri
            return 3
        elif age_days >= 7:  # 1 hafta ve üzeri
            return 2
        else:  # Yeni kelimeler
            return 1
    else:
        # Yanlış cevaplar için sabit -2 puan
        return -2


def update_combo_system(is_correct):
    """Combo sistemini güncelle"""
    if is_correct:
        score_data["correct_streak"] += 1
        score_data["wrong_streak"] = 0

        # Combo multiplier hesapla
        if score_data["correct_streak"] >= 10:
            score_data["combo_multiplier"] = 3.0
        elif score_data["correct_streak"] >= 5:
            score_data["combo_multiplier"] = 2.0
        else:
            score_data["combo_multiplier"] = 1.0

    else:
        score_data["wrong_streak"] += 1
        score_data["correct_streak"] = 0
        score_data["combo_multiplier"] = 1.0

        # Arka arkaya yanlış cezası
        if score_data["wrong_streak"] >= 10:
            return -10  # 10 yanlış cezası
        elif score_data["wrong_streak"] >= 5:
            return -5  # 5 yanlış cezası
        else:
            return 0

    return 0


def check_daily_word_penalty():
    """Günlük kelime ekleme cezasını kontrol et"""
    today_words = score_data["daily"][today_str]["yeni_kelime"]
    if today_words < 10:
        penalty = -20
        score_data["score"] += penalty
        score_data["daily"][today_str]["puan"] += penalty
        return penalty
    return 0


# -------------------- Veriler --------------------

kelimeler, score_data = safe_load_data()
current_time = get_internet_time()
today = current_time.date()
today_str = today.strftime("%Y-%m-%d")

# Günlük verileri kontrol et ve güncelleşitir
if "daily" not in score_data:
    score_data["daily"] = {}

if score_data.get("last_check_date") != today_str:
    # Önceki günün kelime cezasını uygula
    if score_data.get("last_check_date") is not None:
        yesterday_str = score_data["last_check_date"]
        if yesterday_str in score_data["daily"]:
            yesterday_words = score_data["daily"][yesterday_str]["yeni_kelime"]
            if yesterday_words < 10:
                penalty = -20
                score_data["score"] += penalty
                score_data["daily"][yesterday_str]["puan"] += penalty
                st.warning(f"⚠️ Dün {10 - yesterday_words} kelime eksik olduğu için -20 puan kesildi!")

    # Yeni gün için sıfırla
    score_data["answered_today"] = 0
    score_data["last_check_date"] = today_str
    score_data["correct_streak"] = 0
    score_data["wrong_streak"] = 0
    score_data["combo_multiplier"] = 1.0

if today_str not in score_data["daily"]:
    score_data["daily"][today_str] = {"puan": 0, "yeni_kelime": 0, "dogru": 0, "yanlis": 0}

safe_save_data()

# -------------------- Arayüz --------------------

st.set_page_config(page_title="İngilizce Akademi", page_icon="📘", layout="wide")
st.title("📘 Akademi - İngilizce Kelime Uygulaması")

# Sidebar bilgileri
with st.sidebar:
    st.markdown("### 📊 Genel Bilgiler")
    st.write(f"💰 **Genel Puan:** {score_data['score']}")
    st.write(f"🕐 **Güncel Saat:** {current_time.strftime('%H:%M:%S')}")
    st.write(f"📅 **Tarih:** {today_str}")

    st.markdown("### 📈 Günlük Durum")
    bugun_kelime = score_data["daily"][today_str]["yeni_kelime"]
    st.write(f"📚 **Bugün eklenen:** {bugun_kelime}/10 kelime")
    st.write(f"📝 **Cevaplanan soru:** {score_data['answered_today']}")
    st.write(f"📖 **Toplam kelime:** {len(kelimeler)}")

    # Combo durumu
    if score_data.get("correct_streak", 0) > 0:
        st.write(f"🔥 **Doğru serisi:** {score_data['correct_streak']}")
        st.write(f"✨ **Combo:** {score_data.get('combo_multiplier', 1.0)}x")

    if score_data.get("wrong_streak", 0) > 0:
        st.write(f"❌ **Yanlış serisi:** {score_data['wrong_streak']}")

    # Kelime ekleme durumu
    if bugun_kelime < 10:
        st.error(f"⚠️ {10 - bugun_kelime} kelime daha eklemelisiniz!")
        progress = bugun_kelime / 10
    else:
        st.success("✅ Günlük hedef tamamlandı!")
        progress = 1.0

    st.progress(progress)

# Ana menü
menu = st.sidebar.radio(
    "📋 Menü",
    ["🏠 Ana Sayfa", "📝 Testler", "📊 İstatistikler", "➕ Kelime Ekle", "🔧 Ayarlar"],
    key="main_menu"
)

# -------------------- Ana Sayfa --------------------

if menu == "🏠 Ana Sayfa":
    st.header("🏠 Ana Sayfa")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("💰 Genel Puan", score_data['score'])
        st.metric("📖 Toplam Kelime", len(kelimeler))

    with col2:
        bugun_dogru = score_data["daily"][today_str]["dogru"]
        bugun_yanlis = score_data["daily"][today_str]["yanlis"]
        st.metric("✅ Bugün Doğru", bugun_dogru)
        st.metric("❌ Bugün Yanlış", bugun_yanlis)

    with col3:
        if bugun_dogru + bugun_yanlis > 0:
            basari_orani = int((bugun_dogru / (bugun_dogru + bugun_yanlis)) * 100)
            st.metric("🎯 Başarı Oranı", f"{basari_orani}%")
        else:
            st.metric("🎯 Başarı Oranı", "0%")

        combo = score_data.get('combo_multiplier', 1.0)
        if combo > 1.0:
            st.metric("🔥 Combo", f"{combo}x")
        else:
            st.metric("🔥 Combo", "1x")

    # Günlük hedef durumu
    st.subheader("🎯 Günlük Hedefler")

    col1, col2 = st.columns(2)
    with col1:
        st.write("**Kelime Ekleme Hedefi:**")
        bugun_kelime = score_data["daily"][today_str]["yeni_kelime"]
        progress_bar = st.progress(min(bugun_kelime / 10, 1.0))
        st.write(f"{bugun_kelime}/10 kelime eklendi")

    with col2:
        st.write("**Test Çözme Hedefi:**")
        cevaplanan = score_data["answered_today"]
        test_progress = st.progress(min(cevaplanan / 40, 1.0))
        st.write(f"{cevaplanan}/40 soru çözüldü")
        if cevaplanan >= 40:
            st.success("🎉 Puan kazanmaya başladınız!")

# -------------------- Testler --------------------

elif menu == "📝 Testler":
    st.header("📝 Testler")

    if len(kelimeler) < 4:
        st.warning("⚠️ Test çözebilmek için en az 4 kelime olmalı!")
        st.stop()

    test_secim = st.radio(
        "Bir test türü seçin:",
        ["🆕 Yeni Test (EN→TR)", "🇹🇷 Türkçe Test (TR→EN)", "❌ Yanlış Kelimeler", "🔄 Genel Tekrar"],
        key="test_menu"
    )


    def process_answer(is_correct, soru, dogru, test_type):
        """Cevabı işle ve puanları güncelle"""
        score_data["answered_today"] += 1

        # Temel puan hesaplama
        word_points = calculate_word_points(soru, is_correct)

        # Combo sistemini güncelle
        combo_penalty = update_combo_system(is_correct)

        # İlk 40 soruda sadekce eksi puan (Yeni Test ve Türkçe Test için)
        if test_type in ["yeni_test", "turkce_test"] and score_data["answered_today"] <= 40:
            if is_correct:
                final_points = 0  # İlk 40 soruda artı puan yok
            else:
                final_points = word_points  # Eksi puan her zaman var
        else:
            # 40+ sorularda normal puanlama
            if is_correct:
                combo_multiplier = score_data.get("combo_multiplier", 1.0)
                final_points = int(word_points * combo_multiplier)
            else:
                final_points = word_points

        # Combo cezası ekle
        final_points += combo_penalty

        # Puanları güncelle
        score_data["score"] += final_points
        score_data["daily"][today_str]["puan"] += final_points

        if is_correct:
            score_data["daily"][today_str]["dogru"] += 1
            return f"✅ Doğru! (+{final_points} puan)"
        else:
            score_data["daily"][today_str]["yanlis"] += 1
            soru["wrong_count"] = soru.get("wrong_count", 0) + 1
            soru["last_wrong_date"] = today_str

            penalty_msg = f"({final_points} puan)" if final_points != 0 else ""
            combo_msg = ""
            if combo_penalty < 0:
                combo_msg = f" | Seri ceza: {combo_penalty}"

            return f"❌ Yanlış! Doğru cevap: **{dogru}** {penalty_msg}{combo_msg}"


    def soru_goster(soru, dogru, secenekler, test_key, test_type="normal"):
        """Soru göster ve cevabı işle"""
        if f"{test_key}_cevap_verildi" not in st.session_state:
            st.session_state[f"{test_key}_cevap_verildi"] = False
            st.session_state[f"{test_key}_sonuc_mesaji"] = ""

        # Kelime yaşı bilgisi
        age_days = get_word_age_days(soru)
        if age_days > 0:
            if age_days >= 30:
                age_info = f"📅 {age_days} gün önce eklendi (🎯 3 puan)"
            elif age_days >= 7:
                age_info = f"📅 {age_days} gün önce eklendi (🎯 2 puan)"
            else:
                age_info = f"📅 {age_days} gün önce eklendi (🎯 1 puan)"
            st.caption(age_info)

        # Soru ve seçenekler
        secim = st.radio("Seçenekler:", secenekler, key=f"{test_key}_radio")

        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("Cevapla", key=f"{test_key}_cevapla") and not st.session_state[f"{test_key}_cevap_verildi"]:
                st.session_state[f"{test_key}_cevap_verildi"] = True
                st.session_state[f"{test_key}_sonuc_mesaji"] = process_answer(secim == dogru, soru, dogru, test_type)
                safe_save_data()
                st.rerun()

        # Sonuç mesajı göster
        if st.session_state[f"{test_key}_cevap_verildi"]:
            if "✅" in st.session_state[f"{test_key}_sonuc_mesaji"]:
                st.success(st.session_state[f"{test_key}_sonuc_mesaji"])
            else:
                st.error(st.session_state[f"{test_key}_sonuc_mesaji"])

            # Sonraki soru butonu
            if st.button("🔄 Sonraki Soru", key=f"{test_key}_sonraki", use_container_width=True, type="secondary"):
                # Session state'i temizle
                st.session_state[f"{test_key}_cevap_verildi"] = False
                st.session_state[f"{test_key}_sonuc_mesaji"] = ""
                st.session_state[f"{test_key}_selected_answer"] = None
                # Radio button session state'ini de temizle
                if f"{test_key}_radio" in st.session_state:
                    del st.session_state[f"{test_key}_radio"]
                st.rerun()

            # Kelime düzenleme bölümü
            with st.expander("✏️ Kelimeyi Düzenle / Sil"):
                col1, col2 = st.columns(2)
                with col1:
                    yeni_en = st.text_input("İngilizce", soru["en"], key=f"edit_en_{test_key}")
                    yeni_tr = st.text_input("Türkçe", soru["tr"], key=f"edit_tr_{test_key}")

                with col2:
                    if st.button("💾 Kaydet", key=f"save_edit_{test_key}"):
                        if yeni_en.strip() and yeni_tr.strip():
                            soru["en"] = yeni_en.strip()
                            soru["tr"] = yeni_tr.strip()
                            safe_save_data()
                            st.success("✅ Kelime güncellendi!")
                            st.rerun()
                        else:
                            st.error("❌ Boş bırakılamaz!")

                    if st.button("🗑️ Sil", key=f"delete_{test_key}", type="secondary"):
                        kelimeler.remove(soru)
                        safe_save_data()
                        st.warning("🗑️ Kelime silindi!")
                        # Silme işleminden sonra session state'i temizle
                        st.session_state[f"{test_key}_cevap_verildi"] = False
                        st.session_state[f"{test_key}_sonuc_mesaji"] = ""
                        st.session_state[f"{test_key}_selected_answer"] = None
                        if f"{test_key}_radio" in st.session_state:
                            del st.session_state[f"{test_key}_radio"]
                        st.rerun()


    # Test türlerine göre sorular
    if test_secim == "🆕 Yeni Test (EN→TR)":
        soru = random.choice(kelimeler)
        dogru = soru["tr"]
        yanlislar = [k["tr"] for k in kelimeler if k["tr"] != dogru]
        secenekler = random.sample(yanlislar, min(3, len(yanlislar))) + [dogru]
        random.shuffle(secenekler)

        st.write(f"🇺🇸 **{soru['en']}** ne demek?")

        # İlk 40 soru uyarısı
        if score_data["answered_today"] < 40:
            st.info(f"ℹ️ İlk 40 soruda sadece eksi puan verilir. Kalan: {40 - score_data['answered_today']}")

        soru_goster(soru, dogru, secenekler, "yeni_test", "yeni_test")

    elif test_secim == "🇹🇷 Türkçe Test (TR→EN)":
        soru = random.choice(kelimeler)
        dogru = soru["en"]
        yanlislar = [k["en"] for k in kelimeler if k["en"] != dogru]
        secenekler = random.sample(yanlislar, min(3, len(yanlislar))) + [dogru]
        random.shuffle(secenekler)

        st.write(f"🇹🇷 **{soru['tr']}** kelimesinin İngilizcesi nedir?")

        # İlk 40 soru uyarısı
        if score_data["answered_today"] < 40:
            st.info(f"ℹ️ İlk 40 soruda sadece eksi puan verilir. Kalan: {40 - score_data['answered_today']}")

        soru_goster(soru, dogru, secenekler, "turkce_test", "turkce_test")

    elif test_secim == "❌ Yanlış Kelimeler":
        yanlis_kelimeler = [k for k in kelimeler if k.get("wrong_count", 0) > 0]
        if yanlis_kelimeler:
            soru = random.choice(yanlis_kelimeler)
            dogru = soru["tr"]
            yanlislar = [k["tr"] for k in kelimeler if k["tr"] != dogru]
            secenekler = random.sample(yanlislar, min(3, len(yanlislar))) + [dogru]
            random.shuffle(secenekler)

            st.write(f"🇺🇸 **{soru['en']}** ne demek?")
            st.caption(f"❌ Bu kelimeyi {soru.get('wrong_count', 0)} kez yanlış bildiniz")
            soru_goster(soru, dogru, secenekler, "yanlis_test", "yanlis_test")
        else:
            st.success("🎉 Hiç yanlış kelime yok!")

    elif test_secim == "🔄 Genel Tekrar":
        soru = random.choice(kelimeler)
        # Rastgele yön seçimi
        if random.choice([True, False]):
            # EN → TR
            dogru = soru["tr"]
            yanlislar = [k["tr"] for k in kelimeler if k["tr"] != dogru]
            secenekler = random.sample(yanlislar, min(3, len(yanlislar))) + [dogru]
            random.shuffle(secenekler)
            st.write(f"🇺🇸 **{soru['en']}** ne demek?")
            soru_goster(soru, dogru, secenekler, "tekrar_test_en", "tekrar")
        else:
            # TR → EN
            dogru = soru["en"]
            yanlislar = [k["en"] for k in kelimeler if k["en"] != dogru]
            secenekler = random.sample(yanlislar, min(3, len(yanlislar))) + [dogru]
            random.shuffle(secenekler)
            st.write(f"🇹🇷 **{soru['tr']}** kelimesinin İngilizcesi nedir?")
            soru_goster(soru, dogru, secenekler, "tekrar_test_tr", "tekrar")

# -------------------- İstatistikler --------------------

elif menu == "📊 İstatistikler":
    st.header("📊 İstatistikler")

    tab1, tab2, tab3 = st.tabs(["📈 Günlük", "📊 Genel", "❌ Yanlış Kelimeler"])

    with tab1:
        st.subheader("📈 Günlük İstatistikler")
        if score_data["daily"]:
            daily_df = pd.DataFrame.from_dict(score_data["daily"], orient="index")
            daily_df.index = pd.to_datetime(daily_df.index)
            daily_df = daily_df.sort_index()

            col1, col2 = st.columns(2)
            with col1:
                st.metric("📅 Toplam Gün", len(daily_df))
                st.metric("📚 Toplam Eklenen Kelime", daily_df["yeni_kelime"].sum())

            with col2:
                st.metric("💰 Toplam Kazanılan Puan", daily_df["puan"].sum())
                avg_daily = daily_df["puan"].mean()
                st.metric("📊 Günlük Ortalama", f"{avg_daily:.1f}")

            st.subheader("📈 Günlük Puan Grafiği")
            st.line_chart(daily_df["puan"])

            st.subheader("📋 Günlük Detay Tablosu")
            st.dataframe(daily_df.iloc[::-1])  # Tersten sırala
        else:
            st.info("📝 Henüz günlük veri yok.")

    with tab2:
        st.subheader("📊 Genel İstatistikler")

        # Genel metrikler
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("💰 Genel Puan", score_data["score"])
            st.metric("📖 Toplam Kelime", len(kelimeler))

        with col2:
            total_dogru = sum(v.get("dogru", 0) for v in score_data["daily"].values())
            total_yanlis = sum(v.get("yanlis", 0) for v in score_data["daily"].values())
            st.metric("✅ Toplam Doğru", total_dogru)
            st.metric("❌ Toplam Yanlış", total_yanlis)

        with col3:
            if total_dogru + total_yanlis > 0:
                basari_orani = (total_dogru / (total_dogru + total_yanlis)) * 100
                st.metric("🎯 Genel Başarı", f"{basari_orani:.1f}%")
            else:
                st.metric("🎯 Genel Başarı", "0%")

            aktif_gunler = len([d for d in score_data["daily"].values() if d.get("dogru", 0) + d.get("yanlis", 0) > 0])
            st.metric("📅 Aktif Gün", aktif_gunler)

        with col4:
            combo = score_data.get("correct_streak", 0)
            st.metric("🔥 Mevcut Seri", combo)

            yanlis_kelime_sayisi = len([k for k in kelimeler if k.get("wrong_count", 0) > 0])
            st.metric("❌ Yanlış Kelime", yanlis_kelime_sayisi)

        # Kelime yaş dağılımı
        if kelimeler:
            st.subheader("📅 Kelime Yaş Dağılımı")
            age_groups = {"Yeni (0-6 gün)": 0, "Orta (7-29 gün)": 0, "Eski (30+ gün)": 0}

            for word in kelimeler:
                age = get_word_age_days(word)
                if age < 7:
                    age_groups["Yeni (0-6 gün)"] += 1
                elif age < 30:
                    age_groups["Orta (7-29 gün)"] += 1
                else:
                    age_groups["Eski (30+ gün)"] += 1

            age_df = pd.DataFrame(list(age_groups.items()), columns=["Yaş Grubu", "Kelime Sayısı"])
            st.bar_chart(age_df.set_index("Yaş Grubu"))

    with tab3:
        st.subheader("❌ Yanlış Kelimeler")
        yanlis_kelimeler = [k for k in kelimeler if k.get("wrong_count", 0) > 0]

        if yanlis_kelimeler:
            # Yanlış sayısına göre sırala
            yanlis_kelimeler.sort(key=lambda x: x.get("wrong_count", 0), reverse=True)

            col1, col2 = st.columns(2)
            with col1:
                st.metric("❌ Yanlış Kelime Sayısı", len(yanlis_kelimeler))
            with col2:
                total_wrong_count = sum(k.get("wrong_count", 0) for k in yanlis_kelimeler)
                st.metric("🔢 Toplam Yanlış", total_wrong_count)

            st.subheader("📋 Yanlış Kelime Listesi")
            for i, k in enumerate(yanlis_kelimeler[:20], 1):  # İlk 20'yi göster
                col1, col2, col3, col4 = st.columns([1, 3, 3, 2])
                with col1:
                    st.write(f"{i}.")
                with col2:
                    st.write(f"**{k['en']}**")
                with col3:
                    st.write(f"{k['tr']}")
                with col4:
                    st.error(f"❌ {k.get('wrong_count', 0)}")

            if len(yanlis_kelimeler) > 20:
                st.info(f"➕ {len(yanlis_kelimeler) - 20} kelime daha var...")

        else:
            st.success("🎉 Hiç yanlış kelime yok! Mükemmel performans!")

# -------------------- Kelime Ekle --------------------

elif menu == "➕ Kelime Ekle":
    st.header("➕ Kelime Ekle")

    tab1, tab2 = st.tabs(["➕ Yeni Kelime", "📚 Kelime Listesi"])

    with tab1:
        st.subheader("➕ Yeni Kelime Ekle")

        # Günlük hedef göstergesi
        bugun_kelime = score_data["daily"][today_str]["yeni_kelime"]
        st.progress(min(bugun_kelime / 10, 1.0))
        st.caption(f"Günlük hedef: {bugun_kelime}/10 kelime eklendi")

        with st.form("kelime_form", clear_on_submit=True):
            col1, col2 = st.columns(2)

            with col1:
                ing = st.text_input("🇺🇸 İngilizce Kelime", placeholder="örn: apple")

            with col2:
                tr = st.text_input("🇹🇷 Türkçe Karşılığı", placeholder="örn: elma")

            submitted = st.form_submit_button("💾 Kaydet", use_container_width=True)

            if submitted:
                if ing.strip() and tr.strip():
                    # Kelime zaten var mı kontrol et
                    existing_word = any(k["en"].lower() == ing.strip().lower() for k in kelimeler)
                    if existing_word:
                        st.error("⚠️ Bu kelime zaten mevcut!")
                    else:
                        # Yeni kelime ekle
                        yeni_kelime = {
                            "en": ing.strip().lower(),
                            "tr": tr.strip().lower(),
                            "wrong_count": 0,
                            "added_date": today_str,
                            "last_wrong_date": None
                        }

                        kelimeler.append(yeni_kelime)
                        score_data["daily"][today_str]["yeni_kelime"] += 1

                        # Kelime ekleme puanı (her zaman verilir)
                        score_data["score"] += 1
                        score_data["daily"][today_str]["puan"] += 1

                        if safe_save_data():
                            st.success(f"✅ Kelime kaydedildi: **{ing.strip()}** → **{tr.strip()}** (+1 puan)")

                            # Günlük hedef tamamlandı mı?
                            if score_data["daily"][today_str]["yeni_kelime"] == 10:
                                st.balloons()
                                st.success("🎉 Günlük kelime hedefi tamamlandı!")
                        else:
                            st.error("❌ Kayıt sırasında hata oluştu!")
                else:
                    st.warning("⚠️ İngilizce ve Türkçe kelimeyi doldurun.")

    with tab2:
        st.subheader("📚 Kelime Listesi")

        if kelimeler:
            # Filtreleme seçenekleri
            col1, col2, col3 = st.columns(3)

            with col1:
                filtre = st.selectbox(
                    "Filtrele:",
                    ["Tümü", "Bugün Eklenenler", "Bu Hafta", "Yanlış Olanlar"],
                    key="word_filter"
                )

            with col2:
                siralama = st.selectbox(
                    "Sırala:",
                    ["En Yeni", "En Eski", "Alfabetik", "En Çok Yanlış"],
                    key="word_sort"
                )

            with col3:
                arama = st.text_input("🔍 Kelime Ara:", placeholder="Kelime ara...")

            # Kelimeleri filtrele
            filtered_words = kelimeler.copy()

            if filtre == "Bugün Eklenenler":
                filtered_words = [k for k in kelimeler if k.get("added_date") == today_str]
            elif filtre == "Bu Hafta":
                week_ago = (today - timedelta(days=7)).strftime("%Y-%m-%d")
                filtered_words = [k for k in kelimeler if k.get("added_date", "") >= week_ago]
            elif filtre == "Yanlış Olanlar":
                filtered_words = [k for k in kelimeler if k.get("wrong_count", 0) > 0]

            # Arama filtresi
            if arama:
                filtered_words = [k for k in filtered_words
                                  if arama.lower() in k["en"].lower() or arama.lower() in k["tr"].lower()]

            # Sıralama
            if siralama == "En Yeni":
                filtered_words.sort(key=lambda x: x.get("added_date", ""), reverse=True)
            elif siralama == "En Eski":
                filtered_words.sort(key=lambda x: x.get("added_date", ""))
            elif siralama == "Alfabetik":
                filtered_words.sort(key=lambda x: x["en"])
            elif siralama == "En Çok Yanlış":
                filtered_words.sort(key=lambda x: x.get("wrong_count", 0), reverse=True)

            st.write(f"📊 {len(filtered_words)} kelime gösteriliyor")

            # Kelimeleri göster (sayfalama ile)
            page_size = 20
            total_pages = (len(filtered_words) + page_size - 1) // page_size

            if total_pages > 1:
                page = st.selectbox("Sayfa:", range(1, total_pages + 1)) - 1
                start_idx = page * page_size
                end_idx = min(start_idx + page_size, len(filtered_words))
                words_to_show = filtered_words[start_idx:end_idx]
            else:
                words_to_show = filtered_words

            # Kelime listesi tablosu
            for i, k in enumerate(words_to_show, 1):
                with st.container():
                    col1, col2, col3, col4, col5 = st.columns([1, 3, 3, 2, 2])

                    with col1:
                        st.write(f"**{i}.**")

                    with col2:
                        st.write(f"🇺🇸 **{k['en']}**")

                    with col3:
                        st.write(f"🇹🇷 {k['tr']}")

                    with col4:
                        age_days = get_word_age_days(k)
                        if age_days == 0:
                            st.caption("🆕 Bugün")
                        else:
                            st.caption(f"📅 {age_days} gün")

                    with col5:
                        wrong_count = k.get("wrong_count", 0)
                        if wrong_count > 0:
                            st.error(f"❌ {wrong_count}")
                        else:
                            st.success("✅ 0")

                    st.divider()
        else:
            st.info("📝 Henüz eklenmiş kelime yok.")

# -------------------- Ayarlar --------------------

elif menu == "🔧 Ayarlar":
    st.header("🔧 Ayarlar")

    tab1, tab2, tab3 = st.tabs(["💾 Veri Yönetimi", "🎯 Hedefler", "ℹ️ Bilgi"])

    with tab1:
        st.subheader("💾 Veri Yönetimi")

        col1, col2 = st.columns(2)

        with col1:
            st.write("**Backup İşlemleri:**")
            if st.button("💾 Manuel Backup Oluştur", use_container_width=True):
                if create_backup():
                    st.success("✅ Backup başarıyla oluşturuldu!")
                else:
                    st.error("❌ Backup oluşturulamadı!")

            if st.button("🔄 Backup'tan Geri Yükle", use_container_width=True):
                if os.path.exists(BACKUP_DATA_FILE) and os.path.exists(BACKUP_SCORE_FILE):
                    if st.button("⚠️ Onaylıyorum", key="confirm_restore"):
                        if restore_from_backup():
                            st.success("✅ Backup'tan geri yüklendi!")
                            st.rerun()
                        else:
                            st.error("❌ Geri yükleme başarısız!")
                else:
                    st.warning("⚠️ Backup dosyası bulunamadı!")

        with col2:
            st.write("**Dosya Durumu:**")
            st.write(f"📄 Kelime dosyası: {'✅' if os.path.exists(DATA_FILE) else '❌'}")
            st.write(f"📊 Puan dosyası: {'✅' if os.path.exists(SCORE_FILE) else '❌'}")
            st.write(f"💾 Kelime backup: {'✅' if os.path.exists(BACKUP_DATA_FILE) else '❌'}")
            st.write(f"💾 Puan backup: {'✅' if os.path.exists(BACKUP_SCORE_FILE) else '❌'}")

            if st.button("🔄 Verileri Yenile", use_container_width=True):
                st.rerun()

        st.divider()

        st.subheader("⚠️ Tehlikeli İşlemler")
        st.warning("Bu işlemler geri alınamaz!")

        col1, col2 = st.columns(2)

        with col1:
            st.write("**📥 Veri İçe Aktarma:**")
            uploaded_kelimeler = st.file_uploader("Kelimeler JSON", type=['json'], key="upload_kelimeler")
            uploaded_puan = st.file_uploader("Puan JSON", type=['json'], key="upload_puan")

            if st.button("📥 İçe Aktar", type="primary"):
                try:
                    if uploaded_kelimeler:
                        kelimeler_data = json.loads(uploaded_kelimeler.read())
                        kelimeler.clear()
                        kelimeler.extend(kelimeler_data)
                        st.success("✅ Kelimeler içe aktarıldı!")

                    if uploaded_puan:
                        puan_data = json.loads(uploaded_puan.read())
                        score_data.update(puan_data)
                        st.success("✅ Puan verileri içe aktarıldı!")

                    if uploaded_kelimeler or uploaded_puan:
                        safe_save_data()
                        st.rerun()

                except Exception as e:
                    st.error(f"❌ İçe aktarma hatası: {e}")

        with col2:
            st.write("**📤 Veri Dışa Aktarma:**")

            if st.button("📤 Kelimeleri İndir", use_container_width=True):
                kelimeler_json = json.dumps(kelimeler, ensure_ascii=False, indent=2)
                st.download_button(
                    "⬇️ kelimeler.json İndir",
                    kelimeler_json,
                    "kelimeler_backup.json",
                    "application/json"
                )

            if st.button("📤 Puanları İndir", use_container_width=True):
                puan_json = json.dumps(score_data, ensure_ascii=False, indent=2)
                st.download_button(
                    "⬇️ puan.json İndir",
                    puan_json,
                    "puan_backup.json",
                    "application/json"
                )

        st.divider()

        if st.button("🗑️ Tüm Verileri Sıfırla", type="secondary"):
            if st.button("⚠️ EMİNİM, SİL!", key="confirm_reset"):
                kelimeler.clear()
                score_data.clear()
                score_data.update({
                    "score": 0, "daily": {}, "last_check_date": None,
                    "answered_today": 0, "correct_streak": 0, "wrong_streak": 0,
                    "combo_multiplier": 1.0
                })
                if safe_save_data():
                    st.success("✅ Tüm veriler sıfırlandı!")
                    st.rerun()

    with tab2:
        st.subheader("🎯 Hedefler ve Kurallar")

        st.write("**📚 Kelime Ekleme:**")
        st.info(
            "• Her gün en az 10 kelime eklenmeli\n• Eksik kelime başına -20 puan cezası\n• Her eklenen kelime +1 puan")

        st.write("**📝 Test Puanlaması:**")
        st.info(
            "• İlk 40 soruda sadece eksi puan verilir\n"
            "• 40+ sorularda yaş bazlı puanlama:\n"
            "  - Yeni kelimeler (0-6 gün): +1 puan\n"
            "  - Orta kelimeler (7-29 gün): +2 puan\n"
            "  - Eski kelimeler (30+ gün): +3 puan\n"
            "• Yanlış cevap: -2 puan"
        )

        st.write("**🔥 Combo Sistemi:**")
        st.info(
            "• 5 doğru arka arkaya: 2x puan\n"
            "• 10 doğru arka arkaya: 3x puan\n"
            "• 5 yanlış arka arkaya: -5 puan cezası\n"
            "• 10 yanlış arka arkaya: -10 puan cezası"
        )

    with tab3:
        st.subheader("ℹ️ Uygulama Bilgileri")

        st.write("**🔧 Versiyon:** 2.0 - Gelişmiş")
        st.write("**📅 Son Güncelleme:** Bugün")
        st.write("**🎯 Özellikler:**")

        features = [
            "✅ Otomatik backup sistemi",
            "✅ Yaş bazlı puanlama",
            "✅ Combo sistemi",
            "✅ Günlük hedef takibi",
            "✅ Gelişmiş istatistikler",
            "✅ Kelime düzenleme",
            "✅ Veri güvenliği",
            "✅ Mobil uyumlu arayüz"
        ]

        for feature in features:
            st.write(feature)

# -------------------- Alt Bilgi --------------------

with st.sidebar:
    st.divider()
    st.caption("📘 İngilizce Akademi v2.0")
    st.caption("💾 Otomatik backup aktif")
    if len(kelimeler) > 0:
        st.caption(f"🔄 Son güncelleme: {current_time.strftime('%H:%M')}")

# Otomatik kaydetme (her 10 saniyede bir)
if st.session_state.get('last_save_time', 0) + 10 < current_time.timestamp():
    safe_save_data()
    st.session_state['last_save_time'] = current_time.timestamp()
    st.session_state['last_save_time'] = current_time.timestamp()