import React, { useState, useEffect, useRef } from "react";
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { materialOceanic } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { cn } from "@/lib/utils";

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  attachments?: string[];
}

export function ChatMessage({ role, content, attachments }: ChatMessageProps) {
  const [renderedContent, setRenderedContent] = useState(content);
  const contentRef = useRef(content);

  // Debug output
  console.log("ChatMessage rendered:", { role, content, attachments });

  useEffect(() => {
    if (content !== contentRef.current) {
      contentRef.current = content;
      requestAnimationFrame(() => {
        setRenderedContent(content);
      });
    }
  }, [content]);

  return (
    <div className={cn(
      "rounded-lg p-4 min-h-[60px] min-w-[120px] shadow-sm",
      role === "user"
        ? "bg-blue-500 text-white border border-blue-600"
        : "bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700"
    )}>
      <div className="prose dark:prose-invert max-w-none">
        {renderedContent ? (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              h1: ({node, ...props}) => <h1 style={{fontSize: '2em', fontWeight: 'bold', margin: '0.67em 0'}} {...props}/>,
              h2: ({node, ...props}) => <h2 style={{fontSize: '1.5em', fontWeight: 'bold', margin: '0.83em 0'}} {...props}/>,
              h3: ({node, ...props}) => <h3 style={{fontSize: '1.17em', fontWeight: 'bold', margin: '1em 0'}} {...props}/>,
              ul: ({node, ...props}) => <ul style={{listStyle: 'disc', paddingLeft: '2em', margin: '1em 0'}} {...props}/>,
              li: ({node, ...props}) => <li style={{display: 'list-item', margin: '0.5em 0'}} {...props}/>,
              code(props) {
                const {children, className, node, ...rest} = props
                const match = /language-(\w+)/.exec(className || '')
                return match ? (
                  <SyntaxHighlighter
                    language={match[1]}
                    style={materialOceanic}
                    customStyle={{
                      margin: 0,
                      borderRadius: '1rem',
                    }}
                  >
                    {String(children).replace(/\n$/, '')}
                  </SyntaxHighlighter>
                ) : (
                  <code {...rest} className={className}>
                    {children}
                  </code>
                )
              }
            }}
          >
            {renderedContent}
          </ReactMarkdown>
        ) : (
          <p className="text-gray-500 dark:text-gray-400"></p>
        )}
      </div>
      {attachments?.length > 0 && (
        <div className="flex gap-2 mt-2">
          {attachments.map((attachment, index) => (
            <div key={index} className="text-sm text-muted-foreground">
              {attachment}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
