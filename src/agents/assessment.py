"""Assessment Agent — generates grounded, cited practice questions with smart
distractors (each wrong answer maps to a named misconception), and runs the
exam-blueprint coverage gate per candidate."""
from __future__ import annotations

from .base import BaseAgent, Turn
from .. import readiness


class AssessmentAgent(BaseAgent):
    name = "Nadia Okonkwo"
    persona_label = "Chief Examiner"
    color = "bright_green"
    system_prompt = ("You are Nadia Okonkwo, the Chief Examiner. Exacting and fair, with zero "
                     "sugar-coating. You produce exam-quality, source-cited practice questions whose "
                     "wrong answers each target a real misconception, and you judge readiness per "
                     "exam domain — never on the average alone.")

    # A grounded item whose distractors encode named misconceptions (KB-ENABLE-001).
    QUESTION_BANK = {
        "AZ-204": {
            "stem": "An Azure Function must run whenever a message arrives on a Storage Queue, "
                    "and also write a row to Table Storage. Which statement is correct?",
            "options": {
                "A": "The function has exactly one trigger (the queue) and may add output bindings.",
                "B": "The function needs one binding and may declare multiple triggers.",
                "C": "Triggers and bindings are interchangeable, so either can fire the function.",
                "D": "The function should declare two triggers for redundancy.",
            },
            "answer": "A",
            "misconceptions": {
                "B": "confuses trigger with binding — a function has ONE trigger but many bindings",
                "C": "believes triggers and bindings are interchangeable",
                "D": "believes a function may have multiple triggers",
            },
            "source": "KB-ENABLE-001",
            "domain": "Azure Functions",
        }
    }

    def _generic_item(self, cert) -> dict:
        top = max(cert.exam_domains, key=lambda d: d["weight"])
        return {
            "stem": f"Within {cert.id}, which area carries the most exam weight and should be "
                    f"prioritised first?",
            "options": {
                "A": f"{top['name']} ({top['weight']:.0%} of the exam)",
                "B": "Whichever domain the learner already feels confident in",
                "C": "All domains equally, ignoring exam weighting",
                "D": "Only the domains with the shortest study material",
            },
            "answer": "A",
            "misconceptions": {
                "B": "studies to comfort rather than to exam weighting",
                "C": "ignores that exam domains are weighted unequally",
                "D": "optimises for effort, not exam impact",
            },
            "source": "KB-ENABLE-001",
            "domain": top["name"],
        }

    def assess(self, cert_id: str, candidate_ids: list[str]) -> Turn:
        cert = self.store.cert(cert_id)
        item = self.QUESTION_BANK.get(cert_id) or self._generic_item(cert)
        grounded = self.store.citation_exists(item["source"])

        # Coverage gate per candidate
        coverage: dict[str, list[tuple[str, float, float]]] = {}
        for lid in candidate_ids:
            learner = self.store.learner(lid)
            coverage[lid] = readiness.coverage_gaps(learner, cert)

        lines = [
            f"Generated item · domain {item['domain']} · cite {item['source']} "
            f"({'verified in KB' if grounded else 'NOT in KB — will flag'})",
            f"Q: {item['stem']}",
        ]
        for k, v in item["options"].items():
            mark = "  ✔ correct" if k == item["answer"] else ""
            lines.append(f"   {k}) {v}{mark}")
        lines.append("Distractor rationale (smart distractors): "
                     + "; ".join(f"{k}→{why}" for k, why in item["misconceptions"].items()))

        # Coverage summary
        gate_lines = []
        for lid in candidate_ids:
            learner = self.store.learner(lid)
            gaps = coverage[lid]
            if gaps:
                gate_lines.append(f"{learner.name}: weak in " + ", ".join(f"{n} {s:.0f}%" for n, s, _ in gaps))
            else:
                gate_lines.append(f"{learner.name}: clears all domains ≥75%")
        lines.append("Coverage gate → " + " | ".join(gate_lines))

        n_weak = sum(1 for lid in candidate_ids if coverage[lid])
        fallback = (f"Item is grounded in {item['source']} targeting the {item['domain']} domain; "
                    f"distractors map to named misconceptions. Coverage gate flags {n_weak} of "
                    f"{len(candidate_ids)} candidates with a sub-75% domain.")
        headline = self.voice("Summarise the grounded item and the coverage-gate outcome.",
                              "\n".join(lines[:1] + gate_lines), fallback)

        return Turn(self.name, self.persona_label, self.color, headline, lines, kind="gate",
                    data={"question_source": item["source"], "grounded": grounded,
                          "coverage": coverage, "citations": [item["source"]]})
