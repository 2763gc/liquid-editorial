export default defineEventHandler(async (event) => {
  const slug = encodeURIComponent(getRouterParam(event, 'slug') || '');
  const project = await fetchApi<any>(`/api/v1/projects/${slug}`, event);
  const { html } = await renderCached(`project:${project.id ?? slug}`, project.description_md || '');
  return { ...project, html };
});
