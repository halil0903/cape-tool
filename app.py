# app.py
import os
from datetime import datetime

import streamlit as st
from core.engine import DaptRuleEngine
from core.oac_engine import OacRuleEngine


# ----------------------------
# TABLE 5 (ESC) -> Surgery list & risk mapping
# ----------------------------
SURGERY_TABLE5 = {
    "Düşük": [
        "Meme cerrahisi (Breast)",
        "Dental girişimler (Dental)",
        "Endokrin: Tiroid (Endocrine: thyroid)",
        "Göz cerrahisi (Eye)",
        "Jinekolojik: Minör (Gynaecological: minor)",
        "Ortopedik minör: Menisektomi (Orthopaedic minor - meniscectomy)",
        "Rekonstrüktif cerrahi (Reconstructive)",
        "Yüzeyel cerrahi (Superficial surgery)",
        "Ürolojik minör: TUR-P (Transurethral resection of prostate)",
        "VATS minör akciğer rezeksiyonu (VATS minor lung resection)",
    ],
    "Orta": [
        "Karotis asemptomatik: CEA veya CAS (Carotid asymptomatic - CEA/CAS)",
        "Karotis semptomatik: CEA (Carotid symptomatic - CEA)",
        "Endovasküler AAA onarımı: EVAR (Endovascular aortic aneurysm repair)",
        "Baş-boyun cerrahisi (Head or neck surgery)",
        "İntraperitoneal: Splenektomi / Hiatal herni / Kolesistektomi (Intraperitoneal)",
        "İntratorasik: Majör olmayan (Intrathoracic - non-major)",
        "Nörolojik veya ortopedik majör: Kalça / Omurga (Major hip and spine surgery)",
        "Periferik arter anjiyoplasti (Peripheral arterial angioplasty)",
        "Renal transplant (Renal transplants)",
        "Ürolojik veya jinekolojik majör (Urological or gynaecological - major)",
    ],
    "Yüksek": [
        "Adrenal rezeksiyon (Adrenal resection)",
        "Aort ve majör vasküler cerrahi (Aortic and major vascular surgery)",
        "Karotis semptomatik: CAS (Carotid symptomatic - CAS)",
        "Duodeno-pankreatik cerrahi (Duodenal-pancreatic surgery)",
        "Karaciğer rezeksiyonu / Safra yolu cerrahisi (Liver resection / bile duct surgery)",
        "Özofajektomi (Oesophagectomy)",
        "Açık alt ekstremite revaskülarizasyonu (akut iskemi) veya amputasyon",
        "Pnömonektomi (VATS veya açık) (Pneumonectomy)",
        "Pulmoner veya karaciğer transplantı (Pulmonary or liver transplant)",
        "Perfore barsak onarımı (Repair of perforated bowel)",
        "Total sistektomi (Total cystectomy)",
    ],
}

SURGERY_TO_RISK = {}
SURGERY_OPTIONS = []
for risk, items in SURGERY_TABLE5.items():
    for it in items:
        SURGERY_OPTIONS.append(it)
        SURGERY_TO_RISK[it] = risk


# ----------------------------
# Drugs list (optional SGK CSV)
# ----------------------------
DEFAULT_DRUGS = sorted(
    list(
        {
            "Aspirin",
            "Klopidogrel",
            "Prasugrel",
            "Tikagrelor",
            "Warfarin",
            "Apiksaban",
            "Rivaroksaban",
            "Edoksaban",
            "Dabigatran",
            "Enoksaparin",
            "Dalteparin",
            "Fondaparinuks",
            "Metoprolol",
            "Bisoprolol",
            "Nebivolol",
            "Carvedilol",
            "Propranolol",
            "Diltiazem",
            "Verapamil",
            "Amiodaron",
            "Digoksin",
            "Amlodipin",
            "Ramipril",
            "Perindopril",
            "Enalapril",
            "Valsartan",
            "Losartan",
            "Sacubitril/Valsartan",
            "Furosemid",
            "Torasemid",
            "Spironolakton",
            "Eplerenon",
            "Empagliflozin",
            "Dapagliflozin",
            "Atorvastatin",
            "Rosuvastatin",
            "Pantoprazol",
            "Omeprazol",
        }
    )
)


def load_drug_list():
    csv_path = os.path.join("data", "sgk_ilaclar.csv")
    if os.path.exists(csv_path):
        try:
            import pandas as pd

            df = pd.read_csv(csv_path)
            if "drug_name" in df.columns:
                drugs = df["drug_name"].dropna().astype(str).unique().tolist()
            else:
                drugs = df.iloc[:, 0].dropna().astype(str).unique().tolist()
            drugs = sorted(set([d.strip() for d in drugs if d.strip()]))
            if drugs:
                return drugs, f"İlaç listesi: data/sgk_ilaclar.csv ({len(drugs)} kayıt)"
        except Exception as e:
            return DEFAULT_DRUGS, f"İlaç listesi: varsayılan (CSV okunamadı: {e})"
    return DEFAULT_DRUGS, "İlaç listesi: varsayılan (CSV yok)"


DRUGS, DRUGS_CAPTION = load_drug_list()


# ----------------------------
# Clinical helpers
# ----------------------------
BETA_BLOCKERS = {"metoprolol", "bisoprolol", "nebivolol", "carvedilol", "propranolol"}
NON_DHP_CCB = {"diltiazem", "verapamil"}

