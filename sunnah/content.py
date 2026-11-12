"""Everything the bot says that isn't about settings: Sunnah content, occasions
of the Hijri calendar, and the reminder texts. Well-known acts from the Sunnah;
the references are general pointers. Every text exists in English and Arabic."""
import json
import pathlib

DATA = pathlib.Path(__file__).parent / "data"
AZKAR = json.loads((DATA / "azkar.json").read_text(encoding="utf-8"))
HADITHS = json.loads((DATA / "hadith_nawawi.json").read_text(encoding="utf-8"))
LIMIT = 4000   # Telegram rejects messages over 4096 characters

PRAYER_AR = {"Fajr": "الفجر", "Sunrise": "الشروق", "Dhuhr": "الظهر",
             "Asr": "العصر", "Maghrib": "المغرب", "Isha": "العشاء"}


def tr(lang, en, ar):
    return ar if lang == "ar" else en


def md(text):
    """Escape text for Telegram's legacy Markdown."""
    return "".join("\\" + c if c in "_*`[" else c for c in str(text))


def num(n, lang):
    """n with Arabic-Indic digits in Arabic."""
    return str(n).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")) if lang == "ar" else str(n)


def clock(hhmm, lang):
    """'21:37' -> '9:37 PM' (or '9:37 م')."""
    h, m = int(hhmm[:2]), int(hhmm[3:5])
    return f"{h % 12 or 12}:{m:02d} " + tr(lang, "PM" if h >= 12 else "AM", "م" if h >= 12 else "ص")


# ----------------------------------------------------------------------------
# Short content
# ----------------------------------------------------------------------------
# (en_label, arabic, en_meaning, ar_label)
DUAS = [
    ("Morning", "أَصْبَحْنَا وَأَصْبَحَ الْمُلْكُ لِلَّهِ",
     "We have entered the morning and the dominion belongs to Allah.", "أذكار الصباح"),
    ("Before eating", "بِسْمِ اللَّهِ", "In the name of Allah.", "قبل الطعام"),
    ("After eating", "الْحَمْدُ لِلَّهِ الَّذِي أَطْعَمَنِي هَذَا",
     "Praise be to Allah who fed me this.", "بعد الطعام"),
    ("Leaving home", "بِسْمِ اللَّهِ تَوَكَّلْتُ عَلَى اللَّهِ",
     "In the name of Allah, I place my trust in Allah.", "الخروج من البيت"),
    ("Distress", "لَا إِلَٰهَ إِلَّا اللَّهُ الْعَظِيمُ الْحَلِيمُ",
     "There is no god but Allah, the Magnificent, the Forbearing.", "عند الكرب"),
    ("Seeking forgiveness", "أَسْتَغْفِرُ اللَّهَ وَأَتُوبُ إِلَيْهِ",
     "I seek Allah's forgiveness and turn to Him in repentance.", "الاستغفار"),
    ("Salawat", "اللَّهُمَّ صَلِّ وَسَلِّمْ عَلَى نَبِيِّنَا مُحَمَّدٍ",
     "O Allah, send blessings and peace upon our Prophet Muhammad.", "الصلاة على النبي ﷺ"),
    ("Before sleep", "بِاسْمِكَ اللَّهُمَّ أَمُوتُ وَأَحْيَا",
     "In Your name O Allah, I die and I live.", "قبل النوم"),
]

