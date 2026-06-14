"""Learning Path Curator — maps roles to certifications and grounds the plan in
approved content with citations, retrieved from Foundry IQ (Azure AI Search)."""
from __future__ import annotations

from .base import BaseAgent, Turn


class CuratorAgent(BaseAgent):
    name = "Theo Park"
    persona_label = "Knowledge Lead"
    color = "green"
    system_prompt = ("You are Theo Park, the board's Knowledge Lead. Precise and scholarly — you never "
                     "state anything you cannot cite to an approved source. You map roles to "
                     "certifications and ground every recommendation in real documents.")

    # The heaviest exam domain for each cert → the Microsoft Learn module that closes it.
    LEARN_MODULES = {
        "SC-200": "Configure SIEM security operations with Microsoft Sentinel",
        "AZ-500": "Implement platform protection (Azure Security Engineer)",
        "SC-300": "Implement authentication and access management in Microsoft Entra",
        "SC-400": "Implement information protection in Microsoft Purview",
        "SC-900": "Describe the capabilities of Microsoft security solutions",
        "SC-100": "Design a Zero Trust strategy and architecture",
    }
    # What "ready" concretely looks like for each cert — the artefact a passing engineer can produce.
    ARTIFACTS = {
        "SC-200": "a Microsoft Sentinel analytics rule in KQL (SecurityIncident | where Severity == 'High' | summarize by AlertName)",
        "AZ-500": "an NSG rule plus a Conditional Access policy that blocks legacy authentication",
        "SC-300": "a Conditional Access policy enforcing phishing-resistant MFA",
        "SC-400": "a Microsoft Purview DLP policy that auto-labels and blocks confidential egress",
        "SC-900": "a clean explanation of the Microsoft Entra vs Defender vs Purview boundaries",
        "SC-100": "a Zero Trust reference architecture mapped to the six pillars",
    }

    def curate(self, cert_id: str) -> Turn:
        cert = self.store.cert(cert_id)
        chunks = self.store.search_knowledge(cert.id, cert.title, *cert.skills, limit=3)
        role_chunk = self.store.search_knowledge("Role-to-Certification", "Primary", limit=1)
        citations = [c.source_id for c in chunks] + [c.source_id for c in role_chunk]

        top = max(cert.exam_domains, key=lambda d: d["weight"])
        module = self.LEARN_MODULES.get(cert.id)
        artifact = self.ARTIFACTS.get(cert.id)

        lines = [
            f"{cert.id} maps to skills: {', '.join(cert.skills)}",
            f"Exam domains (weighted): " + ", ".join(f"{d['name']} {d['weight']:.0%}" for d in cert.exam_domains),
            f"Heaviest domain: {top['name']} ({top['weight']:.0%})"
            + (f" → grounded path: Microsoft Learn “{module}”" if module else ""),
            f"Prerequisites: {', '.join(cert.prerequisites) or 'none'}",
        ]
        if artifact:
            lines.append(f"Competence bar — “{cert.id}-ready” concretely means producing {artifact}")
        for c in chunks:
            snippet = " ".join(c.text.split())[:130]
            lines.append(f"grounded: {c.citation} “{snippet}…”")

        fallback = (f"For {cert.id}, the heaviest domain is {top['name']} ({top['weight']:.0%}) — close it with "
                    f"Microsoft Learn “{module or cert.id + ' learning path'}”. "
                    + (f"Concretely, “ready” means producing {artifact}. " if artifact else "")
                    + f"All grounded in {', '.join(sorted(set(citations)))}.")
        headline = self.voice(
            f"Summarise the grounded path for {cert.id}: name the heaviest exam domain and its %, the Microsoft Learn "
            f"module that closes it, and what 'ready' concretely looks like (the artefact). Cite your sources.",
            "\n".join(lines), fallback)
        return Turn(self.name, self.persona_label, self.color, headline, lines, kind="info",
                    data={"citations": sorted(set(citations)),
                          "cited_chunks": [(c.source_id, c.heading) for c in chunks]})