DOAC_INTERACT_EDOXABAN = {
    "siklosporin",
    "cyclosporine",
    "dronedarone",
    "eritromisin",
    "erythromycin",
    "ketokonazol",
    "ketoconazole",
}


def meds_contains_any(meds, needles_lower_set):
    meds_l = [m.lower() for m in (meds or [])]
    for n in needles_lower_set:
        if any(n in m for m in meds_l):
            return True
    return False


def get_mech_valve_warfarin_note() -> str:
    return "\n".join(
        [
            "MEKANİK KAPAK – WARFARİN YÖNETİMİ ve ENFEKTİF ENDOKARDİT PROFİLAKSİSİ (Otomatik Not)",
            "- Warfarin operasyon tarihinden **5 gün önce kesilmelidir**.",
            "- Operasyon sabahı hedef **INR < 1.5** olacak şekilde planlama yapılmalıdır.",
            "- INR operasyon öncesi gün kontrol edilmelidir.",
            "",
            "Enfektif Endokardit Profilaksisi:",
            "- Standart: **Amoksisilin 2 g PO** (işlemden 30–60 dk önce).",
            "- Penisilin alerjisi varsa: **Klindamisin 600 mg PO** veya **Azitromisin 500 mg PO**.",
            "",
            "Postop Warfarin:",
            "- Hemostaz sağlandıktan sonra genellikle **operasyondan 12–24 saat sonra** başlanabilir.",
            "- Büyük kanama riski varsa **48–72 saate** ertelenebilir.",
            "- Başlangıç dozu: hastanın **önceki stabil dozuna göre** başlanır.",
            "",
            "INR Hedefleri:",
            "- Mekanik mitral kapak: **2.5–3.5**",
            "- Mekanik aort kapak: **2.0–3.0**",
            "- Atriyal fibrilasyon: **2.0–3.0**",
            "",
            "Bridging:",
            "- **INR >2 olana kadar LMWH ile bridging uygulanır; INR >2 olduktan sonra LMWH kesilmesi uygundur.**",
        ]
    )


def get_device_management_note(has_device: str, device_type: str, pace_dependent: str) -> str:
    if has_device != "Evet":
        return ""

    dt = (device_type or "").strip()
    pd = (pace_dependent or "").strip()

    if dt not in {"Permanent pacemaker", "ICD", "CRT"}:
        return "- Cihaz: Belirtilmedi.\n"

    if pd not in {"Evet", "Hayır"}:
        return f"- Cihaz: {dt}. Pace bağımlılığı belirtilmedi.\n"

    if dt == "Permanent pacemaker":
        if pd == "Evet":
            return "- Cihaz: Permanent pacemaker. **Pace bağımlı** → **VOO 80 bpm** moduna alınmalı (perioperatif plan).\n"
        return "- Cihaz: Permanent pacemaker. Pace bağımlı değil → **VVI 40 bpm** alınmalı (perioperatif plan).\n"

    if pd == "Evet":
        return f"- Cihaz: {dt}. **Pace bağımlı** → **Taşi-terapiler kapatılmalı** + **VOO 80 bpm** moduna alınmalı.\n"
    return f"- Cihaz: {dt}. Pace bağımlı değil → **Taşi-terapiler kapatılmalı** + **VVI 40 bpm** alınmalı.\n"


def get_bradycardia_meds_note(hr: int, has_hf: str, current_meds: list[str]) -> str:
    if hr >= 60:
        return ""

    on_bb = meds_contains_any(current_meds, BETA_BLOCKERS)
    on_non_dhp = meds_contains_any(current_meds, NON_DHP_CCB)

    if not (on_bb or on_non_dhp):
        return ""

    if has_hf != "Evet":
        return (
            "- Bradikardi (HR<60/dk) ve hız düşürücü ilaç kullanımı mevcut: "
            "perioperatif dönemde hemodinami uygunsa beta-bloker ve/veya non-DHP KKB doz azaltımı "
            "veya geçici kesilmesi (hold) uygundur.\n"
        )

    if on_bb:
        return (
            "- Bradikardi (HR<60/dk) mevcut: kalp yetersizliği varlığında perioperatif dönemde "
            "beta-bloker doz azaltımı veya geçici kesilmesi (hold) hemodinamiye göre uygundur.\n"
        )

    return (
        "- Bradikardi (HR<60/dk) mevcut: hemodinamiye göre hız düşürücü ajanların doz azaltımı "
        "veya geçici kesilmesi (hold) düşünülebilir.\n"
    )


