import ReactMarkdown from 'react-markdown';

export default function MarkdownText({ children }) {
  if (!children) return null;
  return (
    <ReactMarkdown
      components={{
        p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
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
      }}
    >
      {children}
    </ReactMarkdown>
  );
}
