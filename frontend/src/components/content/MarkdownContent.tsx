import type { ReactNode } from 'react';
import { Link } from 'react-router';

type MarkdownBlock =
  | { type: 'heading'; level: 1 | 2 | 3; text: string }
  | { type: 'paragraph'; text: string }
  | { type: 'list'; items: string[] };

const linkPattern = /\[([^\]]+)\]\(([^)]+)\)/g;

function isSafeHref(href: string) {
  return (
    href.startsWith('/') ||
    href.startsWith('https://') ||
    href.startsWith('http://') ||
    href.startsWith('mailto:')
  );
}

function renderInlineMarkdown(text: string, keyPrefix: string) {
  const nodes: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  linkPattern.lastIndex = 0;
  while ((match = linkPattern.exec(text)) !== null) {
    const [raw, label, href] = match;
    const index = match.index;

    if (index > lastIndex) {
      nodes.push(text.slice(lastIndex, index));
    }

    if (isSafeHref(href)) {
      const className =
        'font-semibold text-brand underline underline-offset-4 hover:text-brand-active';

      nodes.push(
        href.startsWith('/') ? (
          <Link key={`${keyPrefix}-${index}`} to={href} className={className}>
            {label}
          </Link>
        ) : (
          <a
            key={`${keyPrefix}-${index}`}
            href={href}
            className={className}
            target={href.startsWith('http') ? '_blank' : undefined}
            rel={href.startsWith('http') ? 'noopener noreferrer' : undefined}
          >
            {label}
          </a>
        )
      );
    } else {
      nodes.push(label);
    }

    lastIndex = index + raw.length;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes.length > 0 ? nodes : text;
}

function parseMarkdown(markdown: string): MarkdownBlock[] {
  const blocks: MarkdownBlock[] = [];
  const lines = markdown.replace(/\r\n/g, '\n').split('\n');
  let index = 0;

  while (index < lines.length) {
    const line = lines[index].trim();

    if (!line) {
      index += 1;
      continue;
    }

    const heading = /^(#{1,3})\s+(.+)$/.exec(line);
    if (heading) {
      blocks.push({
        type: 'heading',
        level: heading[1].length as 1 | 2 | 3,
        text: heading[2],
      });
      index += 1;
      continue;
    }

    if (line.startsWith('- ')) {
      const items: string[] = [];
      while (index < lines.length && lines[index].trim().startsWith('- ')) {
        items.push(lines[index].trim().slice(2));
        index += 1;
      }
      blocks.push({ type: 'list', items });
      continue;
    }

    const paragraphLines: string[] = [];
    while (
      index < lines.length &&
      lines[index].trim() &&
      !/^(#{1,3})\s+/.test(lines[index].trim()) &&
      !lines[index].trim().startsWith('- ')
    ) {
      paragraphLines.push(lines[index].trim());
      index += 1;
    }
    blocks.push({ type: 'paragraph', text: paragraphLines.join(' ') });
  }

  return blocks;
}

export function MarkdownContent({ markdown }: { markdown: string }) {
  const blocks = parseMarkdown(markdown);

  return (
    <div className="space-y-7">
      {blocks.map((block, index) => {
        if (block.type === 'heading') {
          if (block.level === 1) {
            return (
              <h1
                key={index}
                className="text-4xl sm:text-5xl font-bold text-gray-950"
              >
                {renderInlineMarkdown(block.text, `h-${index}`)}
              </h1>
            );
          }

          const HeadingTag = block.level === 2 ? 'h2' : 'h3';
          return (
            <HeadingTag
              key={index}
              className="text-2xl font-semibold text-gray-950"
            >
              {renderInlineMarkdown(block.text, `h-${index}`)}
            </HeadingTag>
          );
        }

        if (block.type === 'list') {
          return (
            <ul
              key={index}
              className="grid gap-3 text-lg leading-8 text-gray-700 sm:grid-cols-2"
            >
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex} className="flex gap-3">
                  <span
                    className="mt-3 h-2 w-2 rounded-full bg-brand shrink-0"
                    aria-hidden="true"
                  />
                  <span>{renderInlineMarkdown(item, `li-${index}`)}</span>
                </li>
              ))}
            </ul>
          );
        }

        return (
          <p key={index} className="text-lg leading-8 text-gray-700">
            {renderInlineMarkdown(block.text, `p-${index}`)}
          </p>
        );
      })}
    </div>
  );
}