# (english, arabic)
TIPS = [
    ("Use the miswak / brush your teeth — the Prophet ﷺ loved it before every prayer. (Bukhari)",
     "استعمل السواك — كان النبي ﷺ يحبه عند كل صلاة. (البخاري)"),
    ("Smile at someone today — your smile in your brother's face is charity. (Tirmidhi)",
     "ابتسم لأحدهم اليوم — تبسّمك في وجه أخيك صدقة. (الترمذي)"),
    ("Eat with your right hand and from what is nearest to you. (Bukhari & Muslim)",
     "كُل بيمينك ومما يليك. (البخاري ومسلم)"),
    ("Say Bismillah before you begin, and Alhamdulillah after you finish.",
     "قل بسم الله قبل أن تبدأ، والحمد لله بعد أن تنتهي."),
    ("Pray the 12 Sunnah rak'ah and a house is built for you in Paradise. (Muslim)",
     "صلِّ ١٢ ركعة من السنن يُبنَ لك بها بيت في الجنة. (مسلم)"),
    ("Send salawat on the Prophet ﷺ — for each one, Allah sends ten blessings on you. (Muslim)",
     "أكثر من الصلاة على النبي ﷺ — بكل واحدة يصلي الله عليك عشرًا. (مسلم)"),
    ("Spread salam to those you know and those you don't. (Bukhari)",
     "أفشِ السلام على من عرفت ومن لم تعرف. (البخاري)"),
    ("Control yourself when angry — that is true strength. (Bukhari)",
     "املك نفسك عند الغضب — فتلك هي القوة الحقيقية. (البخاري)"),
    ("Sleep on your right side after making wudu, as the Prophet ﷺ did. (Bukhari)",
     "نَم على شقك الأيمن بعد الوضوء، كما كان النبي ﷺ يفعل. (البخاري)"),
    ("Give in charity today, even half a date. (Bukhari)",
     "تصدّق اليوم ولو بشقّ تمرة. (البخاري)"),
    ("The most beloved deeds to Allah are the consistent ones, even if small. (Bukhari)",
     "أحب الأعمال إلى الله أدومها وإن قلّ. (البخاري)"),
    ("Read some Qur'an today — the best of you learn it and teach it. (Bukhari)",
     "اقرأ وردًا من القرآن اليوم — خيركم من تعلّمه وعلّمه. (البخاري)"),
    ("Honour your parents — Allah's pleasure is in the parent's pleasure. (Tirmidhi)",
     "برّ والديك — رضا الرب في رضا الوالد. (الترمذي)"),
    ("Seek forgiveness often — the Prophet ﷺ did so 70+ times a day. (Bukhari)",
     "أكثر من الاستغفار — كان النبي ﷺ يستغفر أكثر من ٧٠ مرة في اليوم. (البخاري)"),
    ("Pray two rak'ah of Duha (forenoon) — charity for every joint in your body. (Muslim)",
     "صلِّ ركعتي الضحى — صدقة عن كل مفصل في جسدك. (مسلم)"),
]


def tip(i, lang):
    return tr(lang, *TIPS[i % len(TIPS)])


def dua(i, lang):
    label, ar, en, label_ar = DUAS[i % len(DUAS)]
    return tr(lang, f"🤲 *{label}*\n\n{ar}\n_{en}_", f"🤲 *{label_ar}*\n\n{ar}")


def checklist(lang):
    return tr(
        lang,
        "🕌 *Salah & Adhkar*\n"
        "▫️ Pray the 5 prayers on time\n"
        "▫️ 12 Sunnah rak'ah (rawatib)\n"
        "▫️ Morning & evening adhkar\n"
        "▫️ Ayat al-Kursi after each salah\n"
        "▫️ Tasbih 33×3 after salah\n"
        "▫️ Witr before sleeping\n\n"
        "🌿 *Rawatib — Sunnah prayers*\n"
        "▫️ 2 rak'ah before Fajr\n"
        "▫️ 4 rak'ah before Dhuhr\n"
        "▫️ 2 rak'ah after Dhuhr\n"
        "▫️ 2 rak'ah after Maghrib\n"
        "▫️ 2 rak'ah after Isha\n"
        "_12 rak'ah → a house in Paradise (Bukhari & Muslim)_\n\n"
        "🌱 *Daily Sunan*\n"
        "▫️ Miswak / brush\n"
        "▫️ Bismillah + right hand when eating\n"
        "▫️ Send salawat on the Prophet ﷺ\n"
        "▫️ Istighfar 100×\n"
        "▫️ Read some Qur'an\n"
        "▫️ Duha & sleep on right side after wudu\n\n"
        "📅 *Weekly*\n"
        "▫️ Surah Al-Kahf + ghusl on Friday\n"
        "▫️ Fast Monday & Thursday\n"
        "▫️ The 3 white days (13–15)\n"
        "▫️ Keep ties with family\n\n"
        "💛 *Akhlaq*\n"
        "▫️ Smile & spread salam\n"
        "▫️ Be truthful, restrain anger\n"
        "▫️ Honour parents\n"
        "▫️ Speak good or stay silent",
        "🕌 *الصلاة والأذكار*\n"
        "▫️ صلِّ الفروض الخمسة في وقتها\n"
        "▫️ ١٢ ركعة من السنن الرواتب\n"
        "▫️ أذكار الصباح والمساء\n"
        "▫️ آية الكرسي بعد كل صلاة\n"
        "▫️ التسبيح ٣٣×٣ بعد الصلاة\n"
        "▫️ الوتر قبل النوم\n\n"
        "🌿 *السنن الرواتب*\n"
        "▫️ ركعتان قبل الفجر\n"
        "▫️ أربع ركعات قبل الظهر\n"
        "▫️ ركعتان بعد الظهر\n"
        "▫️ ركعتان بعد المغرب\n"
        "▫️ ركعتان بعد العشاء\n"
        "_١٢ ركعة يُبنى بها بيت في الجنة (البخاري ومسلم)_\n\n"
        "🌱 *سنن يومية*\n"
        "▫️ السواك\n"
        "▫️ التسمية والأكل باليمين\n"
        "▫️ الصلاة على النبي ﷺ\n"
        "▫️ الاستغفار ١٠٠ مرة\n"
        "▫️ قراءة وردٍ من القرآن\n"
        "▫️ الضحى والنوم على الشق الأيمن بعد الوضوء\n\n"
        "📅 *أسبوعية*\n"
        "▫️ سورة الكهف والغُسل يوم الجمعة\n"
        "▫️ صيام الإثنين والخميس\n"
        "▫️ الأيام البيض (١٣–١٥)\n"
        "▫️ صلة الرحم\n\n"
        "💛 *الأخلاق*\n"
        "▫️ الابتسامة وإفشاء السلام\n"
        "▫️ الصدق وكظم الغيظ\n"
        "▫️ برّ الوالدين\n"
        "▫️ قول الخير أو الصمت")


