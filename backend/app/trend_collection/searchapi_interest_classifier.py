"""Pure interest classification; no network, database or publication authority."""

from dataclasses import dataclass
from unicodedata import normalize

from app.trend_collection.searchapi_discovery import TrendingLead

VERSION = "interest-rules-1"
RULES = {
    ("FASHION", "의류"): "재킷 자켓 코트 셔츠 니트 원피스 패딩 스웨터",
    ("FASHION", "신발"): "운동화 러닝화 스니커즈 부츠",
    ("FASHION", "가방"): "백팩 숄더백 토트백 가방",
    ("FASHION", "주얼리·액세서리"): "목걸이 귀걸이 팔찌 주얼리",
    ("FASHION", "패션 스타일"): "코디 레이어드룩 패션스타일",
    ("FASHION", "기타"): "패션 소품 패션소품",
    ("BEAUTY", "스킨케어"): "선크림 토너 세럼 수분크림",
    ("BEAUTY", "메이크업"): "립스틱 립틴트 파운데이션 블러셔",
    ("BEAUTY", "헤어"): "헤어스타일 샴푸 헤어케어",
    ("BEAUTY", "향수"): "향수 오드퍼퓸",
    ("BEAUTY", "네일"): "네일아트 젤네일 매니큐어",
    ("BEAUTY", "기타"): "뷰티 화장품",
    ("FOOD", "한식"): "비빔밥 김치찌개 떡볶이",
    ("FOOD", "중식"): "마라탕 짜장면 짬뽕",
    ("FOOD", "일식"): "초밥 라멘 돈카츠",
    ("FOOD", "양식"): "파스타 스테이크 리조또",
    ("FOOD", "카페·디저트"): "커피 케이크 쿠키 디저트",
    ("FOOD", "식품·음료"): "과자 라면 음료 간편식 초콜릿",
    ("FOOD", "기타"): "음식 식품",
    ("ENTERTAINMENT", "음악"): "신곡 앨범 음반 콘서트",
    ("ENTERTAINMENT", "영화"): "영화",
    ("ENTERTAINMENT", "드라마"): "드라마",
    ("ENTERTAINMENT", "예능"): "예능",
    ("ENTERTAINMENT", "웹툰·애니메이션"): "웹툰 애니메이션",
    ("ENTERTAINMENT", "기타"): "콘텐츠",
}
ROOTS = frozenset(root for root, _ in RULES)
MODIFIERS = frozenset(
    "신제품 신작 신규 추천 출시 공개 개봉 발표 인기 신상 겨울 여름 봄 가을 "
    "스웨이드 니치 두바이 브랜드 협업 스타일 프로그램 새 극장".split()
)
BLOCKED = frozenset(
    "사생활 논란 사건 사고 사망 범죄 정치 질병 치료 폭로 열애 이혼 성인".split()
)
CATALOG_PAIRS = frozenset(RULES) | {("ENTERTAINMENT", "연예인·스타")}


@dataclass(frozen=True, slots=True)
class ClassificationDecision:
    parent_code: str | None
    child_name: str | None
    method: str
    reason_code: str
    rule_ids: tuple[str, ...] = ()

    @property
    def eligible(self) -> bool:
        return self.parent_code is not None and self.child_name is not None


def _reject(reason: str) -> ClassificationDecision:
    return ClassificationDecision(None, None, "REJECTED", reason)


def classify(
    lead: TrendingLead, topics: dict[str, tuple[str, str]],
) -> ClassificationDecision:
    hints = lead.possible_root_codes
    if not hints or not hints <= ROOTS:
        return _reject("OUT_OF_SCOPE")
    query = normalize("NFC", lead.query)
    if any(term in query for term in BLOCKED):
        return _reject("TOPIC_ELIGIBILITY_UNCONFIRMED")
    if lead.query in topics:
        pair = topics[lead.query]
        if pair not in CATALOG_PAIRS or pair[0] not in hints:
            return _reject("CATEGORY_CONFLICT")
        return ClassificationDecision(*pair, "CATALOG_EXACT", "ELIGIBLE")

    # Whole words and explicit context, not arbitrary substring matches.
    words = set(query.split())
    vocabulary = set().union(*(set(value.split()) for value in RULES.values()))
    if not words or not words <= vocabulary | MODIFIERS:
        return _reject("NO_MATCHING_RULE")
    matches = {
        pair for pair, value in RULES.items()
        if words.intersection(value.split())
    }
    if not matches:
        return _reject("NO_MATCHING_RULE")
    specific = {pair for pair in matches if pair[1] != "기타"}
    candidates = specific or matches
    # An explicit film context disambiguates the homonym.
    if words == {"영화", "향수"} and "ENTERTAINMENT" in hints:
        candidates = {("ENTERTAINMENT", "영화")}
    roots = {root for root, _ in candidates}
    if len(roots) != 1:
        return _reject("AMBIGUOUS_ROOT")
    root = next(iter(roots))
    if root not in hints:
        return _reject("CATEGORY_CONFLICT")
    ids = tuple(sorted(f"{parent}:{child}" for parent, child in matches))
    children = {child for _, child in candidates}
    if len(children) != 1 or children == {"기타"}:
        return ClassificationDecision(root, "기타", "ROOT_OTHER", "ELIGIBLE", ids)
    child = next(iter(children))
    method = "RULE_RESOLVED" if len(matches) > 1 else "RULE_EXACT"
    return ClassificationDecision(root, child, method, "ELIGIBLE", ids)
