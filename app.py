import streamlit as st
import json
import os
import random
import shutil
from datetime import datetime, timedelta
import pandas as pd
import requests
import zipfile
import io

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


def create_complete_backup_zip():
    """Tam yedekleme ZIP dosyası oluştur"""
    try:
        backup_data = {
            'kelimeler': kelimeler,
            'score_data': score_data,
            'backup_date': datetime.now().isoformat(),
            'app_version': '2.2',
            'total_words': len(kelimeler),
            'total_score': score_data.get('score', 0)
        }

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Ana veriler
            zip_file.writestr("kelimeler.json", json.dumps(kelimeler, ensure_ascii=False, indent=2))
            zip_file.writestr("puan.json", json.dumps(score_data, ensure_ascii=False, indent=2))
            # Yedekleme bilgileri
            zip_file.writestr("backup_info.json", json.dumps(backup_data, ensure_ascii=False, indent=2))

        return zip_buffer.getvalue()
    except Exception as e:
        st.error(f"ZIP oluşturma hatası: {e}")
        return None


def validate_backup_data(kelimeler_data, score_data_backup):
    """Yedekleme verilerini doğrula"""
    errors = []
    warnings = []

    # Kelimeler doğrulama
    if not isinstance(kelimeler_data, list):
        errors.append("Kelimeler verisi liste formatında değil")
    else:
        for i, kelime in enumerate(kelimeler_data):
            if not isinstance(kelime, dict):
                errors.append(f"Kelime {i + 1}: Dict formatında değil")
            elif not all(key in kelime for key in ['en', 'tr']):
                errors.append(f"Kelime {i + 1}: 'en' veya 'tr' alanı eksik")
            else:
                # Eksik alanları varsayılan değerlerle doldur
                if 'wrong_count' not in kelime:
                    kelime['wrong_count'] = 0
                    warnings.append(f"Kelime '{kelime.get('en', 'bilinmiyor')}': wrong_count eklendi")
                if 'added_date' not in kelime:
                    kelime['added_date'] = datetime.now().strftime("%Y-%m-%d")
                    warnings.append(f"Kelime '{kelime.get('en', 'bilinmiyor')}': added_date eklendi")

    # Puan verileri doğrulama
    if not isinstance(score_data_backup, dict):
        errors.append("Puan verisi dict formatında değil")
    else:
        # Zorunlu alanları kontrol et ve eksikleri ekle
        required_fields = {
            'score': 0,
            'daily': {},
            'last_check_date': None,
            'answered_today': 0,
            'correct_streak': 0,
            'wrong_streak': 0,
            'combo_multiplier': 1.0,
            'en_tr_answered': 0,
            'tr_en_answered': 0,
            'tekrar_answered': 0
        }

        for field, default_value in required_fields.items():
            if field not in score_data_backup:
                score_data_backup[field] = default_value
                warnings.append(f"Puan verisi: '{field}' alanı eklendi")

        # Daily verilerini kontrol et
        if 'daily' in score_data_backup and isinstance(score_data_backup['daily'], dict):
            for date_str, day_data in score_data_backup['daily'].items():
                if not isinstance(day_data, dict):
                    errors.append(f"Günlük veri {date_str}: Dict formatında değil")
                else:
                    # Günlük veri için gerekli alanlar
                    daily_required = {
                        'puan': 0,
                        'yeni_kelime': 0,
                        'dogru': 0,
                        'yanlis': 0,
                        'en_tr_answered': 0,
                        'tr_en_answered': 0,
                        'tekrar_answered': 0
                    }

                    for field, default_value in daily_required.items():
                        if field not in day_data:
                            day_data[field] = default_value

    return errors, warnings