def friday(lang):
    return tr(
        lang,
        "🕌 *Jumu'ah Sunnah acts*\n\n"
        "📖 Read *Surah Al-Kahf* — light between the two Fridays. (al-Hakim)\n"
        "🚿 *Ghusl* and wear your best clothes; use perfume.\n"
        "⏱️ Go *early* to the masjid.\n"
        "🤲 Abundant *salawat* on the Prophet ﷺ. (Abu Dawud)\n"
        "⏳ The *last hour before Maghrib* — a time du'a is answered. (Bukhari)",
        "🕌 *سنن يوم الجمعة*\n\n"
        "📖 اقرأ *سورة الكهف* — نور ما بين الجمعتين. (الحاكم)\n"
        "🚿 *الغُسل* وأفضل الثياب والطيب.\n"
        "⏱️ *التبكير* إلى المسجد.\n"
        "🤲 الإكثار من *الصلاة على النبي ﷺ*. (أبو داود)\n"
        "⏳ *الساعة الأخيرة قبل المغرب* — ساعة يُستجاب فيها الدعاء. (البخاري)")


# ----------------------------------------------------------------------------
# Reminder texts
# ----------------------------------------------------------------------------
def morning_reminder(lang):
    _, ar, en, _ = DUAS[0]
    return tr(lang,
              f"🌅 *Morning adhkar time*\n\n{ar}\n_{en}_\n\nStart your day with Allah's remembrance. "
              f"Send /azkar for all {len(AZKAR['morning'])} morning adhkar.",
              f"🌅 *وقت أذكار الصباح*\n\n{ar}\n\nابدأ يومك بذكر الله. "
              f"أرسل /azkar لأذكار الصباح كاملة ({num(len(AZKAR['morning']), 'ar')}).")


def evening_reminder(lang):
    return tr(lang,
              "🌇 *Evening adhkar time*\n\nأَمْسَيْنَا وَأَمْسَى الْمُلْكُ لِلَّهِ\n"
              "_We have entered the evening and the dominion belongs to Allah._\n\n"
              "Send /azkar for the evening adhkar, and review your Sunnah list (/today).",
              "🌇 *وقت أذكار المساء*\n\nأَمْسَيْنَا وَأَمْسَى الْمُلْكُ لِلَّهِ\n\n"
              "أرسل /azkar لأذكار المساء، وراجع قائمة سننك (/today).")