def get_doac_dose_warnings(
    agent: str,
    age: int,
    egfr: float,
    current_meds: list[str],
    bleed_risk: str,
    very_high_bleed: bool,
) -> list[str]:
    warnings: list[str] = []
    a = (agent or "").strip().lower()
    meds_l = [m.lower() for m in (current_meds or [])]
    has_verapamil = any("verapamil" in m for m in meds_l)
    has_edox_interaction = any(any(x in m for m in meds_l) for x in DOAC_INTERACT_EDOXABAN)
    high_bleed = (bleed_risk == "Yüksek") or bool(very_high_bleed)

    if egfr is None:
        egfr = 0.0

    if a in {"apiksaban", "apixaban"}:
        if egfr < 15:
            warnings.append("⚠️ Apiksaban: eGFR <15 → **kesme/kaçınma uyarısı**.")
        elif (age >= 80 and egfr < 30):
            warnings.append("⚠️ Apiksaban: yaş ≥80 + eGFR <30 → **doz azaltımı uyarısı**.")
        elif egfr < 30:
            warnings.append("⚠️ Apiksaban: eGFR <30 → **doz azaltımı uyarısı**.")

    elif a in {"dabigatran", "dabigatran eteksilat"}:
        if egfr < 30:
            warnings.append("⚠️ Dabigatran: eGFR <30 → **kesme/kaçınma uyarısı**.")
        if age >= 80 or has_verapamil:
            warnings.append("⚠️ Dabigatran: (yaş ≥80) veya (eş zamanlı verapamil) → **doz azaltımı uyarısı**.")
        if (75 <= age < 80) or (30 <= egfr <= 50) or high_bleed:
            warnings.append(
                "ℹ️ Dabigatran: 75–80 yaş / eGFR 30–50 / yüksek kanama riski → **doz azaltımı bireysel değerlendirilir**."
            )

    elif a in {"edoksaban", "edoxaban"}:
        if egfr < 15:
            warnings.append("⚠️ Edoksaban: eGFR <15 → **kesme/kaçınma uyarısı**.")
        elif 15 <= egfr <= 50:
            warnings.append("⚠️ Edoksaban: eGFR 15–50 → **doz azaltımı uyarısı**.")
        if has_edox_interaction:
            warnings.append(
                "⚠️ Edoksaban: etkileşimli ilaç (siklosporin/dronedarone/eritromisin/ketokonazol) → **doz azaltımı uyarısı**."
            )

    elif a in {"rivaroksaban", "rivaroxaban"}:
        if egfr < 15:
            warnings.append("⚠️ Rivaroksaban: eGFR <15 → **kesme/kaçınma uyarısı**.")
        elif 15 <= egfr <= 49:
            warnings.append("⚠️ Rivaroksaban: eGFR 15–49 → **doz azaltımı uyarısı**.")

    return warnings


def get_af_rate_control_text(has_af: str, hr: int, has_hf: str, lvef: str, current_meds: list[str]) -> str:
    brady_note = get_bradycardia_meds_note(hr=hr, has_hf=has_hf, current_meds=current_meds)

    if has_af != "Evet":
        base = "- AF’ye yönelik hız kontrol önerisi: Endike değil.\n"
        if brady_note:
            base += brady_note
        return base

    if hr >= 110:
        status = "kontrolsüz (yüksek ventrikül yanıtı)"
    elif hr >= 90:
        status = "kısmi kontrol"
    else:
        status = "kontrollü"

    on_bb = meds_contains_any(current_meds, BETA_BLOCKERS)
    on_non_dhp = meds_contains_any(current_meds, NON_DHP_CCB)
    hfrEF = (has_hf == "Evet" and lvef == "<40%")

    lines = [f"- AF perioperatif hız kontrolü: Ventrikül yanıtı {status} (≈{hr}/dk)."]

    if on_bb:
        lines.append("- Mevcut tedavide beta-bloker mevcut: perioperatif dönemde hemodinami izin verdiği ölçüde sürdürülmesi uygundur.")
    if on_non_dhp:
        if hfrEF:
            lines.append("- Non-DHP KKB (verapamil/diltiazem) mevcut: LVEF <40% olguda negatif inotropi nedeniyle dikkat/kaçınılması gerektiği hatırlatılır.")
        else:
            lines.append("- Non-DHP KKB (verapamil/diltiazem) mevcut: uygun hastada hız kontrolünde kullanılabilir; hipotansiyon/bradikardi açısından izlem önerilir.")

    if hfrEF:
        lines.append("- HFrEF varlığında non-DHP KKB’den kaçınma; hız kontrolünde beta-bloker ± digoksin; instabilitede amiodaron multidisipliner kararla düşünülebilir.")
    else:
        lines.append("- Hemodinami stabil hastada hız kontrolünde beta-bloker veya non-DHP KKB; instabilitede öncelik hemodinamik stabilizasyondur.")

    if brady_note:
        lines.append(brady_note.strip())

    return "\n".join(lines) + "\n"


def get_postop_af_risk_text(age: int, has_hf: str, has_ckd: str, surgery_risk: str, hr: int) -> str:
    flags = 0
    if age >= 70:
        flags += 1
    if has_hf == "Evet":
        flags += 1
    if has_ckd == "Evet":
        flags += 1
    if surgery_risk == "Yüksek":
        flags += 1
    if hr >= 100:
        flags += 1

    if flags >= 3:
        risk_level = "artmış"
    elif flags == 2:
        risk_level = "orta"
    else:
        risk_level = "düşük/orta"

    return f"- Postop AF/aritmi riski: {risk_level}. İlk 48–72 saatte ritim/HR ve elektrolitlerin yakın izlenmesi önerilir."


# ----------------------------
# Antiplatelet monotherapy preop plan (ASA/Klopidogrel)
# - Düşük/Orta risk -> CONTINUE
# - Yüksek risk     -> STOP: ASA 7 days, Clopidogrel 5 days
# ----------------------------
def get_antiplatelet_monotherapy_preop_plan(agent: str, surgery_risk: str) -> str:
    a = (agent or "").strip()
    if surgery_risk in {"Düşük", "Orta"}:
        return f"- Antiplatelet monoterapi ({a}): Cerrahi kanama riski **düşük/orta** → **ilaç devamı önerilir (kesilmez).**"
    if surgery_risk == "Yüksek":
        if a == "Aspirin":
            return "- Antiplatelet monoterapi (Aspirin): Cerrahi kanama riski **yüksek** → **operasyondan 7 gün önce kes.**"
        if a == "Klopidogrel":
            return "- Antiplatelet monoterapi (Klopidogrel): Cerrahi kanama riski **yüksek** → **operasyondan 5 gün önce kes.**"
        return "- Antiplatelet monoterapi: Ajan belirtilmedi (yüksek kanama riski)."
    return "- Antiplatelet monoterapi: Cerrahi kanama riski belirlenemedi."