def restore_from_complete_backup(kelimeler_data, score_data_backup, preserve_daily_progress=True):
    """Tam yedeklemeden geri yükle"""
    try:
        global kelimeler, score_data

        # Verileri doğrula
        errors, warnings = validate_backup_data(kelimeler_data, score_data_backup)

        if errors:
            return False, f"Doğrulama hataları: {'; '.join(errors)}"

        # Mevcut günlük ilerlemeyi koru
        if preserve_daily_progress and today_str in score_data.get('daily', {}):
            current_daily = score_data['daily'][today_str].copy()
            current_counters = {
                'en_tr_answered': score_data.get('en_tr_answered', 0),
                'tr_en_answered': score_data.get('tr_en_answered', 0),
                'tekrar_answered': score_data.get('tekrar_answered', 0),
                'answered_today': score_data.get('answered_today', 0),
                'correct_streak': score_data.get('correct_streak', 0),
                'wrong_streak': score_data.get('wrong_streak', 0),
                'combo_multiplier': score_data.get('combo_multiplier', 1.0)
            }
        else:
            current_daily = None
            current_counters = None

        # Kelimeleri kontrol et ve tarihlere göre günlük hedefleri güncelle
        word_dates = {}
        for kelime in kelimeler_data:
            added_date = kelime.get('added_date')
            if added_date:
                if added_date not in word_dates:
                    word_dates[added_date] = 0
                word_dates[added_date] += 1

        # Yedeklenen verileri yükle
        kelimeler.clear()
        kelimeler.extend(kelimeler_data)
        score_data.clear()
        score_data.update(score_data_backup)

        # Kelime tarihlerine göre günlük hedefleri güncelle
        for date_str, word_count in word_dates.items():
            if date_str not in score_data['daily']:
                score_data['daily'][date_str] = {
                    'puan': word_count,  # Kelime ekleme puanı
                    'yeni_kelime': word_count,
                    'dogru': 0,
                    'yanlis': 0,
                    'en_tr_answered': 0,
                    'tr_en_answered': 0,
                    'tekrar_answered': 0
                }
            else:
                # Mevcut günlük veriye kelime sayısını ekle (eğer eksikse)
                if score_data['daily'][date_str]['yeni_kelime'] < word_count:
                    diff = word_count - score_data['daily'][date_str]['yeni_kelime']
                    score_data['daily'][date_str]['yeni_kelime'] = word_count
                    score_data['daily'][date_str]['puan'] += diff  # Eksik puanları ekle

        # Mevcut günlük ilerlemeyi geri yükle
        if current_daily and preserve_daily_progress:
            score_data['daily'][today_str] = current_daily
            score_data.update(current_counters)
            score_data['last_check_date'] = today_str

        # Verileri kaydet
        if safe_save_data():
            warning_msg = f" Uyarılar: {len(warnings)} alan otomatik düzeltildi." if warnings else ""
            return True, f"Veriler başarıyla yüklendi!{warning_msg}"
        else:
            return False, "Veriler yüklenirken kaydetme hatası oluştu"

    except Exception as e:
        return False, f"Geri yükleme hatası: {str(e)}"


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
        "score": 25,
        "daily": {
            "2025-01-15": {"puan": 5, "yeni_kelime": 5, "dogru": 0, "yanlis": 0,
                           "en_tr_answered": 0, "tr_en_answered": 0, "tekrar_answered": 0}
        },
        "last_check_date": "2025-01-15",
        "answered_today": 0,
        "correct_streak": 0,
        "wrong_streak": 0,
        "combo_multiplier": 1.0,
        "en_tr_answered": 0,
        "tr_en_answered": 0,
        "tekrar_answered": 0
    }

    return default_kelimeler, default_score_data