def salah_reminder(name, hhmm, lang):
    return tr(lang,
              f"🕌 *It's time for {name}* ({clock(hhmm, lang)})\n\n"
              "Hayya 'ala-s-salah. Leave what you're doing and pray. 🤍",
              f"🕌 *حان وقت صلاة {PRAYER_AR[name]}* ({clock(hhmm, lang)})\n\n"
              "حيّ على الصلاة. اترك ما بيدك وصلِّ. 🤍")


def jumuah_reminder(lang):
    return tr(lang,
              "🕌 *Jumu'ah Mubarak!* Today's Sunnah acts:\n\n"
              "📖 Read *Surah Al-Kahf* — light between the two Fridays. (al-Hakim)\n"
              "🚿 *Ghusl* and wear your best clothes.\n"
              "🤲 Abundant *salawat* on the Prophet ﷺ — they are presented to him today. (Abu Dawud)\n"
              "⏳ Watch for the *last hour before Maghrib* — a time when dua is answered. (Bukhari)",
              "🕌 *جمعة مباركة!* من سنن اليوم:\n\n"
              "📖 اقرأ *سورة الكهف* — نور ما بين الجمعتين. (الحاكم)\n"
              "🚿 *الغُسل* وأفضل الثياب.\n"
              "🤲 الإكثار من *الصلاة على النبي ﷺ* — فهي معروضة عليه اليوم. (أبو داود)\n"
              "⏳ تحرَّ *الساعة الأخيرة قبل المغرب* — ساعة يُستجاب فيها الدعاء. (البخاري)")


def friday_hour(lang):
    return tr(lang,
              "⏳ *The last hour before Maghrib (Friday)*\n\nThis is a time when no Muslim asks Allah "
              "for good except that He grants it. (Bukhari)\n\nRaise your hands and make du'a. 🤲",
              "⏳ *الساعة الأخيرة قبل المغرب (الجمعة)*\n\nساعة لا يسأل الله فيها مسلمٌ خيرًا إلا أعطاه إياه. "
              "(البخاري)\n\nارفع يديك وادعُ. 🤲")


# ----------------------------------------------------------------------------
# Occasions of the Hijri calendar
# ----------------------------------------------------------------------------
MUHARRAM, RAMADAN, SHAWWAL, DHUL_HIJJAH = 1, 9, 10, 12
FASTING = {"white", "ashura", "arafah", "shawwal6", "monday", "thursday"}

# key -> (english, arabic); {d} is the Hijri day
OCCASIONS = {
    "white": ("🤍 a *White Day* (the {d}th) — “fasting three days each month is like fasting the whole month.” (Bukhari)",
              "🤍 *يوم من الأيام البيض* ({d}) — «صيام ثلاثة أيام من كل شهر كصيام الدهر». (البخاري)"),
    "ashura": ("🌙 *Ashura* (Muharram {d}) — fasting the 10th (with the 9th) expiates the past year's sins. (Muslim)",
               "🌙 *عاشوراء* (محرم {d}) — صيام العاشر (مع التاسع) يكفّر السنة الماضية. (مسلم)"),
    "dhul_hijjah_10": ("🌟 one of the *first ten days of Dhul Hijjah* — no days in which good deeds are more beloved to Allah. (Bukhari)",
                       "🌟 من *العشر الأوائل من ذي الحجة* — ما من أيام العمل الصالح فيها أحب إلى الله من هذه الأيام. (البخاري)"),
    "arafah": ("⛰️ the *Day of Arafah* — fasting it expiates the sins of two years. (Muslim) (For those not on Hajj.)",
               "⛰️ *يوم عرفة* — صيامه يكفّر سنتين. (مسلم) (لغير الحاج.)"),
    "eid_adha": ("🐑 *Eid al-Adha Mubarak!* — say the takbir; fasting on the day of Eid is not allowed. (Bukhari & Muslim)",
                 "🐑 *عيد الأضحى مبارك!* — أكثر من التكبير، ولا يجوز صيام يوم العيد. (البخاري ومسلم)"),
    "tashreeq": ("🍽️ one of the *Days of Tashreeq* — days of eating, drinking and remembering Allah, not days for fasting. (Muslim)",
                 "🍽️ من *أيام التشريق* — أيام أكل وشرب وذكر لله، فلا تُصام. (مسلم)"),
    "ramadan": ("🌙 *Ramadan*, day {d} — “whoever fasts Ramadan out of faith and hoping for reward is forgiven his past sins.” (Bukhari & Muslim)",
                "🌙 *رمضان*، اليوم {d} — «من صام رمضان إيمانًا واحتسابًا غُفر له ما تقدّم من ذنبه». (البخاري ومسلم)"),
    "eid_fitr": ("🎉 *Eid al-Fitr Mubarak!* — fasting on the day of Eid is not allowed. (Bukhari & Muslim)",
                 "🎉 *عيد الفطر مبارك!* — ولا يجوز صيام يوم العيد. (البخاري ومسلم)"),
    "shawwal6": ("✨ one of the *Six of Shawwal* — “whoever fasts Ramadan then six of Shawwal, it is as if he fasted the whole year.” (Muslim)",
                 "✨ من *ست شوال* — «من صام رمضان ثم أتبعه ستًا من شوال كان كصيام الدهر». (مسلم)"),
}