# ----------------------------
# OAC monotherapy preop plan is handled by Tool-2 (OacRuleEngine)
# Here we only provide a UI hint line.
# ----------------------------
def get_oac_monotherapy_hint(oac_agent: str) -> str:
    a = (oac_agent or "").strip()
    if not a or a == "Bilinmiyor":
        return "- OAC monoterapi: Ajan seçilmedi → **Warfarin/Apiksaban/Rivaroksaban/Dabigatran/Edoksaban** seçeneklerinden biri seçilmeli."
    return f"- OAC monoterapi: **{a}** (kesme/bridging/yeniden başlama planı Tool-2’ye göre oluşturulur)."


# ----------------------------
# Consultation note generator
# ----------------------------
def generate_consultation_note(context: dict, dapt_result: dict, oac_text_block: str, device_note: str) -> str:
    today = datetime.now().strftime("%d.%m.%Y")
    hr_val = int(context.get("hr", 0) or 0)

    rhythm_line = (
        f"Atriyal fibrilasyon, ventrikül yanıtı yaklaşık {hr_val}/dk."
        if context.get("has_af") == "Evet"
        else f"Sinüs ritmi, kalp hızı yaklaşık {hr_val}/dk."
    )

    symptoms_list = context.get("symptoms", [])
    symptom_text = ", ".join(symptoms_list) if symptoms_list and "Yok" not in symptoms_list else "Aktif kardiyak semptom tariflemiyor."

    hf_block = "- Kalp yetersizliği: Yok / bilinmiyor.\n"
    if context.get("has_hf") == "Evet":
        hf_block = (
            f"- Kalp yetersizliği: VAR (NYHA: {context.get('nyha')}, LVEF: {context.get('lvef')}).\n"
            "- Perioperatif volüm/hemodinami: Hipovolemi ve hipervolemiden kaçınılmalı; sıvı yönetimi hedefe yönelik titrasyonla yürütülmelidir.\n"
        )

    ckd_block = "- Kronik böbrek hastalığı: Yok / bilinmiyor.\n"
    if context.get("has_ckd") == "Evet":
        egfr = float(context.get("egfr", 0) or 0)
        egfr_text = f"{egfr:.0f} ml/dk/1.73m²" if egfr > 0 else "bilinmiyor"
        ckd_block = f"- Kronik böbrek hastalığı: VAR (eGFR: {egfr_text}). Nefrotoksik ajanlardan kaçınılmalı; elektrolit/volüm yakın izlenmelidir.\n"

    comorb = []
    if context.get("has_dm") == "Evet":
        comorb.append("DM")
    if context.get("has_ht") == "Evet":
        comorb.append("HT")
    if context.get("has_cad") == "Evet":
        comorb.append("KAH/PCI öyküsü")
    if context.get("has_af") == "Evet":
        comorb.append("AF")
    if context.get("has_mech_valve") == "Evet":
        comorb.append("Mekanik kapak")
    if context.get("has_hf") == "Evet":
        comorb.append("Kalp yetersizliği")
    if context.get("has_ckd") == "Evet":
        comorb.append("CKD")
    if context.get("has_device") == "Evet":
        comorb.append(f"Kardiyak cihaz ({context.get('device_type')})")
    comorb_text = ", ".join(comorb) if comorb else "Belirtilmedi"

    tests = ["12 derivasyonlu ECG (bazal)"]
    if context.get("surgery_risk") in ["Orta", "Yüksek"] or context.get("functional_capacity") in ["<4 MET", "Bilinmiyor"]:
        tests.append("Bazal hs-troponin (ve merkez protokolüne göre postop seri izlem)")
    if context.get("has_hf") == "Evet" or context.get("surgery_risk") in ["Orta", "Yüksek"]:
        tests.append("Gereğinde TTE (klinik/endikasyona göre)")
    if context.get("has_hf") == "Evet":
        tests.append("BNP/NT-proBNP (risk katmanlaması için düşünülebilir)")
    tests_text = "\n".join([f"- {t}" for t in tests])

    monitoring = [
        "İntraoperatif hemodinamik yakın izlem (TA, nabız, SpO₂).",
        "Postop dönemde aritmi/iskemi açısından klinik + ECG izlem.",
    ]
    if context.get("surgery_risk") in ["Orta", "Yüksek"]:
        monitoring.append("Postop hs-troponin izlemi (ilk 48–72 saat, merkez pratiğine göre).")
    monitoring.append(
        get_postop_af_risk_text(
            age=int(context.get("patient_age", 0) or 0),
            has_hf=context.get("has_hf"),
            has_ckd=context.get("has_ckd"),
            surgery_risk=context.get("surgery_risk"),
            hr=hr_val,
        )
    )
    monitoring_text = "\n".join([f"- {m}" if not m.startswith("- ") else m for m in monitoring])

    meds = context.get("current_meds", [])
    meds_text = ", ".join(meds) if meds else "Belirtilmedi"

    af_rate_control = get_af_rate_control_text(
        has_af=context.get("has_af"),
        hr=hr_val,
        has_hf=context.get("has_hf"),
        lvef=context.get("lvef"),
        current_meds=meds,
    )

    # ----------------------------
    # Antithrombotic blocks (DAPT vs Monotherapy)
    # ----------------------------
    ant_strategy = context.get("antithrombotic_strategy", "—")
    pci_time = context.get("pci_time", "—")

    if ant_strategy == "Monoterapi-OAC":
        oac_mono_agent = context.get("mono_oac_agent", "Bilinmiyor")
        antithrombotic_block = "\n".join(
            [
                "F1) Antitrombotik Tedavi",
                f"- PCI zamanı: {pci_time}",
                "- Strateji: Monoterapi (OAC)",
                f"- Ajan: {oac_mono_agent}",
                get_oac_monotherapy_hint(oac_mono_agent),
            ]
        )
    elif ant_strategy == "Monoterapi-AP":
        ap_agent = context.get("mono_ap_agent", "Bilinmiyor")
        ap_plan = get_antiplatelet_monotherapy_preop_plan(ap_agent, context.get("surgery_risk"))
        antithrombotic_block = "\n".join(
            [
                "F1) Antitrombotik Tedavi",
                f"- PCI zamanı: {pci_time}",
                "- Strateji: Monoterapi (Antiplatelet)",
                f"- Ajan: {ap_agent}",
                ap_plan,
            ]
        )
    elif ant_strategy == "DAPT (Tool-1)":
        antithrombotic_block = "\n".join(
            [
                "F1) Antitrombotik Tedavi",
                f"- PCI zamanı: {pci_time}",
                "- Strateji: DAPT (Tool-1)",
                f"- Aspirin: {context.get('aspirin_dose')}",
                f"- P2Y12 inhibitörü: {context.get('p2y12_agent_ui')}",
            ]
        )
    else:
        antithrombotic_block = "\n".join(
            [
                "F1) Antitrombotik Tedavi",
                "- Strateji: Belirtilmedi / uygulanmadı.",
            ]
        )

    plan = dapt_result.get("recommendation_tr", "")
    rec_class = dapt_result.get("class", "")

    note = f"""
PREOPERATİF KARDİYOLOJİ KONSÜLTASYON NOTU
Tarih: {today}

A) Hasta Bilgileri
- Yaş/Cinsiyet: {context.get("patient_age")} / {context.get("patient_sex")}
- Komorbiditeler: {comorb_text}
- Mevcut ilaçlar: {meds_text}

B) Vital Bulgular
- Ritim: {rhythm_line}
- TA (mmHg): {context.get("sbp")}/{context.get("dbp")}

C) İşlem / Cerrahi Bilgisi
- Planlanan işlem: {context.get("selected_surgery")}
- Cerrahi kardiyak risk (Table 5): {context.get("surgery_risk")}
- Cerrahi aciliyeti: {context.get("urgency")}

D) Kardiyak Öykü – Semptom / Fonksiyonel Kapasite
- Semptomlar: {symptom_text}
- Fonksiyonel kapasite: {context.get("functional_capacity")}

E) Klinik Değerlendirme (perioperatif kritik noktalar)
{hf_block}{ckd_block}
{device_note}

F) Antitrombotik Yönetim
{antithrombotic_block}

{oac_text_block}

G) Kılavuz Temelli Perioperatif Antitrombotik Plan (Tool-1 / DAPT)
- Öneri: {plan}
- Öneri sınıfı: {rec_class}

H) Ritim / Hız kontrolü ve perioperatif ilaç notu
{af_rate_control}

I) Önerilen Tetkikler
{tests_text}

J) Perioperatif İzlem Önerileri
{monitoring_text}

K) Sonuç / Plan
- Bu çıktı karar destek amaçlıdır; nihai klinik karar ilgili hekim değerlendirmesi ve multidisipliner ekip kararı ile verilecektir.
""".strip()

    return note


