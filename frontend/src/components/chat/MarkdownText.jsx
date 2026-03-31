import ReactMarkdown from 'react-markdown';

// 순수 URL 텍스트를 마크다운 링크로 변환
function autoLinkUrls(text) {
  if (typeof text !== 'string') return text;
  return text.replace(
    /(https?:\/\/[^\s)<>]+)/g,
    (url) => `[${url}](${url})`
  );
}

export default function MarkdownText({ children }) {
  if (!children) return null;

  // 백엔드로부터 넘어온 리터럴 \n 문자열을 실제 줄바꿈 문자로 치환
  let processedText = typeof children === 'string' ? children.replace(/\\n/g, '\n') : children;
  // URL 자동 링크 변환
  processedText = autoLinkUrls(processedText);

  return (
    <ReactMarkdown
      components={{
        p: ({ children }) => <p className="mb-2 last:mb-0 whitespace-pre-wrap">{children}</p>,
        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
        em: ({ children }) => <em className="italic">{children}</em>,
        ul: ({ children }) => <ul className="list-disc pl-5 mb-2 last:mb-0 space-y-0.5">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal pl-5 mb-2 last:mb-0 space-y-0.5">{children}</ol>,
        li: ({ children }) => <li>{children}</li>,
        h1: ({ children }) => <h1 className="text-base font-bold mb-1">{children}</h1>,
        h2: ({ children }) => <h2 className="text-sm font-bold mb-1">{children}</h2>,
        h3: ({ children }) => <h3 className="text-sm font-semibold mb-1">{children}</h3>,
        code: ({ children }) => <code className="bg-neutral-100 text-[0.8125rem] px-1 py-0.5 rounded">{children}</code>,
        pre: ({ children }) => <pre className="bg-neutral-100 rounded-lg p-3 mb-2 last:mb-0 overflow-x-auto text-[0.8125rem]">{children}</pre>,
        a: ({ href, children }) => (
          <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary-600 hover:text-primary-700 underline underline-offset-2">
            {children}
          </a>
        ),
      }}
    >
      {processedText}
    </ReactMarkdown>
  );
}