FAST_EVE = {
    "monday": ("🌙 *Monday* — a day the Prophet ﷺ fasted. (Tirmidhi)",
               "🌙 *الإثنين* — يوم كان النبي ﷺ يصومه. (الترمذي)"),
    "thursday": ("🌙 *Thursday* — a day the Prophet ﷺ fasted. (Tirmidhi)",
                 "🌙 *الخميس* — يوم كان النبي ﷺ يصومه. (الترمذي)"),
    "white": OCCASIONS["white"], "ashura": OCCASIONS["ashura"], "arafah": OCCASIONS["arafah"],
    "ramadan_start": ("🌙 *Ramadan is expected to begin tomorrow* (confirm with your local mosque). Make the intention "
                      "tonight and don't miss suhoor — there is blessing in it. (Bukhari & Muslim)",
                      "🌙 *يُتوقّع أن يبدأ رمضان غدًا* (تأكّد من مسجدك). انوِ الصيام الليلة ولا تترك السحور — "
                      "فإن في السحور بركة. (البخاري ومسلم)"),
    "eid_fitr_eve": ("🎉 *Eid al-Fitr is expected tomorrow* (confirm with your local mosque). Pay *Zakat al-Fitr* "
                     "before the Eid prayer, and say the takbir. (Bukhari & Muslim)",
                     "🎉 *يُتوقّع أن يكون العيد غدًا* (تأكّد من مسجدك). أخرج *زكاة الفطر* قبل صلاة العيد، "
                     "وأكثر من التكبير. (البخاري ومسلم)"),
}


def occasion_keys(day, month):
    """What's special about Hijri `day` of `month`, as OCCASIONS keys."""
    if month == RAMADAN:
        return ["ramadan"]
    if month == SHAWWAL and day == 1:
        return ["eid_fitr"]
    if month == DHUL_HIJJAH and day == 10:
        return ["eid_adha"]
    if month == DHUL_HIJJAH and 11 <= day <= 13:
        return ["tashreeq"]
    keys = []
    if month == DHUL_HIJJAH and day <= 9:
        keys.append("dhul_hijjah_10")
    if month == DHUL_HIJJAH and day == 9:
        keys.append("arafah")
    if month == MUHARRAM and day in (9, 10):
        keys.append("ashura")
    if month == SHAWWAL and 2 <= day <= 7:
        keys.append("shawwal6")
    if 13 <= day <= 15:
        keys.append("white")
    return keys


def fast_eve_keys(weekday, day, month):
    """FAST_EVE keys for tomorrow, given tomorrow's weekday (Mon=0) and Hijri date."""
    if month == RAMADAN:
        return ["ramadan_start"] if day == 1 else []
    if month == SHAWWAL and day == 1:
        return ["eid_fitr_eve"]
    occ = occasion_keys(day, month) if day else []
    if {"eid_adha", "tashreeq"} & set(occ):
        return []
    keys = {0: ["monday"], 3: ["thursday"]}.get(weekday, [])
    return keys + [k for k in occ if k in ("white", "ashura", "arafah")]


def qadr_night(day, month):
    """The odd night of Ramadan's last ten that begins this evening, or None."""
    return day + 1 if month == RAMADAN and day in (20, 22, 24, 26, 28) else None


def _texts(table, keys, d, lang):
    return [tr(lang, *table[k]).format(d=num(d, lang)) for k in keys]