# ----------------------------
# Streamlit UI — SINGLE PAGE
# ----------------------------
st.set_page_config(page_title="CAPE Tool (Tek Sayfa)", layout="centered")
st.title("CAPE – Preop Kardiyoloji Karar Destek (Tek Sayfa)")

engine = DaptRuleEngine("rules/dapt.yaml")
oac_engine = OacRuleEngine()

if "answers" not in st.session_state:
    st.session_state["answers"] = {}
if "dapt_result" not in st.session_state:
    st.session_state["dapt_result"] = None


# ----------------------------
# 1) Shared patient inputs
# ----------------------------
with st.expander("1) Hasta Yaş, Cerrahi ve Klinik Bilgiler", expanded=True):
    colA, colB = st.columns(2)
    with colA:
        patient_age = st.number_input("Yaş", min_value=0, max_value=120, value=55, step=1)
    with colB:
        patient_sex = st.selectbox("Cinsiyet", ["Erkek", "Kadın"])

    st.markdown("---")

    selected_surgery = st.selectbox("Planlanan işlemi seçin (Table 5)", SURGERY_OPTIONS, index=0)
    auto_risk = SURGERY_TO_RISK.get(selected_surgery, "Orta")
    surgery_risk = st.selectbox(
        "Cerrahi kardiyak risk (otomatik)",
        ["Düşük", "Orta", "Yüksek"],
        index=["Düşük", "Orta", "Yüksek"].index(auto_risk),
        disabled=True,
    )
    urgency = st.selectbox("Cerrahi aciliyeti", ["Elektif", "Time-sensitive", "Acil"])

    st.markdown("---")

    c1, c2, c3 = st.columns(3)
    with c1:
        hr = st.number_input("EKG hızı / Nabız (dk)", min_value=0, max_value=250, value=80, step=1)
    with c2:
        sbp = st.number_input("Sistolik TA (mmHg)", min_value=0, max_value=300, value=130, step=1)
    with c3:
        dbp = st.number_input("Diyastolik TA (mmHg)", min_value=0, max_value=200, value=80, step=1)

    st.markdown("---")

    symptoms = st.multiselect(
        "Mevcut semptomlar",
        ["Angina", "Dispne", "Senkop", "Kalp yetersizliği semptomu", "Yok"],
        default=["Yok"],
    )
    functional_capacity = st.selectbox("Fonksiyonel kapasite (MET)", ["≥4 MET", "<4 MET", "Bilinmiyor"])

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        has_hf = st.selectbox("Kalp yetersizliği var mı?", ["Hayır", "Evet"])
        nyha = st.selectbox("NYHA sınıfı", ["Bilinmiyor", "I", "II", "III", "IV"], disabled=(has_hf == "Hayır"))
        lvef = st.selectbox("LVEF", ["Bilinmiyor", "≥50%", "40–49%", "<40%"], disabled=(has_hf == "Hayır"))
    with col2:
        has_af = st.selectbox("Atriyal fibrilasyon (AF)", ["Hayır", "Evet"])
        has_ckd = st.selectbox("Kronik böbrek hastalığı (CKD)", ["Hayır", "Evet"])
        egfr = st.number_input("eGFR (ml/dk/1.73m²) - varsa", min_value=0.0, max_value=200.0, value=0.0, step=1.0)

    has_dm = st.selectbox("Diabetes mellitus", ["Hayır", "Evet"])
    has_ht = st.selectbox("Hipertansiyon", ["Hayır", "Evet"])

    # ----------------------------
    # CAD/PCI + ≥1 year branching with AF-aware monotherapy
    # ----------------------------
    has_cad = st.selectbox("Koroner arter hastalığı / PCI öyküsü", ["Hayır", "Evet"])

    pci_time = "—"
    antithrombotic_strategy = "—"   # "DAPT (Tool-1)" | "Monoterapi-AP" | "Monoterapi-OAC" | "—"
    mono_ap_agent = "—"
    mono_oac_agent = "Bilinmiyor"

    if has_cad == "Evet":
        pci_time = st.selectbox(
            "PCI/AKS üzerinden 1 yıl geçti mi?",
            ["<1 yıl", "≥1 yıl"],
            index=0,
            key="pci_time",
        )

        if pci_time == "<1 yıl":
            antithrombotic_strategy = "DAPT (Tool-1)"
        else:
            # PCI ≥1 yıl
            if has_af == "Evet":
                # AF (+) -> OAC monoterapi
                antithrombotic_strategy = "Monoterapi-OAC"
                st.markdown("### Monoterapi (AF + PCI ≥1 yıl) → OAC seçimi")
                mono_oac_agent = st.selectbox(
                    "OAC ajanı (monoterapi)",
                    ["Bilinmiyor", "Warfarin", "Apiksaban", "Rivaroksaban", "Dabigatran", "Edoksaban"],
                    index=0,
                    key="mono_oac_agent",
                    help="AF (+) ve PCI ≥1 yıl: antiplatelet monoterapi yerine OAC monoterapi tercih edilir.",
                )
                st.info(get_oac_monotherapy_hint(mono_oac_agent))
            else:
                # AF (-) -> antiplatelet monoterapi
                antithrombotic_strategy = "Monoterapi-AP"
                st.markdown("### Monoterapi (AF yok + PCI ≥1 yıl) → Aspirin/Klopidogrel")
                mono_ap_agent = st.selectbox(
                    "Antiplatelet monoterapi ajanı",
                    ["Aspirin", "Klopidogrel"],
                    index=0,
                    key="mono_ap_agent",
                )
                st.info(get_antiplatelet_monotherapy_preop_plan(mono_ap_agent, surgery_risk))

    has_mech_valve_ui = st.selectbox("Mekanik kapak var mı?", ["Hayır", "Evet"])

    # Cardiac device logic
    st.markdown("---")
    has_device = st.selectbox("Hastada pacemaker/ICD/CRT var mı?", ["Hayır", "Evet"])
    device_type = "—"
    pace_dependent = "—"
    if has_device == "Evet":
        device_type = st.selectbox("Cihaz tipi", ["Permanent pacemaker", "ICD", "CRT"])
        pace_dependent = st.selectbox("Hasta pace bağımlı mı?", ["Hayır", "Evet"])
        device_note_preview = get_device_management_note(has_device, device_type, pace_dependent)
        if device_note_preview.strip():
            st.markdown("**Cihaz Yönetimi Uyarısı (Önizleme)**")
            st.warning(device_note_preview)

    st.markdown("---")
    st.caption(DRUGS_CAPTION)
    current_meds = st.multiselect("Kullandığı ilaçlar (type-ahead)", options=DRUGS, default=[])


