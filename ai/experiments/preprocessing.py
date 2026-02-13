"""
전처리 파이프라인 모듈 (실험 6)

4단계 전처리를 각각 on/off 가능한 모듈로 구현.
실서비스에서 사용자 입력을 정규화한 뒤 Intent 분류기에 전달하는 용도.

사용법:
    from ai.experiments.preprocessing import preprocess, PreprocessConfig

    # 전체 전처리
    result = preprocess("회이록 정리해조")

    # 특정 단계만
    config = PreprocessConfig(spell_check=True, chosung_restore=False, slang_normalize=False, clean_text=True)
    result = preprocess("회이록 정리해조", config)
"""

import re
from dataclasses import dataclass


@dataclass
class PreprocessConfig:
    """전처리 단계별 on/off 설정"""
    spell_check: bool = True       # P1: 맞춤법 교정
    chosung_restore: bool = True   # P2: 초성 복원
    slang_normalize: bool = True   # P3: 슬랭/축약어 정규화
    clean_text: bool = True        # P4: 공백/특수문자 정리


# ── P1: 맞춤법 교정 (규칙 기반) ──

SPELL_CORRECTIONS = {
    # 자주 틀리는 업무용 단어
    "회이록": "회의록", "회이": "회의", "회의룩": "회의록",
    "보거서": "보고서", "보고ㅓ서": "보고서", "보고써": "보고서",
    "일졍": "일정", "일젱": "일정", "일정확인": "일정 확인",
    "귝정": "규정", "귶정": "규정", "규졍": "규정",
    "연챠": "연차", "연쨔": "연차",
    "스케쥴": "스케줄",
    "문셔": "문서", "먼서": "문서",
    "셋업": "설정", "미팅잇나": "미팅 있나",
    "잇나": "있나", "잇어": "있어", "잇는": "있는",
    "해조": "해줘", "해줘어": "해줘", "해쥬": "해줘",
    "되나용": "되나요", "되나용?": "되나요?",
    "안녕하세여": "안녕하세요",
    # 붙여쓰기 교정
    "내일미팅": "내일 미팅", "다음주": "다음 주", "이번주": "이번 주",
}


def spell_check(text: str) -> str:
    """규칙 기반 맞춤법 교정"""
    result = text
    # 긴 패턴부터 먼저 매칭 (greedy)
    for wrong, correct in sorted(SPELL_CORRECTIONS.items(), key=lambda x: -len(x[0])):
        result = result.replace(wrong, correct)
    return result


# ── P2: 초성 복원 ──

CHOSUNG_MAP = {
    # 2글자 초성 약어 (업무 관련)
    "ㅎㅇ": "회의",  "ㅎㅇㄹ": "회의록", "ㅂㄱㅅ": "보고서",
    "ㅁㅅ": "문서",  "ㄱㅈ": "규정",    "ㅇㅈ": "일정",
    "ㅎㄹ": "회의록",
    # 1글자 감탄사/리액션은 그대로 둠 (general로 분류되어야 함)
    # "ㅋ", "ㅎ", "ㅠ" 등은 건드리지 않음
}

# 리액션 초성 (복원하지 않음)
REACTION_CHOSUNG = {"ㅋ", "ㅎ", "ㅠ", "ㄷ", "ㅇㅋ", "ㅇㅇ", "ㄴㄴ", "ㅂㅂ",
                    "ㅋㅋ", "ㅎㅎ", "ㅠㅠ", "ㄷㄷ", "ㅇㅈ", "ㄹㅇ", "ㄴㅇㅂ",
                    "ㅋㅋㅋ", "ㅎㅎㅎ", "ㅋㅋㅋㅋ", "ㅎㅎㅎㅎ"}


def chosung_restore(text: str) -> str:
    """초성 약어를 원래 단어로 복원"""
    # 단독 리액션 초성이면 건드리지 않음
    stripped = text.strip()
    if stripped in REACTION_CHOSUNG:
        return text

    result = text
    # 긴 패턴부터 (ㅎㅇㄹ → 회의록 먼저, ㅎㅇ → 회의는 나중에)
    for chosung, word in sorted(CHOSUNG_MAP.items(), key=lambda x: -len(x[0])):
        result = result.replace(chosung, word)
    return result


