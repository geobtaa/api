import { ExternalLink } from 'lucide-react';
import { useApi } from '../../context/ApiContext';

interface FooterProps {
  id?: string;
}

function BtaaFooter({ id }: FooterProps) {
  const { lastApiUrl } = useApi();
  const footerLinkClass = 'text-white/85 hover:text-white hover:underline';

  return (
    <footer className="bg-[#003C5B] text-white print:hidden">
      <div className="w-full px-4 sm:px-6 lg:px-8 py-12">
        <div className="space-y-10">
          <div>
            <a href="https://gin.btaa.org">
              <img
                src="/gin-white.png"
                alt="Big Ten Academic Alliance Geospatial Information Network"
                className="h-16 w-auto mb-4 rounded"
              />
            </a>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-8 text-sm">
            <div>
              <h3 className="font-bold text-lg mb-3 text-white">
                About & Help
              </h3>
              <ul className="space-y-2">
                <li>
                  <a href="/about" className={footerLinkClass}>
                    About Us
                  </a>
                </li>
                <li>
                  <a
                    href="https://gin.btaa.org/updates"
                    className={footerLinkClass}
                  >
                    Program Updates
                  </a>
                </li>
                <li>
                  <a href="/feedback" className={footerLinkClass}>
                    Contact Us
                  </a>
                </li>
                <li>
                  <a href="/help" className={footerLinkClass}>
                    Help
                  </a>
                </li>
                <li>
                  <a
                    href="https://gin.btaa.org/tutorials"
                    className={footerLinkClass}
                  >
                    Tutorials
                  </a>
                </li>
              </ul>
            </div>

            <div>
              <h3 className="font-bold text-lg mb-3 text-white">Policies</h3>
              <ul className="space-y-2">
                <li>
                  <a
                    href="https://gin.btaa.org/policies/harmful-language"
                    className={footerLinkClass}
                  >
                    Harmful Language Statement
                  </a>
                </li>
                <li>
                  <a
                    href="https://btaa.org/privacy"
                    className={footerLinkClass}
                  >
                    Privacy Statement
                  </a>
                </li>
                <li>
                  <a
                    href="https://gin.btaa.org/policies/collection-development"
                    className={footerLinkClass}
                  >
                    Collection Development
                  </a>
                </li>
              </ul>
            </div>

            <div>
              <h3 className="font-bold text-lg mb-3 text-white">Sponsors</h3>
              <ul className="space-y-2">
                <li>
                  <a href="https://btaa.org/" className={footerLinkClass}>
                    Big Ten Academic Alliance
                  </a>
                </li>
                <li>
                  <a href="https://gin.btaa.org/" className={footerLinkClass}>
                    BTAA Geospatial Information Network
                  </a>
                </li>
                <li>
                  <a href="https://lib.umn.edu/" className={footerLinkClass}>
                    University of Minnesota Libraries
                  </a>
                </li>
              </ul>
            </div>

            <div className="lg:col-span-2">
              <h3 className="font-bold text-lg mb-3 text-white">
                BTAA Member Libraries
              </h3>
              <ul className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs text-white/85">
                <li>Indiana University</li>
                <li>Michigan State University</li>
                <li>Northwestern University</li>
                <li>Pennsylvania State University</li>
                <li>Purdue University</li>
                <li>Rutgers University</li>
                <li>The Ohio State University</li>
                <li>University of Chicago</li>
                <li>University of Illinois</li>
                <li>University of Iowa</li>
                <li>University of Maryland</li>
                <li>University of Michigan</li>
                <li>University of Minnesota</li>
                <li>University of Nebraska-Lincoln</li>
                <li>University of Oregon</li>
                <li>University of Washington</li>
                <li>University of Wisconsin-Madison</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Divider */}
        <hr className="border-white/20 my-10" />

        {/* Bottom Section: API Info & Contextual Links */}
        <div className="flex flex-col md:flex-row justify-between items-start gap-8 text-sm">
          {/* Copyright & API Info */}
          <div className="flex flex-col gap-4 w-full md:w-auto">
            <div className="text-white/70">
              © {new Date().getFullYear()} Big Ten Academic Alliance. All rights
              reserved.
            </div>

            {/* API Debug Info */}
            {lastApiUrl ? (
              <div className="flex items-center gap-2 bg-[#002a41] rounded px-3 py-1.5 border border-white/15 w-full md:w-fit">
                <span className="text-xs uppercase tracking-wider font-semibold text-white/60 shrink-0">
                  API:
                </span>
                <a
                  href={lastApiUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="truncate text-xs font-mono text-white/75 hover:text-white transition-colors flex items-center gap-1 group"
                >
                  <span className="truncate max-w-[200px] sm:max-w-[400px]">
                    {lastApiUrl}
                  </span>
                  <ExternalLink
                    size={10}
                    className="shrink-0 opacity-50 group-hover:opacity-100"
                  />
                </a>
              </div>
            ) : (
              <div className="text-xs text-white/60 italic">
                No API requests yet
              </div>
            )}
          </div>

          {id && (
            <div className="flex flex-wrap items-center gap-6 bg-[#002a41] px-4 py-3 rounded-lg border border-white/15">
              <a
                href={`https://geo.btaa.org/catalog/${id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-white/75 hover:text-white transition-colors flex items-center gap-1 uppercase font-semibold tracking-wider"
              >
                View Original
                <ExternalLink size={10} />
              </a>
            </div>
          )}
        </div>
      </div>
    </footer>
  );
}

export function Footer({ id }: FooterProps) {
  return <BtaaFooter id={id} />;
}

export default Footer;
