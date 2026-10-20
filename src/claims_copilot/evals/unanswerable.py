"""The 20 unanswerable questions (Phase 7): topics the verified corpus does not cover.

"Does not cover" is checked, not assumed: every question lists `absent_terms`, words that name the
topic, and a test requires that none of them occurs in any of the 1,913 chunks. Absence of a word
does not prove absence of the idea (a synonym could carry it), so this is a floor; the limit is
recorded as KF-035. Fourteen questions are in domains far from the corpus; six are near misses,
where related vocabulary is present (dental, surgery, counselling) but the specific rule asked
about is not. Near misses are the harder test for a retriever that always returns something.
"""

from __future__ import annotations

from claims_copilot.agent.answer import Status
from claims_copilot.evals.schema import EvalCase, Layer
from claims_copilot.project import REPO_ROOT

CASES_PATH = REPO_ROOT / "eval" / "phase7_unanswerable.jsonl"

# (id, question, absent terms, near miss?)
_SPEC: tuple[tuple[str, str, tuple[str, ...], bool], ...] = (
    ("un-01", "What do the policy sources say about helicopter transport authorization?",
     ("helicopter",), False),
    ("un-02", "What do the policy sources require for step therapy before a GLP-1 drug is covered?",
     ("step therapy", "glp-1", "semaglutide"), False),
    ("un-03", "What quantitative treatment limits may apply to behavioral health benefits "
     "under MHPAEA?", ("mhpaea",), False),
    ("un-04", "What do the policy sources say about marketplace risk adjustment and HCC scores?",
     ("marketplace", "risk adjustment"), False),
    ("un-05", "What is the allowance for eyeglass frames, and when is LASIK covered?",
     ("eyeglass", "lasik"), False),
    ("un-06", "How does the independent dispute resolution process under the No Surprises "
     "rules work?", ("surprise", "independent dispute"), False),
    ("un-07", "What limits apply to balance billing of a member by an out-of-network provider?",
     ("balance bill",), False),
    ("un-08", "How does a member request an exception to a formulary tier?",
     ("formulary",), False),
    ("un-09", "How many acupuncture visits per year does the policy allow?",
     ("acupuncture",), False),
    ("un-10", "What BMI criteria must be met before bariatric surgery is covered?",
     ("bariatric",), False),
    ("un-11", "Do the sources cover in vitro fertilization cycles?", ("in vitro",), False),
    ("un-12", "How does a plan pursue subrogation recovery after an accident?",
     ("subrogation",), False),
    ("un-13", "What time and distance standards define network adequacy?",
     ("network adequacy",), False),
    ("un-14", "How often must a provider go through credentialing again?",
     ("credentialing",), False),
    ("un-15", "How often can a dental crown be replaced under the policy?", ("crown",), True),
    ("un-16", "Is a supervised weight loss program a covered service?", ("weight loss",), True),
    ("un-17", "What criteria must be met before genetic testing is covered?",
     ("genetic test",), True),
    ("un-18", "What do the policy sources say about proton beam therapy?", ("proton",), True),
    ("un-19", "Is there an added payment for robotic-assisted surgery?", ("robotic",), True),
    ("un-20", "How many smoking cessation counseling visits are allowed per year?",
     ("smoking cessation",), True),
)  # fmt: skip


def unanswerable_cases() -> list[EvalCase]:
    return [
        EvalCase(
            case_id=cid,
            layer=Layer.UNANSWERABLE,
            question=question,
            expected_statuses=(Status.INSUFFICIENT_EVIDENCE,),
            absent_terms=terms,
            note="near miss: related vocabulary is in the corpus" if near else "far from corpus",
        )
        for cid, question, terms, near in _SPEC
    ]


def main() -> int:
    from claims_copilot.evals.casefile import write_cases

    write_cases(CASES_PATH, unanswerable_cases())
    print(f"wrote {CASES_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
