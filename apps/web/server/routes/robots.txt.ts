export default defineEventHandler((event) => {
  const siteUrl = process.env.SITE_URL || 'http://localhost:3000';

  const robots = `User-agent: *
Disallow: /admin/
Disallow: /api/
Disallow: /dev/

Sitemap: ${siteUrl}/sitemap.xml
`;

  event.node.res.setHeader('content-type', 'text/plain; charset=utf-8');
  return robots;
});