# ----------------------------
# 2) Tool-1 (DAPT) -> only if PCI <1 year
# ----------------------------
show_tool1 = (has_cad == "Evet") and (pci_time == "<1 yıl")

with st.expander("2) Tool-1: DAPT (yalnızca PCI <1 yıl ise)", expanded=show_tool1):
    if not show_tool1:
        if has_cad != "Evet":
            st.info("Koroner arter hastalığı / PCI öyküsü **Hayır** seçildiği için Tool-1 (DAPT) algoritması gizlendi.")
        else:
            st.success("PCI/AKS üzerinden **≥1 yıl** geçtiği için monoterapi dalı aktif. Tool-1 (DAPT) uygulanmadı.")
        aspirin_dose = "—"
        p2y12_agent_ui = "—"
    else:
        st.caption(f"Kural seti: {engine.title_tr}")

        st.markdown("---")
        st.subheader("Antiplatelet Tedavi (Klinik Kayıt)")

        aspirin_dose = st.selectbox(
            "Aspirin günlük dozu",
            ["Bilinmiyor", "75 mg/gün", "81 mg/gün", "100 mg/gün", "150 mg/gün", "300 mg/gün"],
            index=0,
            key="aspirin_dose",
        )
        p2y12_agent_ui = st.selectbox(
            "P2Y12 inhibitörü (klinik kayıt)",
            ["Bilinmiyor", "Klopidogrel", "Prasugrel", "Tikagrelor"],
            index=0,
            key="p2y12_agent_ui",
        )

        st.markdown("---")
        answers = st.session_state["answers"]
        visible_questions = engine.get_visible_questions(answers)

        for q in visible_questions:
            key = f"q_{q.id}"
            default = answers.get(q.id, q.options[0] if q.options else "")
            idx = q.options.index(default) if default in q.options else 0
            val = st.radio(q.text_tr, q.options, index=idx, key=key)
            answers[q.id] = val

        st.markdown("---")
        if st.button("Tool-1 Sonucu Göster (opsiyonel)", key="btn_tool1"):
            dapt_result = engine.evaluate(answers)
            st.session_state["dapt_result"] = dapt_result
            st.success(dapt_result.get("recommendation_tr", ""))
            if dapt_result.get("class"):
                st.info(f"Öneri sınıfı: {dapt_result['class']}")
            with st.expander("Ham yanıtlar (Tool-1)"):
                st.json(answers)