# ── P3: 슬랭/축약어 정규화 ──

SLANG_MAP = {
    "걍": "그냥", "겜": "게임", "셈": "세요", "해주셈": "해주세요",
    "해줘셈": "해줘요", "해주삼": "해주세요",
    "ㄱㄱ": "하자", "ㄱ": "하자",
    "넹": "네", "넵": "네", "응응": "응",
    "레알": "정말", "리얼": "정말",
    "고고": "하자", "오키": "알겠어", "오케이": "알겠어",
}


def slang_normalize(text: str) -> str:
    """슬랭/축약어를 표준어로 변환"""
    result = text
    for slang, standard in sorted(SLANG_MAP.items(), key=lambda x: -len(x[0])):
        result = result.replace(slang, standard)
    return result


# ── P4: 공백/특수문자 정리 ──

def clean_text(text: str) -> str:
    """불필요한 공백, 반복 특수문자, 이모지 제거"""
    result = text.strip()

    # 반복 문자 축소 (3회 이상 → 1회): ㅋㅋㅋㅋ → ㅋ, 회의이이이 → 회의이
    result = re.sub(r'(.)\1{2,}', r'\1', result)

    # 반복 특수문자 제거: !!!!! → !, ???? → ?
    result = re.sub(r'([!?.]){2,}', r'\1', result)

    # 연속 공백 → 단일 공백
    result = re.sub(r'\s+', ' ', result)

    # 앞뒤 특수문자만 있는 경우 제거하지 않음 (의미 보존)
    result = result.strip()

    return result


# ── 통합 전처리 함수 ──

def preprocess(text: str, config: PreprocessConfig = None) -> str:
    """
    전처리 파이프라인 실행

    순서: P4(공백정리) → P1(맞춤법) → P2(초성복원) → P3(슬랭)
    (기획서 순서와 다르지만, 공백 정리를 먼저 해야 후속 매칭이 정확함)
    """
    if config is None:
        config = PreprocessConfig()

    result = text

    # P4: 공백/특수문자 정리 (가장 먼저 — 후속 매칭 정확도 향상)
    if config.clean_text:
        result = clean_text(result)

    # P1: 맞춤법 교정
    if config.spell_check:
        result = spell_check(result)

    # P2: 초성 복원
    if config.chosung_restore:
        result = chosung_restore(result)

    # P3: 슬랭/축약어 정규화
    if config.slang_normalize:
        result = slang_normalize(result)

    return result


# ── 프리셋 설정 ──

ABLATION_CONFIGS = {
    "A": PreprocessConfig(spell_check=False, chosung_restore=False, slang_normalize=False, clean_text=False),
    "B": PreprocessConfig(spell_check=False, chosung_restore=False, slang_normalize=False, clean_text=True),
    "C": PreprocessConfig(spell_check=True,  chosung_restore=False, slang_normalize=False, clean_text=True),
    "D": PreprocessConfig(spell_check=True,  chosung_restore=True,  slang_normalize=False, clean_text=True),
    "E": PreprocessConfig(spell_check=True,  chosung_restore=True,  slang_normalize=True,  clean_text=True),
}


if __name__ == "__main__":
    # 간단한 테스트
    test_cases = [
        "회이록 정리해조",
        "ㅎㅇㄹ ㅈㄹ해줘",
        "연챠 되나용?",
        "ㅂㄱㅅ 써줘",
        "일졍 추가해줘",
        "보고ㅓ서 작성해줘어",
        "ㅋㅋㅋㅋ",
        "회의이이이 언제야",
        "내일미팅잇나",
        "일정확인 ㄱㄱ",
    ]

    print("=" * 60)
    print("  전처리 파이프라인 테스트")
    print("=" * 60)

    for config_name, config in ABLATION_CONFIGS.items():
        print(f"\n--- Config {config_name} ---")
        print(f"  P1={config.spell_check}, P2={config.chosung_restore}, "
              f"P3={config.slang_normalize}, P4={config.clean_text}")
        for text in test_cases:
            result = preprocess(text, config)
            if result != text:
                print(f"  \"{text}\" → \"{result}\"")
