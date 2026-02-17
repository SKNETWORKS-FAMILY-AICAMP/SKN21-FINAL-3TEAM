"""
3단계 E2E 테스트: RAG → judgment_agent → 오케스트레이터

테스트 항목:
  1. Qdrant 연결 + 데이터 확인
  2. 데이터 없으면 규정 PDF 적재 (메타데이터 검증 포함)
  3. RAG 검색 테스트 (하이브리드 검색)
  4. judgment_agent 단독 테스트 (실 규정 기반)
  5. 오케스트레이터 judgment 라우팅 테스트
  6. 오케스트레이터 general 라우팅 테스트 (backend 분리)

실행:
  cd 프로젝트루트
  python -m ai.tests.test_e2e_judgment                       # 기본 (fail-fast, 60s 타임아웃)
  python -m ai.tests.test_e2e_judgment --continue-on-failure  # 실패해도 계속
  python -m ai.tests.test_e2e_judgment --force-ingest         # 강제 재적재
  python -m ai.tests.test_e2e_judgment --timeout 120          # 타임아웃 변경
"""
import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# Windows cp949 인코딩 문제 방지
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── CLI 옵션 ──

parser = argparse.ArgumentParser(description="3단계 E2E 테스트")
parser.add_argument(
    "--continue-on-failure", action="store_true",
    help="실패해도 다음 Step 계속 실행 (기본: fail-fast)",
)
parser.add_argument(
    "--force-ingest", action="store_true",
    help="기존 데이터 무시하고 강제 재적재",
)
parser.add_argument(
    "--timeout", type=int, default=60,
    help="각 Step 타임아웃(초) (기본: 60)",
)
args = parser.parse_args()

STEP_TIMEOUT = args.timeout


# ── 출력 헬퍼 ──

def ok(msg):
    print(f"  [PASS] {msg}")

def fail(msg):
    print(f"  [FAIL] {msg}")

def warn(msg):
    print(f"  [WARN] {msg}")

def info(msg):
    print(f"  [INFO] {msg}")

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ── Step 1: Qdrant 연결 + 데이터 확인 ──

def test_qdrant_connection():
    section("Step 1: Qdrant 연결 + 데이터 확인")

    from qdrant_client import QdrantClient

    url = os.getenv("QDRANT_URL")
    api_key = os.getenv("QDRANT_API_KEY")

    if not url or not api_key:
        fail("QDRANT_URL 또는 QDRANT_API_KEY가 .env에 없습니다")
        return -1

    try:
        client = QdrantClient(url=url, api_key=api_key)
        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]
        ok(f"Qdrant 연결 성공 | 컬렉션: {collection_names}")

        doc_count = 0
        if "documents" in collection_names:
            collection_info = client.get_collection("documents")
            doc_count = collection_info.points_count
            ok(f"documents 컬렉션: {doc_count}개 문서")
        else:
            info("documents 컬렉션이 없습니다 (Step 2에서 생성)")

        return doc_count

    except Exception as e:
        fail(f"Qdrant 연결 실패: {e}")
        return -1


# ── Step 2 보조: 기존 데이터 메타데이터 검증 ──

def validate_existing_data():
    """Qdrant 기존 데이터의 source 메타데이터가 규정 데이터인지 검증

    Returns:
        (valid: bool, detail: str)
    """
    from qdrant_client import QdrantClient

    url = os.getenv("QDRANT_URL")
    api_key = os.getenv("QDRANT_API_KEY")

    client = QdrantClient(url=url, api_key=api_key)

    points, _ = client.scroll(
        collection_name="documents",
        limit=10,
        with_payload=True,
    )

    if not points:
        return False, "데이터가 비어있습니다"

    matched = 0
    for point in points:
        payload = point.payload or {}
        source = payload.get("source", "")
        scope = payload.get("scope", "")
        if "dudu_tech" in source or re.match(r"제\s*\d+\s*[조장절]", source) or scope == "company":
            matched += 1

    ratio = matched / len(points)
    if ratio >= 0.5:
        return True, f"메타데이터 검증 통과 ({matched}/{len(points)} 일치)"
    else:
        return False, f"메타데이터 불일치 ({matched}/{len(points)}) — 예상 source가 아닙니다"