# ----------------------------
# 3) Tool-2 (OAK/NOAC)
# ----------------------------
# AF varsa her zaman göster; ayrıca mekanik kapakta göster.
# Ayrıca AF + PCI≥1y dalında OAC seçildi/isteniyor: Tool-2 planını otomatik üretmek için yine göster.
show_tool2 = (has_af == "Evet") or (has_mech_valve_ui == "Evet")

oac_agent = "Bilinmiyor"
bleed_risk_oac = "Düşük-Orta"
very_high_bleed = False
high_te_risk = False

with st.expander("3) Tool-2: OAK/NOAC (AF veya mekanik kapak varsa)", expanded=show_tool2):
    if not show_tool2:
        st.info("AF **Hayır** ve Mekanik kapak **Hayır** seçildiği için Tool-2 (OAK/NOAC) algoritması gizlendi.")
    else:
        OAC_OPTIONS = ["Bilinmiyor", "Warfarin", "Apiksaban", "Rivaroksaban", "Edoksaban", "Dabigatran"]

        # Eğer AF + PCI≥1y monoterapi-oac dalı varsa, o seçimi Tool-2 varsayılanı yapalım
        preferred_oac = mono_oac_agent if antithrombotic_strategy == "Monoterapi-OAC" else "Bilinmiyor"

        if has_mech_valve_ui == "Evet":
            oac_agent = st.selectbox(
                "Oral antikoagülan",
                OAC_OPTIONS,
                index=OAC_OPTIONS.index("Warfarin"),
                disabled=True,
                help="Mekanik kapakta DOAC kullanılmaz; otomatik Warfarin seçildi.",
                key="oac_agent",
            )
        else:
            default_idx = OAC_OPTIONS.index(preferred_oac) if preferred_oac in OAC_OPTIONS else 0
            oac_agent = st.selectbox("Oral antikoagülan", OAC_OPTIONS, index=default_idx, key="oac_agent")

        bleed_risk_oac = st.selectbox(
            "Prosedür kanama riski (OAK/NOAC için)",
            ["Minör", "Düşük-Orta", "Yüksek"],
            index=1,
            key="bleed_risk_oac",
        )

        very_high_bleed = st.checkbox(
            "Çok yüksek kanama riski (örn. spinal/epidural, intrakraniyal, vitreoretinal vb.)",
            value=False,
            key="very_high_bleed",
        )

        has_mech_valve = (has_mech_valve_ui == "Evet")
        if has_mech_valve:
            high_te_risk = (
                st.selectbox(
                    "Yüksek tromboemboli riski var mı? (mekanik kapak + RF vb.)",
                    ["Hayır", "Evet"],
                    index=0,
                    key="high_te_risk_ui",
                )
                == "Evet"
            )
        else:
            st.caption("Not: Mekanik kapak yoksa bridging/TE risk değerlendirmesi genellikle daha sınırlıdır.")
            high_te_risk = False

        st.markdown("---")
        if st.button("Tool-2 Sonucu Göster (opsiyonel)", key="btn_tool2"):
            mapped_bleed = "Düşük-Orta" if bleed_risk_oac in ["Minör", "Düşük-Orta"] else "Yüksek"
            res = oac_engine.evaluate(
                agent=oac_agent,
                urgency=urgency,
                bleed_risk=mapped_bleed,
                very_high_bleed=very_high_bleed,
                egfr=egfr,
                has_mech_valve=has_mech_valve,
                high_te_risk=high_te_risk,
            )

            dose_warnings = get_doac_dose_warnings(
                agent=oac_agent,
                age=int(patient_age or 0),
                egfr=float(egfr or 0),
                current_meds=current_meds,
                bleed_risk=mapped_bleed,
                very_high_bleed=very_high_bleed,
            )

            st.write("### Tool-2 Çıktı")
            st.write(res.summary_tr)
            st.write(res.stop_plan_tr)
            st.write(res.bridging_tr)
            st.write(res.restart_plan_tr)
            st.caption(res.cautions_tr)

            if has_mech_valve:
                st.markdown("### Mekanik Kapak – Warfarin / EE Profilaksisi / Bridging Notu")
                st.info(get_mech_valve_warfarin_note())

            if dose_warnings:
                st.markdown("### DOAC Doz / Kesme Uyarıları")
                for w in dose_warnings:
                    if "kesme" in w.lower() or "kaçınma" in w.lower():
                        st.warning(w)
                    else:
                        st.info(w)


