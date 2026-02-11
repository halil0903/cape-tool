from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import yaml


@dataclass
class Question:
    id: str
    text_tr: str
    qtype: str
    options: List[str]
    visible_if: Optional[Dict[str, str]] = None


@dataclass
class OutputRule:
    id: str
    when: str
    recommendation_tr: str
    klass: str


class DaptRuleEngine:
    """
    Minimal YAML-driven rule engine for Tool-1 (DAPT).
    - Reads rules/dapt.yaml
    - Evaluates derived variable: high_thrombotic_risk
    - Returns the first matching output rule
    """

    def __init__(self, yaml_path: str):
        with open(yaml_path, "r", encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)

        self.tool_id = self.cfg.get("tool_id")
        self.title_tr = self.cfg.get("title_tr")

        self.questions: List[Question] = []
        for q in self.cfg.get("questions", []):
            self.questions.append(
                Question(
                    id=q["id"],
                    text_tr=q["text_tr"],
                    qtype=q.get("type", "choice"),
                    options=q.get("options", []),
                    visible_if=q.get("visible_if"),
                )
            )

        self.outputs: List[OutputRule] = []
        for o in self.cfg.get("outputs", []):
            self.outputs.append(
                OutputRule(
                    id=o["id"],
                    when=o["when"],
                    recommendation_tr=o["recommendation_tr"].strip(),
                    klass=o.get("class", "").strip(),
                )
            )

    @staticmethod
    def _is_visible(visible_if: Optional[Dict[str, str]], answers: Dict[str, Any]) -> bool:
        if not visible_if:
            return True
        for k, v in visible_if.items():
            if answers.get(k) != v:
                return False
        return True

    @staticmethod
    def _compute_high_thrombotic_risk(answers: Dict[str, Any]) -> str:
        pci = answers.get("pci_lt_1m") == "Evet"
        acs = answers.get("acs_lt_3m") == "Evet"
        st = answers.get("high_stent_thrombosis_risk") == "Evet"
        return "Evet" if (pci or acs or st) else "Hayır"

    def get_visible_questions(self, answers: Dict[str, Any]) -> List[Question]:
        return [q for q in self.questions if self._is_visible(q.visible_if, answers)]

    def evaluate(self, answers: Dict[str, Any]) -> Dict[str, str]:
        # derive high_thrombotic_risk only if high_bleeding_risk_ncs == "Evet"
        if answers.get("high_bleeding_risk_ncs") == "Evet":
            answers["high_thrombotic_risk"] = self._compute_high_thrombotic_risk(answers)
        else:
            answers["high_thrombotic_risk"] = "Hayır"

        # safe eval context
        ctx = dict(answers)

        for rule in self.outputs:
            if eval(rule.when, {"__builtins__": {}}, ctx) is True:
                return {
                    "output_id": rule.id,
                    "recommendation_tr": rule.recommendation_tr,
                    "class": rule.klass,
                    "high_thrombotic_risk": answers.get("high_thrombotic_risk", ""),
                }

        return {
            "output_id": "no_match",
            "recommendation_tr": "Girilen yanıtlara göre uygun öneri bulunamadı. Lütfen yanıtları kontrol edin.",
            "class": "",
            "high_thrombotic_risk": answers.get("high_thrombotic_risk", ""),
        }