# ── Step 2: 규정 PDF → Qdrant 적재 ──

def _clear_collection():
    """기존 컬렉션 삭제 후 재생성 (force-ingest 용)"""
    from qdrant_client import QdrantClient

    url = os.getenv("QDRANT_URL")
    api_key = os.getenv("QDRANT_API_KEY")
    client = QdrantClient(url=url, api_key=api_key)

    try:
        client.delete_collection("documents")
        info("기존 documents 컬렉션 삭제 완료")
    except Exception:
        info("documents 컬렉션이 없거나 삭제 실패 (무시)")


def _chunk_by_articles(full_text: str) -> tuple[list[str], list[dict]]:
    """조항(제N조) 단위 세밀한 청킹

    전략:
      1. 표지/목차(제N장·제N조 목록만 있는 페이지) 스킵
      2. 장(제N장) 헤더 → 현재 chapter 추적
      3. 조(제N조) 헤더 → 새 청크 시작
      4. 장 본문(조 시작 전 설명문) → 별도 청크
      5. 긴 조항(>400자) → ● 불릿 기준 서브 분할
    """
    lines = full_text.split("\n")

    # 파싱용 정규식
    RE_CHAPTER = re.compile(r"^(제\s*\d+\s*장)\s*(.*)")
    RE_ARTICLE = re.compile(r"^(제\s*\d+\s*조(?:의\d+)?)\s*(?:\(([^)]+)\))?\s*(.*)")
    RE_APPENDIX = re.compile(r"^(부\s*칙|별\s*표|부록)")
    RE_TOC_LINE = re.compile(r"^제\s*\d+\s*[조장절]\s")  # 목차 줄 패턴

    chunks = []
    chunk_metas = []

    current_chapter = ""
    current_article = ""
    current_article_title = ""
    current_lines = []
    in_toc = False

    def _flush():
        """현재 누적된 lines를 청크로 저장"""
        nonlocal current_lines
        if not current_lines:
            return

        text = "\n".join(current_lines).strip()
        # 30자 미만이거나 목차성 텍스트(조 이름만 나열)면 스킵
        if len(text) < 30:
            current_lines = []
            return

        # 목차 감지: 대부분의 줄이 "제N조/장" 패턴이면 스킵
        non_empty = [l for l in current_lines if l.strip()]
        if non_empty:
            toc_ratio = sum(1 for l in non_empty if RE_TOC_LINE.match(l.strip())) / len(non_empty)
            if toc_ratio > 0.5 and len(non_empty) > 3:
                info(f"  목차 스킵: {non_empty[0][:30]}... ({len(non_empty)}줄)")
                current_lines = []
                return

        source = current_article or current_chapter or "dudu_tech_regulations"
        title = current_article_title or current_chapter or "사내규정"

        # 긴 청크는 ● 불릿 기준으로 서브 분할
        if len(text) > 400:
            sub_chunks = _split_by_bullets(text)
            for idx, sub in enumerate(sub_chunks):
                if len(sub.strip()) < 20:
                    continue
                sub_source = f"{source} ({idx+1}/{len(sub_chunks)})" if len(sub_chunks) > 1 else source
                chunks.append(sub.strip())
                chunk_metas.append({
                    "source": sub_source,
                    "scope": "company",
                    "title": title,
                    "chapter": current_chapter,
                    "article": current_article,
                })
        else:
            chunks.append(text)
            chunk_metas.append({
                "source": source,
                "scope": "company",
                "title": title,
                "chapter": current_chapter,
                "article": current_article,
            })

        current_lines = []

    def _split_by_bullets(text: str) -> list[str]:
        """● 불릿 기준으로 분할, 각 서브청크 200~400자 목표"""
        # ● 또는 ①②③ 기준 분할
        parts = re.split(r"(?=●)", text)
        if len(parts) <= 1:
            # ● 가 없으면 문장 기준 분할
            parts = re.split(r"(?<=다\.)\s*\n|(?<=한다\.)\s*\n|(?<=된다\.)\s*\n", text)

        result = []
        current = ""
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if len(current) + len(part) > 400 and current:
                result.append(current)
                current = part
            else:
                current = current + "\n" + part if current else part

        if current.strip():
            result.append(current)

        return result if result else [text]

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # 표지 감지 (첫 페이지)
        if "듀듀 테크놀로지" in stripped or "Duedue Technology" in stripped:
            in_toc = True
            continue
        if in_toc and ("목 차" in stripped or "목차" in stripped):
            continue

        # 부록/부칙
        if RE_APPENDIX.match(stripped):
            _flush()
            current_article = stripped[:20]
            current_article_title = stripped[:20]
            current_lines = [stripped]
            continue

        # 장 헤더
        m_ch = RE_CHAPTER.match(stripped)
        if m_ch:
            _flush()
            current_chapter = f"{m_ch.group(1)} {m_ch.group(2)}".strip()
            in_toc = False
            # 장 헤더 뒤에 설명문이 올 수 있으므로 새 청크 시작
            current_lines = [stripped]
            current_article = ""
            current_article_title = ""
            continue

        # 조 헤더
        m_art = RE_ARTICLE.match(stripped)
        if m_art:
            _flush()
            current_article = m_art.group(1)
            current_article_title = m_art.group(2) or ""
            in_toc = False
            current_lines = [stripped]
            continue

        # 일반 라인
        current_lines.append(stripped)

    _flush()

    return chunks, chunk_metas