# ----------------------------
# 4) Konsültasyon Notu (AUTO-CALC)
# ----------------------------
with st.expander("4) Konsültasyon Notu (Tool-1 + Tool-2 birleşik)", expanded=True):
    if st.button("Öneri + Konsültasyon Notu Oluştur", key="btn_generate_all"):
        # ---- Tool-1: auto evaluate if DAPT active ----
        if show_tool1:
            dapt_result = engine.evaluate(st.session_state.get("answers", {}))
            aspirin_val = st.session_state.get("aspirin_dose", "Bilinmiyor")
            p2y12_val = st.session_state.get("p2y12_agent_ui", "Bilinmiyor")
        else:
            # monoterapi branch -> Tool-1 neutral
            dapt_result = {
                "output_id": "tool1_inactive",
                "recommendation_tr": "Tool-1 (DAPT) uygulanmadı (PCI ≥1 yıl veya KAH/PCI yok).",
                "class": "",
            }
            aspirin_val = "—"
            p2y12_val = "—"

        # ---- Device note ----
        device_note = get_device_management_note(has_device, device_type, pace_dependent)

        # ---- Tool-2: AUTO evaluate if visible ----
        if show_tool2:
            mapped_bleed = "Düşük-Orta" if bleed_risk_oac in ["Minör", "Düşük-Orta"] else "Yüksek"
            has_mech_valve = (has_mech_valve_ui == "Evet")
            agent_for_eval = "Warfarin" if has_mech_valve else oac_agent

            oac_res = oac_engine.evaluate(
                agent=agent_for_eval,
                urgency=urgency,
                bleed_risk=mapped_bleed,
                very_high_bleed=very_high_bleed,
                egfr=egfr,
                has_mech_valve=has_mech_valve,
                high_te_risk=high_te_risk,
            )

            dose_warnings = get_doac_dose_warnings(
                agent=agent_for_eval,
                age=int(patient_age or 0),
                egfr=float(egfr or 0),
                current_meds=current_meds,
                bleed_risk=mapped_bleed,
                very_high_bleed=very_high_bleed,
            )

            if has_mech_valve:
                base_lines = [
                    "F2) Oral Antikoagülasyon (Tool-2 / OAK-NOAC)",
                    oac_res.summary_tr,
                    "",
                    get_mech_valve_warfarin_note(),
                ]
            else:
                base_lines = [
                    "F2) Oral Antikoagülasyon (Tool-2 / OAK-NOAC)",
                    oac_res.summary_tr,
                    oac_res.stop_plan_tr,
                    oac_res.bridging_tr,
                    oac_res.restart_plan_tr,
                ]

            if dose_warnings:
                base_lines += ["", "F2-Not) DOAC Doz / Kesme Uyarıları:", *[f"- {w}" for w in dose_warnings]]

            oac_block = "\n".join([l for l in base_lines if l is not None and str(l).strip() != ""])
        else:
            oac_block = "F2) Oral Antikoagülasyon (Tool-2 / OAK-NOAC)\n- Tool-2 uygulanmadı: AF veya mekanik kapak yok."

        ctx = {
            "patient_age": patient_age,
            "patient_sex": patient_sex,
            "selected_surgery": selected_surgery,
            "surgery_risk": surgery_risk,
            "urgency": urgency,
            "hr": hr,
            "sbp": sbp,
            "dbp": dbp,
            "symptoms": symptoms,
            "functional_capacity": functional_capacity,
            "has_hf": has_hf,
            "nyha": nyha,
            "lvef": lvef,
            "has_af": has_af,
            "has_ckd": has_ckd,
            "egfr": egfr,
            "has_dm": has_dm,
            "has_ht": has_ht,
            "has_cad": has_cad,
            "pci_time": pci_time,
            "antithrombotic_strategy": antithrombotic_strategy,
            "mono_ap_agent": mono_ap_agent,
            "mono_oac_agent": mono_oac_agent,
            "has_mech_valve": has_mech_valve_ui,
            "has_device": has_device,
            "device_type": device_type,
            "pace_dependent": pace_dependent,
            "aspirin_dose": aspirin_val,
            "p2y12_agent_ui": p2y12_val,
            "current_meds": current_meds,
        }

        note = generate_consultation_note(ctx, dapt_result, oac_block, device_note)
        st.text_area("Kopyalanabilir çıktı", note, height=620)

