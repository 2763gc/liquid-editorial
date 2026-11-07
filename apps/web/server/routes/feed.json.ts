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

  const feedJson = {
    version: 'https://jsonfeed.org/version/1.1',
    title: "Luntrix's Editorial",
    home_page_url: siteUrl,
    feed_url: `${siteUrl}/feed.json`,
    description: '杂志级排版 × 空间化交互 × 电影级动效个人技术博客',
    items: posts.map((p) => ({
      id: `${siteUrl}${p.url}`,
      url: `${siteUrl}${p.url}`,
      title: p.title,
      summary: p.description,
      content_text: p.content_md,
      date_published: p.published_at,
      date_modified: p.updated_at,
    })),
  };

  event.node.res.setHeader('content-type', 'application/json; charset=utf-8');
  return feedJson;
});
