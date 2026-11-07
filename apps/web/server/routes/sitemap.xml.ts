export default defineEventHandler(async (event) => {
  const apiBase = process.env.API_INTERNAL_URL || 'http://127.0.0.1:8000';
  const siteUrl = process.env.SITE_URL || 'http://localhost:3000';

  let posts: any[] = [];
  try {
    const res: any = await $fetch(`${apiBase}/api/v1/feed`);
    posts = res || [];
  } catch (err) {
    posts = [];
  }

  const staticRoutes = [
    '',
    '/posts',
    '/projects',
    '/archive',
    '/about',
  ];

  const staticUrls = staticRoutes.map((r) => `
    <url>
      <loc>${siteUrl}${r}</loc>
      <changefreq>daily</changefreq>
      <priority>${r === '' ? '1.0' : '0.8'}</priority>
    </url>
  `).join('');

  const postUrls = posts.map((p) => `
    <url>
      <loc>${siteUrl}${p.url}</loc>
      <lastmod>${(p.updated_at || p.published_at || '').split('T')[0]}</lastmod>
      <changefreq>weekly</changefreq>
      <priority>0.9</priority>
    </url>
  `).join('');

  const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  ${staticUrls}
  ${postUrls}
</urlset>`;

  event.node.res.setHeader('content-type', 'application/xml; charset=utf-8');
  return sitemap;
});
