export default defineEventHandler(async (event) => {
  const slug = encodeURIComponent(getRouterParam(event, 'slug') || '');
  const post = await fetchApi<any>(`/api/v1/posts/${slug}`, event);
  const { html, toc } = await renderCached(`post:${post.id}`, post.content_md || '');
  const { content_md: _omit, ...rest } = post;
  return { ...rest, html, toc };
});
