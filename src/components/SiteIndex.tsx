import type { Site } from '../api';

const SECTIONS: { category: Site['category']; title: string }[] = [
  { category: 'video', title: 'Video & audio' },
  { category: 'social', title: 'Social' },
  { category: 'image', title: 'Images' },
];

export function SiteIndex({ sites }: { sites: Site[] }) {
  if (!sites.length) return null;
  return (
    <footer className="index">
      <div className="index-intro">
        <h2>Works with</h2>
        <p>
          A few favourites below. Under the hood, <b>yt-dlp</b> and <b>gallery-dl</b> cover well over a thousand sites, so try any link.
        </p>
      </div>
      <div className="index-grid">
        {SECTIONS.map(({ category, title }) => (
          <div key={category} className={`index-col ${category}`}>
            <h3>{title}</h3>
            <ul>
              {sites
                .filter((s) => s.category === category)
                .map((s) => (
                  <li key={s.domain} title={s.domain}>
                    {s.name}
                  </li>
                ))}
            </ul>
          </div>
        ))}
      </div>
      <p className="colophon">Private tool · runs on your machine · nothing is tracked, nothing is shared.</p>
    </footer>
  );
}