def safe_load_data():
    """Verileri güvenli bir şekilde yükle - Acil durum koruması ile"""
    kelimeler = []
    score_data = {
        "score": 0, "daily": {}, "last_check_date": None, "answered_today": 0,
        "correct_streak": 0, "wrong_streak": 0, "combo_multiplier": 1.0,
        "en_tr_answered": 0, "tr_en_answered": 0, "tekrar_answered": 0
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
                    loaded_score = json.loads(f)
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

    # Yeni alanları ekle (geriye dönük uyumluluk için)
    if "en_tr_answered" not in score_data:
        score_data["en_tr_answered"] = 0
    if "tr_en_answered" not in score_data:
        score_data["tr_en_answered"] = 0
    if "tekrar_answered" not in score_data:
        score_data["tekrar_answered"] = 0

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


def get_word_age_category(word):
    """Kelimenin yaş kategorisini döndür"""
    age_days = get_word_age_days(word)
    if age_days < 7:
        return "yeni"  # 0-6 gün
    elif age_days < 30:
        return "orta"  # 7-29 gün
    else:
        return "eski"  # 30+ gün


def select_word_by_probability(test_type):
    """Test türüne göre kelime seç - yaş kategorisi olasılıklarına göre"""
    if not kelimeler:
        return None

    # Kelimeleri yaş kategorilerine göre ayır
    yeni_kelimeler = [k for k in kelimeler if get_word_age_category(k) == "yeni"]
    orta_kelimeler = [k for k in kelimeler if get_word_age_category(k) == "orta"]
    eski_kelimeler = [k for k in kelimeler if get_word_age_category(k) == "eski"]

    # Test türüne göre olasılıkları belirle
    if test_type in ["en_tr", "tr_en"]:
        # Yeni test ve Türkçe test: %50 yeni, %30 orta, %20 eski
        probabilities = [0.5, 0.3, 0.2]
    elif test_type == "tekrar":
        # Genel tekrar: %20 yeni, %30 orta, %50 eski
        probabilities = [0.2, 0.3, 0.5]
    else:
        # Yanlış kelimeler için normal seçim
        return random.choice(kelimeler)

    # Mevcut kelimelere göre kategorileri hazırla
    categories = []
    if yeni_kelimeler:
        categories.append(("yeni", yeni_kelimeler, probabilities[0]))
    if orta_kelimeler:
        categories.append(("orta", orta_kelimeler, probabilities[1]))
    if eski_kelimeler:
        categories.append(("eski", eski_kelimeler, probabilities[2]))

    if not categories:
        return random.choice(kelimeler)

    # Olasılıkları normalize et
    total_prob = sum(cat[2] for cat in categories)
    normalized_probs = [cat[2] / total_prob for cat in categories]

    # Rastgele seçim yap
    rand_val = random.random()
    cumulative_prob = 0

    for i, (category_name, category_words, _) in enumerate(categories):
        cumulative_prob += normalized_probs[i]
        if rand_val <= cumulative_prob:
            return random.choice(category_words)

    # Fallback
    return random.choice(categories[-1][1])


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


def is_daily_test_goal_complete():
    """Günlük test hedeflerinin tamamlanıp tamamlanmadığını kontrol et"""
    en_tr_complete = score_data.get("en_tr_answered", 0) >= 30
    tr_en_complete = score_data.get("tr_en_answered", 0) >= 30
    tekrar_complete = score_data.get("tekrar_answered", 0) >= 30
    return en_tr_complete and tr_en_complete and tekrar_complete


def get_test_progress_info(test_type):
    """Test türü için ilerleme bilgisini döndür"""
    if test_type == "en_tr":
        current = score_data.get("en_tr_answered", 0)
        target = 30
        test_name = "EN→TR"
    elif test_type == "tr_en":
        current = score_data.get("tr_en_answered", 0)
        target = 30
        test_name = "TR→EN"
    elif test_type == "tekrar":
        current = score_data.get("tekrar_answered", 0)
        target = 30
        test_name = "Genel Tekrar"
    else:
        return None, None, None

    return current, target, test_name


def can_earn_points(test_type):
    """Bu test türünde puan kazanılabilir mi kontrol et"""
    # Yanlış kelime testinde her zaman puan alınabilir
    if test_type == "yanlis":
        return True

    # Diğer testlerde günlük hedef tamamlanmış mı kontrol et
    return is_daily_test_goal_complete()


def generate_question(test_type):
    """Test türüne göre soru üret ve session state'e kaydet"""
    if test_type == "en_tr":
        soru = select_word_by_probability("en_tr")
        dogru = soru["tr"]
        yanlislar = [k["tr"] for k in kelimeler if k["tr"] != dogru]
        secenekler = random.sample(yanlislar, min(3, len(yanlislar))) + [dogru]
        random.shuffle(secenekler)
        question_text = f"🇺🇸 **{soru['en']}** ne demek?"

    elif test_type == "tr_en":
        soru = select_word_by_probability("tr_en")
        dogru = soru["en"]
        yanlislar = [k["en"] for k in kelimeler if k["en"] != dogru]
        secenekler = random.sample(yanlislar, min(3, len(yanlislar))) + [dogru]
        random.shuffle(secenekler)
        question_text = f"🇹🇷 **{soru['tr']}** kelimesinin İngilizcesi nedir?"

    elif test_type == "yanlis":
        yanlis_kelimeler = [k for k in kelimeler if k.get("wrong_count", 0) > 0]
        if not yanlis_kelimeler:
            return None, None, None, None
        soru = random.choice(yanlis_kelimeler)
        dogru = soru["tr"]
        yanlislar = [k["tr"] for k in kelimeler if k["tr"] != dogru]
        secenekler = random.sample(yanlislar, min(3, len(yanlislar))) + [dogru]
        random.shuffle(secenekler)
        question_text = f"🇺🇸 **{soru['en']}** ne demek?"

    elif test_type == "tekrar":
        soru = select_word_by_probability("tekrar")
        # Rastgele yön seçimi
        if random.choice([True, False]):
            # EN → TR
            dogru = soru["tr"]
            yanlislar = [k["tr"] for k in kelimeler if k["tr"] != dogru]
            secenekler = random.sample(yanlislar, min(3, len(yanlislar))) + [dogru]
            random.shuffle(secenekler)
            question_text = f"🇺🇸 **{soru['en']}** ne demek?"
        else:
            # TR → EN
            dogru = soru["en"]
            yanlislar = [k["en"] for k in kelimeler if k["en"] != dogru]
            secenekler = random.sample(yanlislar, min(3, len(yanlislar))) + [dogru]
            random.shuffle(secenekler)
            question_text = f"🇹🇷 **{soru['tr']}** kelimesinin İngilizcesi nedir?"

    return soru, dogru, secenekler, question_text


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
    score_data["en_tr_answered"] = 0
    score_data["tr_en_answered"] = 0
    score_data["tekrar_answered"] = 0

if today_str not in score_data["daily"]:
    score_data["daily"][today_str] = {
        "puan": 0, "yeni_kelime": 0, "dogru": 0, "yanlis": 0,
        "en_tr_answered": 0, "tr_en_answered": 0, "tekrar_answered": 0
    }

safe_save_data()

# -------------------- Arayüz --------------------

st.set_page_config(page_title="İngilizce Akademi", page_icon="📘", layout="wide")
st.title("📘 Akademi - İngilizce Kelime Uygulaması v2.3")

# Sidebar bilgileri
with st.sidebar:
    st.markdown("### 📊 Genel Bilgiler")
    st.write(f"💰 **Genel Puan:** {score_data['score']}")
    st.write(f"🕐 **Güncel Saat:** {current_time.strftime('%H:%M:%S')}")
    st.write(f"📅 **Tarih:** {today_str}")

    st.markdown("### 📈 Günlük Durum")
    bugun_kelime = score_data["daily"][today_str]["yeni_kelime"]
    st.write(f"📚 **Bugün eklenen:** {bugun_kelime}/10 kelime")
    st.write(f"📖 **Toplam kelime:** {len(kelimeler)}")

    # Test hedefleri
    st.markdown("### 🎯 Test Hedefleri")
    en_tr_current = score_data.get("en_tr_answered", 0)
    tr_en_current = score_data.get("tr_en_answered", 0)
    tekrar_current = score_data.get("tekrar_answered", 0)

    st.write(f"🆕 **EN→TR:** {en_tr_current}/30")
    st.progress(min(en_tr_current / 30, 1.0))

    st.write(f"🇹🇷 **TR→EN:** {tr_en_current}/30")
    st.progress(min(tr_en_current / 30, 1.0))

    st.write(f"🔄 **Genel Tekrar:** {tekrar_current}/30")
    st.progress(min(tekrar_current / 30, 1.0))

    if is_daily_test_goal_complete():
        st.success("🎉 Tüm test hedefleri tamamlandı!")

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
        total_answered = en_tr_current + tr_en_current + tekrar_current
        test_progress = st.progress(min(total_answered / 90, 1.0))
        st.write(f"{total_answered}/90 soru çözüldü")
        if is_daily_test_goal_complete():
            st.success("🎉 Puan kazanmaya başladınız!")

# -------------------- Testler --------------------

elif menu == "📝 Testler":
    st.header("📝 Testler")

    if len(kelimeler) < 4:
        st.warning("⚠️ Test çözebilmek için en az 4 kelime olmalı!")
        st.stop()

    # Test türü seçimi - Sadece ilk kez seçildiğinde çalışır
    if "selected_test_type" not in st.session_state:
        st.session_state.selected_test_type = None

    # Test türü butonları
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        current, target, test_name = get_test_progress_info("en_tr")
        button_text = f"🆕 Yeni Test (EN→TR)\n{current}/{target}"
        if st.button(button_text, use_container_width=True,
                     type="primary" if st.session_state.selected_test_type == "en_tr" else "secondary"):
            st.session_state.selected_test_type = "en_tr"
            st.session_state.current_question = None  # Yeni soru için sıfırla

    with col2:
        current, target, test_name = get_test_progress_info("tr_en")
        button_text = f"🇹🇷 Türkçe Test (TR→EN)\n{current}/{target}"
        if st.button(button_text, use_container_width=True,
                     type="primary" if st.session_state.selected_test_type == "tr_en" else "secondary"):
            st.session_state.selected_test_type = "tr_en"
            st.session_state.current_question = None

    with col3:
        if st.button("❌ Yanlış Kelimeler", use_container_width=True,
                     type="primary" if st.session_state.selected_test_type == "yanlis" else "secondary"):
            st.session_state.selected_test_type = "yanlis"
            st.session_state.current_question = None

    with col4:
        current, target, test_name = get_test_progress_info("tekrar")
        button_text = f"🔄 Genel Tekrar\n{current}/{target}"
        if st.button(button_text, use_container_width=True,
                     type="primary" if st.session_state.selected_test_type == "tekrar" else "secondary"):
            st.session_state.selected_test_type = "tekrar"
            st.session_state.current_question = None

    # Test seçilmişse soruyu göster
    if st.session_state.selected_test_type:

        # Yanlış kelimeler kontrolü
        if st.session_state.selected_test_type == "yanlis":
            yanlis_kelimeler = [k for k in kelimeler if k.get("wrong_count", 0) > 0]
            if not yanlis_kelimeler:
                st.success("🎉 Hiç yanlış kelime yok!")
                st.session_state.selected_test_type = None
                st.stop()

        st.divider()

        # İlerleme bilgisi göster
        if st.session_state.selected_test_type != "yanlis":
            current, target, test_name = get_test_progress_info(st.session_state.selected_test_type)
            if current < target:
                st.info(f"📊 {test_name} ilerlemesi: {current}/{target} - Hedefe {target - current} soru kaldı")
            else:
                st.success(f"🎉 {test_name} günlük hedefi tamamlandı! ({current}/{target})")

        # Puan kazanma durumu
        can_get_points = can_earn_points(st.session_state.selected_test_type)
        if not can_get_points and st.session_state.selected_test_type != "yanlis":
            st.warning("⚠️ Günlük test hedefleri tamamlanmadan sadece eksi puan verilir!")

        # Mevcut soruyu kontrol et, yoksa yeni soru üret
        if "current_question" not in st.session_state or st.session_state.current_question is None:
            result = generate_question(st.session_state.selected_test_type)
            if result[0] is None:  # Yanlış kelime yoksa
                st.success("🎉 Hiç yanlış kelime yok!")
                st.session_state.selected_test_type = None
                st.stop()

            st.session_state.current_question = {
                "soru": result[0],
                "dogru": result[1],
                "secenekler": result[2],
                "question_text": result[3],
                "answered": False,
                "result_message": ""
            }

        question_data = st.session_state.current_question

        # Soruyu göster
        st.write(question_data["question_text"])

        # Kelime yaşı ve kategori bilgisi
        age_days = get_word_age_days(question_data["soru"])
        age_category = get_word_age_category(question_data["soru"])
        if age_days > 0:
            if age_category == "eski":
                age_info = f"📅 {age_days} gün önce eklendi (🎯 Eski kelime - 3 puan)"
            elif age_category == "orta":
                age_info = f"📅 {age_days} gün önce eklendi (🎯 Orta kelime - 2 puan)"
            else:
                age_info = f"📅 {age_days} gün önce eklendi (🎯 Yeni kelime - 1 puan)"
            st.caption(age_info)

        # Hedef tamamlanmadan uyarısı
        if not can_get_points and st.session_state.selected_test_type != "yanlis":
            st.info("ℹ️ Günlük test hedefleri tamamlanmadan sadece eksi puan verilir!")

        # Cevap verilmemişse seçenekleri göster
        if not question_data["answered"]:
            selected_answer = st.radio(
                "Seçenekler:",
                question_data["secenekler"],
                key=f"answer_radio_{st.session_state.selected_test_type}_{hash(str(question_data))}"
            )

            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("Cevapla", key="answer_btn", type="primary"):
                    # Cevabı işle
                    is_correct = selected_answer == question_data["dogru"]

                    # Test sayaçlarını güncelle
                    score_data["answered_today"] += 1
                    test_type = st.session_state.selected_test_type

                    if test_type == "en_tr":
                        score_data["en_tr_answered"] += 1
                        score_data["daily"][today_str]["en_tr_answered"] += 1
                    elif test_type == "tr_en":
                        score_data["tr_en_answered"] += 1
                        score_data["daily"][today_str]["tr_en_answered"] += 1
                    elif test_type == "tekrar":
                        score_data["tekrar_answered"] += 1
                        score_data["daily"][today_str]["tekrar_answered"] += 1

                    # Puan hesaplama
                    word_points = calculate_word_points(question_data["soru"], is_correct)
                    combo_penalty = update_combo_system(is_correct)

                    # Puan verme kuralları
                    if is_correct:
                        if can_get_points:
                            # Hedef tamamlandıysa normal puanlama
                            combo_multiplier = score_data.get("combo_multiplier", 1.0)
                            final_points = int(word_points * combo_multiplier)
                        else:
                            # Hedef tamamlanmadıysa artı puan yok
                            final_points = 0
                    else:
                        # Yanlış cevaplarda her zaman eksi puan
                        final_points = word_points

                    # Combo cezası ekle
                    final_points += combo_penalty

                    # Puanları güncelle
                    if final_points != 0:
                        score_data["score"] += final_points
                        score_data["daily"][today_str]["puan"] += final_points

                    if is_correct:
                        score_data["daily"][today_str]["dogru"] += 1
                        if final_points > 0:
                            question_data["result_message"] = f"✅ Doğru! (+{final_points} puan)"
                        else:
                            question_data["result_message"] = f"✅ Doğru! (Hedef tamamlanınca puan alacaksınız)"
                    else:
                        score_data["daily"][today_str]["yanlis"] += 1
                        question_data["soru"]["wrong_count"] = question_data["soru"].get("wrong_count", 0) + 1
                        question_data["soru"]["last_wrong_date"] = today_str

                        penalty_msg = f"({final_points} puan)" if final_points != 0 else ""
                        combo_msg = ""
                        if combo_penalty < 0:
                            combo_msg = f" | Seri ceza: {combo_penalty}"

                        question_data[
                            "result_message"] = f"❌ Yanlış! Doğru cevap: **{question_data['dogru']}** {penalty_msg}{combo_msg}"

                    question_data["answered"] = True
                    safe_save_data()
                    st.rerun()

        # Cevap verildiyse sonucu göster
        else:
            if "✅" in question_data["result_message"]:
                st.success(question_data["result_message"])
            else:
                st.error(question_data["result_message"])

            # Sonraki soru butonu
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("🔄 Sonraki Soru", key="next_question", type="primary", use_container_width=True):
                    st.session_state.current_question = None  # Yeni soru için sıfırla
                    st.rerun()

            with col2:
                if st.button("🏠 Test Menüsüne Dön", key="back_to_menu", use_container_width=True):
                    st.session_state.selected_test_type = None
                    st.session_state.current_question = None
                    st.rerun()

            # Kelime düzenleme bölümü
            with st.expander("✏️ Kelimeyi Düzenle / Sil"):
                col1, col2 = st.columns(2)
                with col1:
                    yeni_en = st.text_input("İngilizce", question_data["soru"]["en"], key="edit_en")
                    yeni_tr = st.text_input("Türkçe", question_data["soru"]["tr"], key="edit_tr")

                with col2:
                    if st.button("💾 Kaydet", key="save_edit"):
                        if yeni_en.strip() and yeni_tr.strip():
                            question_data["soru"]["en"] = yeni_en.strip()
                            question_data["soru"]["tr"] = yeni_tr.strip()
                            safe_save_data()
                            st.success("✅ Kelime güncellendi!")
                            st.rerun()
                        else:
                            st.error("❌ Boş bırakılamaz!")

                    if st.button("🗑️ Sil", key="delete_word", type="secondary"):
                        kelimeler.remove(question_data["soru"])
                        safe_save_data()
                        st.warning("🗑️ Kelime silindi!")
                        st.session_state.current_question = None
                        st.session_state.selected_test_type = None
                        st.rerun()
    else:
        st.info("👆 Yukarıdaki butonlardan bir test türü seçin")

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

        # ===== YENİ KAPSAMLI YEDEKLEME SİSTEMİ =====
        st.markdown("### 📦 Kapsamlı Yedekleme Sistemi (v2.3)")

        col1, col2 = st.columns(2)

        with col1:
            st.write("**📥 Tam Yedekleme İndirme:**")

            # Tam yedekleme ZIP oluştur ve indir
            if st.button("📦 Tam Yedekleme İndir (ZIP)", use_container_width=True, type="primary"):
                zip_data = create_complete_backup_zip()
                if zip_data:
                    backup_filename = f"akademi_yedek_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                    st.download_button(
                        label="⬇️ ZIP Dosyasını İndir",
                        data=zip_data,
                        file_name=backup_filename,
                        mime="application/zip"
                    )
                    st.success("✅ Tam yedekleme hazır! İndirme butonuna tıklayın.")
                else:
                    st.error("❌ Yedekleme oluşturulamadı!")

            st.info("💡 Bu yedekleme tüm kelimelerinizi, puanlarınızı ve istatistik geçmişinizi içerir.")

        with col2:
            st.write("**📤 Tam Yedekleme Yükleme:**")

            uploaded_zip = st.file_uploader(
                "ZIP Yedekleme Dosyası Seçin:",
                type=['zip'],
                key="upload_full_backup"
            )

            if uploaded_zip is not None:
                preserve_progress = st.checkbox(
                    "✅ Bugünkü ilerlemeyi koru",
                    value=True,
                    help="İşaretlenirse bugün eklediğiniz kelimeler ve çözdüğünüz testler korunur"
                )

                if st.button("📥 Tam Yedeklemeyi Yükle", type="primary"):
                    try:
                        with zipfile.ZipFile(uploaded_zip, 'r') as zip_file:
                            # ZIP içeriğini kontrol et
                            file_list = zip_file.namelist()

                            if 'kelimeler.json' not in file_list or 'puan.json' not in file_list:
                                st.error("❌ Geçersiz yedekleme dosyası! kelimeler.json veya puan.json eksik.")
                            else:
                                # Verileri yükle
                                kelimeler_content = zip_file.read('kelimeler.json').decode('utf-8')
                                puan_content = zip_file.read('puan.json').decode('utf-8')

                                kelimeler_data = json.loads(kelimeler_content)
                                score_data_backup = json.loads(puan_content)

                                # Backup bilgilerini göster (varsa)
                                if 'backup_info.json' in file_list:
                                    backup_info_content = zip_file.read('backup_info.json').decode('utf-8')
                                    backup_info = json.loads(backup_info_content)

                                    st.info(f"""
                                    📋 **Yedekleme Bilgileri:**
                                    - Yedekleme Tarihi: {backup_info.get('backup_date', 'Bilinmiyor')}
                                    - Uygulama Sürümü: {backup_info.get('app_version', 'Bilinmiyor')}  
                                    - Kelime Sayısı: {backup_info.get('total_words', 'Bilinmiyor')}
                                    - Toplam Puan: {backup_info.get('total_score', 'Bilinmiyor')}
                                    """)

                                # Geri yükleme işlemi
                                success, message = restore_from_complete_backup(
                                    kelimeler_data,
                                    score_data_backup,
                                    preserve_progress
                                )

                                if success:
                                    st.success(f"🎉 {message}")
                                    st.info("🔄 Sayfa yenilenecek...")
                                    time.sleep(2)
                                    st.rerun()
                                else:
                                    st.error(f"❌ {message}")

                    except zipfile.BadZipFile:
                        st.error("❌ Geçersiz ZIP dosyası!")
                    except json.JSONDecodeError as e:
                        st.error(f"❌ JSON okuma hatası: {e}")
                    except Exception as e:
                        st.error(f"❌ Beklenmeyen hata: {e}")

        st.divider()

        # ===== ESKI SİSTEM (GERİYE DÖNÜK UYUMLULUK) =====
        st.markdown("### 📁 Ayrı Dosya İşlemleri")

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
            st.write("**📥 Eski Veri İçe Aktarma:**")
            uploaded_kelimeler = st.file_uploader("Kelimeler JSON", type=['json'], key="upload_kelimeler")
            uploaded_puan = st.file_uploader("Puan JSON", type=['json'], key="upload_puan")

            if st.button("📥 İçe Aktar", type="primary"):
                try:
                    success_messages = []

                    if uploaded_kelimeler:
                        kelimeler_data = json.loads(uploaded_kelimeler.read())
                        # Veri doğrulama
                        errors, warnings = validate_backup_data(kelimeler_data, score_data)
                        if errors:
                            st.error(f"❌ Kelimeler verisi hatalı: {'; '.join(errors)}")
                        else:
                            kelimeler.clear()
                            kelimeler.extend(kelimeler_data)
                            success_messages.append("✅ Kelimeler içe aktarıldı!")

                    if uploaded_puan:
                        puan_data = json.loads(uploaded_puan.read())
                        # Veri doğrulama
                        errors, warnings = validate_backup_data(kelimeler, puan_data)
                        if errors:
                            st.error(f"❌ Puan verisi hatalı: {'; '.join(errors)}")
                        else:
                            score_data.clear()
                            score_data.update(puan_data)
                            success_messages.append("✅ Puan verileri içe aktarıldı!")

                    if success_messages and (uploaded_kelimeler or uploaded_puan):
                        safe_save_data()
                        for msg in success_messages:
                            st.success(msg)
                        st.rerun()

                except Exception as e:
                    st.error(f"❌ İçe aktarma hatası: {e}")

        with col2:
            st.write("**📤 Eski Veri Dışa Aktarma:**")

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
                    "combo_multiplier": 1.0, "en_tr_answered": 0,
                    "tr_en_answered": 0, "tekrar_answered": 0
                })
                if safe_save_data():
                    st.success("✅ Tüm veriler sıfırlandı!")
                    st.rerun()

    with tab2:
        st.subheader("🎯 Hedefler ve Kurallar")

        st.write("**📚 Kelime Ekleme:**")
        st.info(
            "• Her gün en az 10 kelime eklenmeli\n• Eksik kelime başına -20 puan cezası\n• Her eklenen kelime +1 puan")

        st.write("**📝 Yeni Test Sistemi (v2.3):**")
        st.info(
            "• EN→TR Testi: 30 soru hedefi (%50 yeni, %30 orta, %20 eski kelime)\n"
            "• TR→EN Testi: 30 soru hedefi (%50 yeni, %30 orta, %20 eski kelime)\n"
            "• Genel Tekrar: 30 soru hedefi (%20 yeni, %30 orta, %50 eski kelime)\n"
            "• Tüm hedefler tamamlandıktan sonra artı puan verilir\n"
            "• Yanlış cevaplarda her zaman -2 puan"
        )

        st.write("**🎯 Puanlama Sistemi:**")
        st.info(
            "• Yeni kelimeler (0-6 gün): +1 puan\n"
            "• Orta kelimeler (7-29 gün): +2 puan\n"
            "• Eski kelimeler (30+ gün): +3 puan\n"
            "• Yanlış cevap: -2 puan"
        )

        st.write("**🔥 Combo Sistemi:**")
        st.info(
            "• 5 doğru arka arkaya: 2x puan\n"
            "• 10 doğru arka arkaya: 3x puan\n"
            "• 5 yanlış arka arkaya: -5 puan cezası\n"
            "• 10 yanlış arka arkaya: -10 puan cezası"
        )

        st.write("**💾 Yeni Yedekleme Sistemi (v2.3):**")
        st.info(
            "• Tam yedekleme ZIP dosyası ile tüm verilerinizi koruyun\n"
            "• Kelimeler, puanlar ve istatistik geçmişi tek dosyada\n"
            "• Akıllı geri yükleme: Günlük ilerlemenizi korur\n"
            "• Otomatik veri doğrulama ve düzeltme\n"
            "• Geriye dönük uyumluluk: Eski JSON dosyaları da desteklenir"
        )

    with tab3:
        st.subheader("ℹ️ Uygulama Bilgileri")

        st.write("**🔧 Versiyon:** 2.3 - Gelişmiş Yedekleme Sistemi")
        st.write("**📅 Son Güncelleme:** Bugün")

        st.markdown("### ✨ v2.3 Yenilikleri:")
        st.success("""
        🆕 **Kapsamlı Yedekleme Sistemi:**
        • ZIP formatında tam yedekleme
        • Tüm veriler tek dosyada (kelimeler + istatistikler)  
        • Akıllı geri yükleme ile günlük ilerleme korunur
        • Otomatik veri doğrulama ve onarım
        • Yedekleme tarihi ve bilgiler dahil

        🔧 **İyileştirmeler:**
        • Günlük kelime hedefleri yedeklemeden etkilenmez
        • Test ilerlemeleri korunur
        • Eksik veriler otomatik tamamlanır
        • Hata durumunda detaylı bilgi
        """)

        st.write("**🎯 Geliştiriciye Not:**")
        st.info("Artık tek ZIP dosyası ile tüm verilerinizi güvenle yedekleyebilir ve geri yükleyebilirsiniz!")

# Import time for sleep function
import time
import time