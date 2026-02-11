/**
 * KeywordHighlight — 검색 키워드 하이라이트 컴포넌트 (FR-DOC-006)
 *
 * @param {string} text      - 원본 텍스트
 * @param {string} keyword   - 하이라이트할 검색어 (빈 문자열이면 원본 그대로 렌더)
 * @param {string} className - 래퍼 span에 적용할 추가 클래스
 */
export default function KeywordHighlight({ text = '', keyword = '', className = '' }) {
  if (!keyword || !keyword.trim() || !text) {
    return <span className={className}>{text}</span>;
  }

  // 정규식 특수문자 이스케이프
  const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const regex = new RegExp(`(${escaped})`, 'gi');
  const parts = text.split(regex);

  return (
    <span className={className}>
      {parts.map((part, i) =>
        regex.test(part) ? (
          <mark
            key={i}
            className="bg-warning-bg text-warning-dark px-0.5 rounded-sm font-medium"
            style={{ backgroundColor: '#F5EDD0', color: '#8B6914' }}
          >
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </span>
  );
}
