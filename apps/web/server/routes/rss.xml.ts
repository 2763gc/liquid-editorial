export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig();
  const apiBase = process.env.API_INTERNAL_URL || 'http://127.0.0.1:8000';
  const siteUrl = process.env.SITE_URL || 'http://localhost:3000';

  let posts: any[] = [];
  try {
    const res: any = await $fetch(`${apiBase}/api/v1/feed`);
    posts = res || [];
  } catch (err) {
    posts = [];
  }

  const itemsXml = posts.map((p) => `
    <item>
      <title><![CDATA[${p.title}]]></title>
      <link>${siteUrl}${p.url}</link>
      <guid>${siteUrl}${p.url}</guid>
      <description><![CDATA[${p.description || ''}]]></description>
      <pubDate>${new Date(p.published_at).toUTCString()}</pubDate>
    </item>
  `).join('');

  const rss = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Luntrix's Editorial</title>
    <link>${siteUrl}</link>
    <description>杂志级排版 × 空间化交互 × 电影级动效个人技术博客</description>
    <language>zh-cn</language>
    ${itemsXml}
  </channel>
</rss>`;

  event.node.res.setHeader('content-type', 'application/xml; charset=utf-8');
  return rss;
});
