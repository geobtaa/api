import { render, screen } from '@testing-library/react';
import { GinBlogSection } from '../../../components/home/GinBlogSection';
import type { HomeBlogPost } from '../../../types/api';

const SAMPLE_POSTS: HomeBlogPost[] = [
  {
    slug: 'pinned-slug',
    url: 'https://gin.btaa.org/updates/pinned-slug/',
    title: 'Pinned Story',
    excerpt: 'Pinned excerpt',
    published_at: '2026-02-02T00:00:00',
    category: 'update',
    authors: ['BTAA-GIN Staff'],
    tags: ['Program Updates'],
    image_url: null,
    image_alt: null,
  },
  {
    slug: 'second-slug',
    url: 'https://gin.btaa.org/posts/second-slug/',
    title: 'Second Story',
    excerpt: 'Second excerpt',
    published_at: '2026-01-29T00:00:00',
    category: 'post',
    authors: ['Author One'],
    tags: ['featured collections'],
    image_url: null,
    image_alt: null,
  },
];

describe('GinBlogSection', () => {
  it('renders title, CTA, and post cards', () => {
    render(
      <GinBlogSection
        posts={SAMPLE_POSTS}
        loading={false}
        error={null}
        title="GIN News & Stories"
        subtitle="Latest updates from BTAA-GIN."
        ctaLabel="View all stories"
        ctaUrl="https://gin.btaa.org/blog/"
      />
    );

    expect(screen.getByText('GIN News & Stories')).toBeInTheDocument();
    expect(screen.getByText('Pinned Story')).toBeInTheDocument();
    expect(screen.getByText('Second Story')).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /view all stories/i })
    ).toHaveAttribute('href', 'https://gin.btaa.org/blog/');
    expect(screen.queryAllByText(/2026|jan|feb/i)).toHaveLength(0);
    expect(document.querySelector('time')).toBeNull();
  });

  it('renders loading state', () => {
    render(
      <GinBlogSection
        posts={[]}
        loading
        error={null}
        title="GIN News & Stories"
        ctaLabel="View all stories"
        ctaUrl="https://gin.btaa.org/blog/"
      />
    );
    expect(screen.getByText('Loading stories...')).toBeInTheDocument();
  });
});
