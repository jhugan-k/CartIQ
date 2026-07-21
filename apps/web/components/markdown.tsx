// renders the agent's markdown replies as real formatted content
// (fixes raw **bold** / * bullets showing as plain text).

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function Markdown({ children }: { children: string }) {
  return (
    <div className="text-[14.5px] leading-relaxed [word-break:break-word]">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="my-2 first:mt-0 last:mb-0">{children}</p>,
          strong: ({ children }) => (
            <strong className="font-semibold text-text">{children}</strong>
          ),
          em: ({ children }) => <em className="italic">{children}</em>,
          h1: ({ children }) => <h1 className="mt-3 mb-2 text-base font-semibold">{children}</h1>,
          h2: ({ children }) => <h2 className="mt-3 mb-2 text-[15px] font-semibold">{children}</h2>,
          h3: ({ children }) => <h3 className="mt-3 mb-1.5 text-sm font-semibold">{children}</h3>,
          ul: ({ children }) => (
            <ul className="my-2 flex flex-col gap-1.5 pl-1">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="my-2 flex list-decimal flex-col gap-1.5 pl-5">{children}</ol>
          ),
          li: ({ children }) => (
            <li className="flex gap-2 [&>ol]:mt-1.5 [&>ul]:mt-1.5">
              <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-primary/70" />
              <span className="flex-1">{children}</span>
            </li>
          ),
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-primary underline underline-offset-2 hover:opacity-80"
            >
              {children}
            </a>
          ),
          code: ({ children }) => (
            <code className="rounded bg-black/5 px-1 py-0.5 font-mono text-[13px] dark:bg-white/10">
              {children}
            </code>
          ),
          hr: () => <hr className="my-3 border-border" />,
          table: ({ children }) => (
            <div className="my-2 overflow-x-auto">
              <table className="w-full border-collapse text-[13.5px]">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border-b border-border px-2.5 py-1.5 text-left font-semibold">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border-b border-border/60 px-2.5 py-1.5">{children}</td>
          ),
          blockquote: ({ children }) => (
            <blockquote className="my-2 border-l-2 border-primary/50 pl-3 text-muted">
              {children}
            </blockquote>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
