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

  const entriesXml = posts.map((p) => `
    <entry>
      <title><![CDATA[${p.title}]]></title>
      <link href="${siteUrl}${p.url}"/>
      <id>${siteUrl}${p.url}</id>
      <updated>${p.updated_at || p.published_at}</updated>
      <summary><![CDATA[${p.description || ''}]]></summary>
    </entry>
  `).join('');

  const atom = `<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Luntrix's Editorial</title>
  <link href="${siteUrl}"/>
  <link href="${siteUrl}/atom.xml" rel="self"/>
  <id>${siteUrl}/</id>
  <updated>${new Date().toISOString()}</updated>
  ${entriesXml}
</feed>`;

  event.node.res.setHeader('content-type', 'application/atom+xml; charset=utf-8');
  return atom;
});
