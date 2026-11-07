/** Nitro 存活探针：只回答活着没有，不暴露内存、版本与运行时长 */
export default defineEventHandler(() => ({ status: 'healthy', timestamp: new Date().toISOString() }));