def ingest_regulations():
    section("Step 2: 규정 PDF → Qdrant 적재")

    pdf_path = ROOT / "data" / "regulations" / "dudu_tech_regulations.pdf"
    if not pdf_path.exists():
        fail(f"규정 PDF 없음: {pdf_path}")
        return False

    # 0. force-ingest면 기존 컬렉션 삭제
    if args.force_ingest:
        _clear_collection()

    # 1. PDF 텍스트 추출
    info("PDF 텍스트 추출 중...")
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(pdf_path))
        full_text = ""
        for page in doc:
            full_text += page.get_text()
        page_count = doc.page_count
        doc.close()
        ok(f"PDF 추출 완료: {len(full_text)}자, {page_count}페이지")
    except Exception as e:
        fail(f"PDF 추출 실패: {e}")
        return False

    # 2. 조항 기반 세밀한 청킹
    info("조항 기반 세밀한 청킹 중...")
    final_chunks, final_metas = _chunk_by_articles(full_text)

    ok(f"청킹 완료: {len(final_chunks)}개 청크")
    # 청크 통계
    lengths = [len(c) for c in final_chunks]
    info(f"청크 길이: 평균={sum(lengths)/len(lengths):.0f}자, "
         f"최소={min(lengths)}자, 최대={max(lengths)}자")
    articles = set(m.get("article", "") for m in final_metas if m.get("article"))
    chapters = set(m.get("chapter", "") for m in final_metas if m.get("chapter"))
    info(f"장: {len(chapters)}개, 조: {len(articles)}개")

    # 3. Qdrant에 적재
    info("Qdrant에 적재 중 (임베딩 생성 포함)...")
    try:
        from ai.rag.qdrant_pipeline import get_qdrant_pipeline, reset_qdrant_pipeline

        # force-ingest로 컬렉션을 삭제했으면 싱글턴 리셋
        if args.force_ingest:
            reset_qdrant_pipeline()

        pipeline = get_qdrant_pipeline()
        pipeline.add_documents(
            documents=final_chunks,
            metadatas=final_metas,
            batch_size=50,
        )
        ok(f"Qdrant 적재 완료: {len(final_chunks)}개 문서")
        return True
    except Exception as e:
        fail(f"Qdrant 적재 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


# ── Step 3: RAG 검색 테스트 ──

def test_rag_search():
    section("Step 3: RAG 하이브리드 검색 테스트")

    from ai.rag.qdrant_pipeline import get_qdrant_pipeline

    pipeline = get_qdrant_pipeline()

    test_queries = [
        "연차 휴가는 며칠인가요?",
        "재택근무 규정이 있나요?",
        "보안 규정 위반 시 처벌은?",
        "출장비 지급 기준",
        "개인정보 처리 규정",
    ]

    passed = 0
    for query in test_queries:
        t = time.time()
        results = pipeline.retrieve(query=query, user_id=None, top_k=5)
        elapsed = time.time() - t

        if results:
            top = results[0]
            ok(f"'{query}' → {len(results)}건 ({elapsed:.2f}s) | Top: {top['source'][:40]} (score={top['score']:.4f})")
            passed += 1
        else:
            fail(f"'{query}' → 검색 결과 없음 ({elapsed:.2f}s)")

    print(f"\n  RAG 검색 결과: {passed}/{len(test_queries)} 통과")
    return passed == len(test_queries)


# ── Step 4: judgment_agent 단독 테스트 ──

VALID_RESULTS = ("yes", "no", "conditional", "no_regulation")

async def test_judgment_agent():
    section("Step 4: judgment_agent 단독 테스트 (실 규정 기반)")

    from ai.agents.judgment_agent import judgment_agent
    from ai.agents.state import AgentState

    test_cases = [
        {
            "name": "규정 판단 - 연차 사용",
            "input": "입사 1년 미만인 직원이 연차 휴가를 사용할 수 있나요?",
            "expected_result": "conditional",
        },
        {
            "name": "규정 판단 - 재택근무",
            "input": "재택근무 시 근태는 어떻게 관리되나요?",
            "expected_result": None,  # 정보성 질문, 특정 결과 기대하지 않음
        },
        {
            "name": "규정 판단 - 보안 위반",
            "input": "회사 자료를 개인 USB에 복사해도 되나요?",
            "expected_result": "no",
        },
    ]

    passed = 0
    for tc in test_cases:
        info(f"테스트: {tc['name']}")

        state: AgentState = {
            "user_input": tc["input"],
            "user_id": 1,
            "intent": "judgment",
            "confidence": 0.95,
            "context": [],
            "agent_response": {},
            "chat_history": [],
            "error": None,
            "template_id": None,
            "source_page": None,
            "template_fields": None,
            "extracted_text": None,
            "google_services_result": None,
            "stream_mode": False,
        }

        t = time.time()
        try:
            result = await judgment_agent(state)
            elapsed = time.time() - t

            resp = result.get("agent_response", {})
            result_val = resp.get("result", "?")
            confidence = resp.get("confidence", 0)
            reasoning = resp.get("reasoning", "")[:80]
            regs = resp.get("regulations", [])
            groups = resp.get("regulation_groups", [])

            if resp.get("type") == "judgment" and result_val in VALID_RESULTS:
                ok(f"result={result_val}, confidence={confidence:.3f}, regs={len(regs)}개, groups={groups}")
                ok(f"reasoning: {reasoning}...")
                if result.get("context"):
                    ok(f"RAG context: {len(result['context'])}개 문서 검색됨")

                # expected_result 검증 (WARN only — LLM 비결정성 허용)
                expected = tc.get("expected_result")
                if expected and result_val != expected:
                    warn(f"기대 result={expected}, 실제={result_val} (LLM 비결정성으로 인한 차이)")

                passed += 1
            else:
                fail(f"응답 형식 오류: type={resp.get('type')}, result={result_val}")

            info(f"소요시간: {elapsed:.2f}s")

        except Exception as e:
            fail(f"에러: {e}")
            import traceback
            traceback.print_exc()

        print()

    print(f"  judgment_agent 결과: {passed}/{len(test_cases)} 통과")
    return passed == len(test_cases)


# ── Step 5: 오케스트레이터 judgment 라우팅 테스트 ──

async def test_orchestrator_judgment():
    section("Step 5: 오케스트레이터 judgment 라우팅 테스트")

    from ai.agents.orchestrator import get_graph
    from ai.agents.state import AgentState

    state: AgentState = {
        "user_input": "회사 보안 규정상 외부 클라우드 서비스를 사용해도 되나요?",
        "user_id": 1,
        "intent": "",
        "confidence": 0.0,
        "context": [],
        "agent_response": {},
        "chat_history": [],
        "error": None,
        "template_id": None,
        "source_page": None,
        "template_fields": None,
        "extracted_text": None,
        "google_services_result": None,
        "stream_mode": False,
    }

    graph = get_graph()
    t = time.time()

    try:
        result = await graph.ainvoke(state)
        elapsed = time.time() - t

        intent = result.get("intent", "?")
        confidence = result.get("confidence", 0)
        resp = result.get("agent_response", {})
        resp_type = resp.get("type", "?")

        info(f"intent={intent} (confidence={confidence:.4f}) → type={resp_type}")
        info(f"소요시간: {elapsed:.2f}s")

        if resp_type == "judgment":
            result_val = resp.get("result")
            j_confidence = resp.get("confidence")
            regs = resp.get("regulations", [])
            ok(f"judgment 라우팅 정확 | result={result_val}, confidence={j_confidence}, regs={len(regs)}개")
            return True
        else:
            fail(f"라우팅 불일치: expected=judgment, got={resp_type}")
            return False

    except Exception as e:
        fail(f"에러: {e}")
        import traceback
        traceback.print_exc()
        return False


# ── Step 6: 오케스트레이터 general 라우팅 테스트 (backend 분리) ──

async def test_orchestrator_general():
    section("Step 6: 오케스트레이터 general 라우팅 테스트 (backend 분리)")

    from ai.agents.orchestrator import get_graph
    from ai.agents.state import AgentState

    # stream_mode=True → general_response_node가 backend LLM 호출 없이 즉시 반환
    state: AgentState = {
        "user_input": "안녕하세요 반갑습니다",
        "user_id": 1,
        "intent": "",
        "confidence": 0.0,
        "context": [],
        "agent_response": {},
        "chat_history": [],
        "error": None,
        "template_id": None,
        "source_page": None,
        "template_fields": None,
        "extracted_text": None,
        "google_services_result": None,
        "stream_mode": True,  # backend LLM 호출 스킵
    }

    graph = get_graph()
    t = time.time()

    try:
        result = await graph.ainvoke(state)
        elapsed = time.time() - t

        intent = result.get("intent", "?")
        confidence = result.get("confidence", 0)
        resp = result.get("agent_response", {})
        resp_type = resp.get("type", "?")

        info(f"intent={intent} (confidence={confidence:.4f}) → type={resp_type}")
        info(f"소요시간: {elapsed:.2f}s")
        info("stream_mode=True: backend LLM 호출 없이 라우팅만 검증")

        if resp_type == "general":
            ok("general 라우팅 정확")
            return True
        else:
            fail(f"라우팅 불일치: expected=general, got={resp_type}")
            return False

    except Exception as e:
        fail(f"에러: {e}")
        import traceback
        traceback.print_exc()
        return False


# ── 결과 요약 ──

def _print_summary(results):
    section("최종 결과")
    all_pass = True
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  [{status}] {name}")

    print()
    if all_pass:
        print("  >>> 3단계 E2E 테스트 전체 통과!")
    else:
        failed = [n for n, p in results.items() if not p]
        print(f"  >>> 실패한 Step: {', '.join(failed)}")
    print()


# ── 메인 ──

async def main():
    print("\n" + "=" * 60)
    print("  3단계 E2E 테스트: RAG → judgment_agent → 오케스트레이터")
    print("=" * 60)

    mode = "fail-late (--continue-on-failure)" if args.continue_on_failure else "fail-fast"
    opts = f"모드: {mode} | 타임아웃: {STEP_TIMEOUT}초"
    if args.force_ingest:
        opts += " | --force-ingest"
    info(opts)

    results = {}
    fail_fast = not args.continue_on_failure

    # ── Step 1: Qdrant 연결 ──
    try:
        doc_count = await asyncio.wait_for(
            asyncio.to_thread(test_qdrant_connection),
            timeout=STEP_TIMEOUT,
        )
    except asyncio.TimeoutError:
        fail(f"Step 1 타임아웃 ({STEP_TIMEOUT}초 초과)")
        doc_count = -1

    results["qdrant_connection"] = doc_count >= 0

    if fail_fast and not results["qdrant_connection"]:
        info("fail-fast: Qdrant 연결 실패로 이후 Step 스킵")
        _print_summary(results)
        return

    # ── Step 2: 데이터 적재 ──
    if doc_count < 0:
        fail("Qdrant 연결 실패로 적재 스킵")
        results["data_ingestion"] = False
    elif args.force_ingest:
        info("--force-ingest: 기존 데이터 무시하고 강제 재적재")
        try:
            results["data_ingestion"] = await asyncio.wait_for(
                asyncio.to_thread(ingest_regulations),
                timeout=STEP_TIMEOUT,
            )
        except asyncio.TimeoutError:
            fail(f"Step 2 타임아웃 ({STEP_TIMEOUT}초 초과)")
            results["data_ingestion"] = False
    elif doc_count == 0:
        try:
            results["data_ingestion"] = await asyncio.wait_for(
                asyncio.to_thread(ingest_regulations),
                timeout=STEP_TIMEOUT,
            )
        except asyncio.TimeoutError:
            fail(f"Step 2 타임아웃 ({STEP_TIMEOUT}초 초과)")
            results["data_ingestion"] = False
    else:
        # doc_count > 0: 메타데이터 검증
        info(f"이미 {doc_count}개 문서 적재됨. 메타데이터 검증 중...")
        try:
            valid, detail = await asyncio.wait_for(
                asyncio.to_thread(validate_existing_data),
                timeout=STEP_TIMEOUT,
            )
            if valid:
                ok(detail)
                info("적재 스킵 (--force-ingest로 강제 재적재 가능)")
                results["data_ingestion"] = True
            else:
                warn(detail)
                warn("기존 데이터가 예상과 다릅니다. --force-ingest로 재적재하세요")
                results["data_ingestion"] = False
        except asyncio.TimeoutError:
            fail(f"메타데이터 검증 타임아웃 ({STEP_TIMEOUT}초 초과)")
            results["data_ingestion"] = False

    if fail_fast and not results["data_ingestion"]:
        info("fail-fast: 데이터 적재 실패로 이후 Step 스킵")
        _print_summary(results)
        return

    # ── Step 3: RAG 검색 ──
    try:
        results["rag_search"] = await asyncio.wait_for(
            asyncio.to_thread(test_rag_search),
            timeout=STEP_TIMEOUT,
        )
    except asyncio.TimeoutError:
        fail(f"Step 3 타임아웃 ({STEP_TIMEOUT}초 초과)")
        results["rag_search"] = False

    if fail_fast and not results["rag_search"]:
        info("fail-fast: RAG 검색 실패로 이후 Step 스킵")
        _print_summary(results)
        return

    # ── Step 4: judgment_agent ──
    try:
        results["judgment_agent"] = await asyncio.wait_for(
            test_judgment_agent(),
            timeout=STEP_TIMEOUT,
        )
    except asyncio.TimeoutError:
        fail(f"Step 4 타임아웃 ({STEP_TIMEOUT}초 초과)")
        results["judgment_agent"] = False

    if fail_fast and not results["judgment_agent"]:
        info("fail-fast: judgment_agent 실패로 이후 Step 스킵")
        _print_summary(results)
        return

    # ── Step 5: 오케스트레이터 judgment 라우팅 ──
    try:
        results["orchestrator_judgment"] = await asyncio.wait_for(
            test_orchestrator_judgment(),
            timeout=STEP_TIMEOUT,
        )
    except asyncio.TimeoutError:
        fail(f"Step 5 타임아웃 ({STEP_TIMEOUT}초 초과)")
        results["orchestrator_judgment"] = False

    if fail_fast and not results["orchestrator_judgment"]:
        info("fail-fast: 오케스트레이터 judgment 실패로 이후 Step 스킵")
        _print_summary(results)
        return

    # ── Step 6: 오케스트레이터 general 라우팅 (backend 분리) ──
    try:
        results["orchestrator_general"] = await asyncio.wait_for(
            test_orchestrator_general(),
            timeout=STEP_TIMEOUT,
        )
    except asyncio.TimeoutError:
        fail(f"Step 6 타임아웃 ({STEP_TIMEOUT}초 초과)")
        results["orchestrator_general"] = False

    _print_summary(results)


if __name__ == "__main__":
    asyncio.run(main())
