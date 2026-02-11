# core/oac_engine.py
from dataclasses import dataclass

@dataclass
class OacResult:
    summary_tr: str
    stop_plan_tr: str
    restart_plan_tr: str
    bridging_tr: str
    cautions_tr: str


class OacRuleEngine:
    """
    Tool-2 (OAK/NOAC) — perioperatif yönetim için kural motoru.
    Bu sınıf, UI'dan gelen yapılandırılmış girdilerle TR plan üretir.
    """

    def __init__(self, title_tr: str = "Tool-2: OAK/NOAC (Oral Antikoagülan)"):
        self.title_tr = title_tr

    # --- helpers ---
    def _is_noac(self, agent: str) -> bool:
        a = (agent or "").lower()
        return any(x in a for x in ["apiksaban", "rivaroksaban", "edoksaban", "dabigatran"])

    def _noac_last_dose_timing_hours(self, agent: str, egfr: float, bleed_risk: str, very_high: bool) -> int:
        """
        Basitleştirilmiş ESC yaklaşımı:
        - Xa inhibitörleri (apiksaban/rivaroksaban/edoksaban): düşük/orta 24h, yüksek 48h (eGFR>=30 varsayımı)
        - Dabigatran: renal fonksiyona duyarlı (>=50: 24/48; 30-49: 48/72-96)
        - Çok yüksek kanama riski (spinal/epidural vb): ~5 yarı-ömür -> genelde 72-120h
        """
        a = (agent or "").lower()
        egfr = float(egfr or 0)

        if very_high:
            # pratik: 96 saat (4 gün) default; dabigatran/ileri CKD'de 120 saate kadar uzar
            if "dabigatran" in a and egfr and egfr < 50:
                return 120
            return 96

        high = (bleed_risk == "Yüksek")

        # Dabigatran
        if "dabigatran" in a:
            if egfr >= 50:
                return 48 if high else 24
            if 30 <= egfr < 50:
                return 96 if high else 48
            # eGFR <30: elektif girişim için uzman değerlendirmesi
            return 120 if high else 96

        # Xa inhibitörleri
        if egfr and egfr < 30:
            # elektif için uzat
            return 72 if high else 48

        return 48 if high else 24

    def _restart_window_hours(self, bleed_risk: str, very_high: bool) -> tuple[int, int]:
        """
        Hemostaz sağlandıysa: düşük/orta 24h, yüksek 48-72h.
        Çok yüksek riskte genelde 48-72h ve prosedüre göre daha geç olabilir.
        """
        if very_high:
            return (48, 72)
        if bleed_risk == "Yüksek":
            return (48, 72)
        return (24, 24)

    def _bridging_text(self, agent: str, has_mech_valve: bool, high_te_risk: bool) -> str:
        if self._is_noac(agent):
            return "- Bridging: NOAC kullanan hastada rutin bridging önerilmez."
        # VKA
        if has_mech_valve and high_te_risk:
            return "- Bridging: Mekanik kapak + yüksek tromboemboli riski varlığında UFH/LMWH ile bridging multidisipliner kararla düşünülebilir."
        return "- Bridging: Düşük/orta trombotik riskte bridging önerilmez."

    # --- public API ---
    def evaluate(
        self,
        *,
        agent: str,
        urgency: str,
        bleed_risk: str,        # "Minör" / "Düşük-Orta" / "Yüksek"
        very_high_bleed: bool,  # spinal/epidural, intrakraniyal vb
        egfr: float,
        has_mech_valve: bool,
        high_te_risk: bool
    ) -> OacResult:

        agent = agent or "Bilinmiyor"
        urgency = urgency or "Elektif"
        bleed_risk = bleed_risk or "Düşük-Orta"

        # Urgent: stop immediately
        if urgency == "Acil":
            summary = f"- Antikoagülasyon: {agent}. Acil cerrahi planlanıyor."
            stop_plan = "- Öneri: NOAC/VKA derhal kesilir. Kanama riski yüksekse tersine çevirme (antidot/PCC) gereksinimi multidisipliner değerlendirilir."
            restart = "- Hemostaz sağlandıktan sonra kanama riski ve cerrahi ekiple birlikte değerlendirilerek yeniden başlama planlanır."
            bridging = self._bridging_text(agent, has_mech_valve, high_te_risk)
            cautions = "- Not: Bu çıktı karar destek amaçlıdır; acil durumda hematoloji/anestezi ile birlikte hızlı yönetim önerilir."
            return OacResult(summary, stop_plan, restart, bridging, cautions)

        # Planned / Time-sensitive
        if self._is_noac(agent):
            h = self._noac_last_dose_timing_hours(agent, egfr, "Yüksek" if bleed_risk == "Yüksek" else "Düşük-Orta", very_high_bleed)
            days = h // 24
            hours = h % 24
            h_txt = f"{days} gün" if hours == 0 else f"{days} gün {hours} saat" if days else f"{h} saat"

            summary = f"- Antikoagülasyon: {agent} (NOAC)."
            stop_plan = f"- Son doz zamanlaması: {bleed_risk} kanama riski ve eGFR≈{int(egfr) if egfr else 0} dikkate alınarak, elektif cerrahiden **{h_txt} önce** kesilmesi yeterlidir."
            r0, r1 = self._restart_window_hours(bleed_risk, very_high_bleed)
            if r0 == r1:
                restart = f"- Yeniden başlama: Hemostaz sağlandıysa genellikle **{r0} saat** sonra tam doz tekrar başlanabilir."
            else:
                restart = f"- Yeniden başlama: Hemostaz sağlandıysa genellikle **{r0}–{r1} saat** sonra tam doz tekrar başlanabilir."
            bridging = "- Bridging: NOAC kullanan hastada rutin bridging önerilmez."
            cautions = "- Çok yüksek kanama riski (örn. spinal/epidural) varsa daha uzun kesme aralığı ve yeniden başlama için cerrahi/anestezi ile ortak karar önerilir."
            return OacResult(summary, stop_plan, restart, bridging, cautions)

        # VKA
        summary = f"- Antikoagülasyon: {agent} (VKA/Warfarin varsayımı)."
        stop_plan = "- Kesilme: Elektif cerrahi öncesi warfarin genellikle **5 gün önce** kesilir; hedef INR cerrahi tipine göre doğrulanır."
        r0, r1 = self._restart_window_hours(bleed_risk, very_high_bleed)
        restart = "- Yeniden başlama: Kanama kontrolü sağlanır sağlanmaz (çoğu olguda ilk 24 saat içinde) warfarin tekrar başlanır; terapötik INR’a kadar köprüleme ihtiyacı ayrıca değerlendirilir."
        bridging = self._bridging_text(agent, has_mech_valve, high_te_risk)
        cautions = "- INR izlemi ve bridging kararı trombotik/kanama riski dengesiyle, cerrahi/anestezi ile birlikte verilmelidir."
        return OacResult(summary, stop_plan, restart, bridging, cautions)
