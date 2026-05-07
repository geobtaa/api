import { Header } from '../components/layout/Header';
import { Footer } from '../components/layout/Footer';
import { MarkdownContent } from '../components/content/MarkdownContent';
import { Seo } from '../components/Seo';
import helpMarkdown from '../content/pages/help.md?raw';

export function HelpPage() {
  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <Seo
        title="Help"
        description="Learn how to search, filter, view resources, and use bookmarks in the Big Ten Academic Alliance Geoportal."
      />
      <Header />
      <main className="flex-1">
        <section className="bg-white border-b border-gray-200">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16">
            <MarkdownContent markdown={helpMarkdown} />
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
