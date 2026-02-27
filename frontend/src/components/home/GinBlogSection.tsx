import { useMemo, useState } from 'react';
import { ArrowRight } from 'lucide-react';
import type { HomeBlogPost } from '../../types/api';

interface GinBlogSectionProps {
  posts: HomeBlogPost[];
  loading: boolean;
  error: string | null;
  title: string;
  subtitle?: string;
  ctaLabel: string;
  ctaUrl: string;
}

function formatPublishedDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '';
  return parsed.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function BlogImage({ post, featured }: { post: HomeBlogPost; featured: boolean }) {
  const [failed, setFailed] = useState(false);
  const hasImage = !!post.image_url && !failed;
  return (
    <div
      className={`relative overflow-hidden ${
        featured ? 'aspect-[16/9] lg:aspect-[3/2]' : 'aspect-[16/9]'
      }`}
    >
      {hasImage ? (
        <img
          src={post.image_url ?? ''}
          alt={post.image_alt || post.title}
          className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
          loading="lazy"
          onError={() => setFailed(true)}
        />
      ) : (
        <div className="h-full w-full bg-gradient-to-br from-brand-primary/15 via-slate-100 to-slate-200" />
      )}
    </div>
  );
}

function BlogCard({
  post,
  featured = false,
}: {
  post: HomeBlogPost;
  featured?: boolean;
}) {
  const published = formatPublishedDate(post.published_at);
  const categoryLabel =
    post.category === 'update' ? 'Program Update' : 'Collection Highlight';

  return (
    <a
      href={post.url}
      target="_blank"
      rel="noopener noreferrer"
      className="group block overflow-hidden border border-slate-700/60 bg-slate-900 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-brand-active/60 hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-active focus-visible:ring-offset-2"
    >
      <div className="relative">
        <BlogImage post={post} featured={featured} />

        <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/90 via-black/55 to-black/5" />

        <div className="absolute left-0 top-3 z-10 sm:top-4">
          <span className="inline-flex border border-white/80 border-l-0 bg-white pl-3 pr-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.14em] text-brand shadow-[0_0_0_1px_rgba(0,0,0,0.06),0_6px_14px_rgba(0,0,0,0.3)]">
            {categoryLabel}
          </span>
        </div>

        <div className="absolute inset-x-0 bottom-0 z-10 p-3.5 sm:p-4">
          <div className="mb-1.5 text-[11px] font-medium uppercase tracking-[0.11em] text-slate-100/90">
            {published && <time dateTime={post.published_at}>{published}</time>}
          </div>
          <h3
            className={`${
              featured ? 'text-lg sm:text-xl lg:text-2xl' : 'text-base sm:text-lg'
            } font-semibold leading-tight text-white line-clamp-2`}
          >
            {post.title}
          </h3>
          {post.excerpt && (
            <p
              className={`mt-1.5 text-sm leading-snug text-slate-100/95 ${
                featured ? 'line-clamp-2 lg:line-clamp-3' : 'line-clamp-2'
              }`}
            >
              {post.excerpt}
            </p>
          )}
        </div>
      </div>
    </a>
  );
}

export function GinBlogSection({
  posts,
  loading,
  error,
  title,
  subtitle,
  ctaLabel,
  ctaUrl,
}: GinBlogSectionProps) {
  const visiblePosts = useMemo(() => posts.slice(0, 3), [posts]);

  return (
    <section className="w-full bg-white text-gray-900 px-4 sm:px-6 lg:px-8 py-14">
      <div className="w-full">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div className="max-w-2xl">
            <h2 className="text-2xl font-semibold">{title}</h2>
            {subtitle && <p className="mt-2 text-slate-600">{subtitle}</p>}
          </div>
          <a
            href={ctaUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-full border border-brand bg-brand px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#002f49] focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-active focus-visible:ring-offset-2"
          >
            {ctaLabel}
            <ArrowRight className="h-4 w-4" />
          </a>
        </div>

        {loading && (
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 text-slate-300">
            Loading stories...
          </div>
        )}
        {!loading && error && (
          <div className="rounded-xl border border-red-500/30 bg-red-950/20 p-6 text-red-100">
            {error}
          </div>
        )}
        {!loading && !error && posts.length === 0 && (
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 text-slate-300">
            No stories available yet.
          </div>
        )}
        {!loading && !error && posts.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
            {visiblePosts.map((post) => (
              <BlogCard key={post.slug} post={post} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