def hijri_label(hijri, lang):
    return tr(lang, f"{hijri['day']} {hijri['month_en']} {hijri['year']} AH",
              f"{num(hijri['day'], 'ar')} {hijri['month_ar']} {num(hijri['year'], 'ar')}هـ")


def occasion_message(keys, hijri, lang):
    if not keys:
        return None
    msg = tr(lang, "🗓️ *Today* — ", "🗓️ *اليوم* — ") + hijri_label(hijri, lang) + "\n\n"
    msg += "\n".join(_texts(OCCASIONS, keys, hijri["day"], lang))
    if FASTING & set(keys):
        msg += tr(lang, "\n\nA blessed day to fast if you're able. 🤍", "\n\nيوم مبارك للصيام إن استطعت. 🤍")
    return msg


def fast_eve_message(keys, hijri, lang):
    """Evening nudge about tomorrow; `hijri` is tomorrow's date."""
    if not keys:
        return None
    fasts = _texts(FAST_EVE, [k for k in keys if k in FASTING], (hijri or {}).get("day"), lang)
    notes = _texts(FAST_EVE, [k for k in keys if k not in FASTING], None, lang)
    parts = notes
    if fasts:
        parts = [tr(lang, "🍽️ *Plan to fast tomorrow?*\n\nTomorrow is ", "🍽️ *تنوي صيام الغد؟*\n\nالغد ")
                 + tr(lang, "; ", "؛ ").join(fasts)
                 + tr(lang, "\n\nMake the intention and remember suhoor. 🤍",
                      "\n\nاعقد النية ولا تنسَ السحور. 🤍")] + notes
    return "\n\n".join(parts)


def qadr_message(night, lang):
    return tr(lang,
              f"✨ *Tonight is the {night}{ {1: 'st', 3: 'rd'}.get(night % 10, 'th') } night of Ramadan* — "
              "seek Laylat al-Qadr in the odd nights of the "
              "last ten. (Bukhari)\n\nPray, read Qur'an, and say: _Allahumma innaka 'afuwwun tuhibbul-'afwa "
              "fa'fu 'anni_ — O Allah, You are Pardoning and love to pardon, so pardon me. (Tirmidhi)",
              f"✨ *الليلة هي ليلة {num(night, 'ar')} من رمضان* — تحرّوا ليلة القدر في الوتر من العشر الأواخر. "
              "(البخاري)\n\nأكثر من القيام وقراءة القرآن، وقل: «اللهم إنك عفوٌّ تحب العفو فاعفُ عني». (الترمذي)")


# ----------------------------------------------------------------------------
# Long content: Nawawi's Forty and the morning/evening adhkar
# ----------------------------------------------------------------------------
def hadith_of_day(date):
    return date.toordinal() % len(HADITHS) + 1


def hadith_message(n, lang):
    h = HADITHS[n - 1]
    return tr(lang, f"📖 *Hadith {n} of an-Nawawi's Forty*\n\n{md(h['en'])}",
              f"📖 *الحديث {num(n, 'ar')} من الأربعين النووية*\n\n{md(h['ar'])}")


def azkar_messages(kind, lang):
    """The full morning or evening adhkar, split into messages under LIMIT."""
    items = AZKAR[kind]
    head = tr(lang, {"morning": "🌅 *Morning adhkar*", "evening": "🌇 *Evening adhkar*"}[kind],
              {"morning": "🌅 *أذكار الصباح*", "evening": "🌇 *أذكار المساء*"}[kind])
    blocks = []
    for i, z in enumerate(items, 1):
        times = f" ×{num(z['count'], lang)}" if z["count"] > 1 else ""
        tl = z["tl"].replace("`", "ʿ").translate(str.maketrans("", "", "_*["))   # no escapes inside _italics_
        blocks.append(tr(lang, f"*{i}.*{times}\n{md(z['ar'])}\n_{tl}_\n{md(z['en'])}",
                         f"*{num(i, 'ar')}.*{times}\n{md(z['ar'])}"))
    blocks.append(tr(lang, "_Source: Ḥiṣn al-Muslim_", "_المصدر: حصن المسلم_"))
    msgs, cur = [], head
    for b in blocks:
        if len(cur) + 2 + len(b) > LIMIT:
            msgs.append(cur)
            cur = b
        else:
            cur += "\n\n" + b
    return msgs + [cur]
