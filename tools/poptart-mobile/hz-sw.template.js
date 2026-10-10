// Hazewave Poptart versioned same-origin offline asset cache.
const CACHE = /*HAZE_CACHE_NAME*/;
const SHELL = /*HAZE_CACHE_LIST*/;
self.addEventListener('install', event => event.waitUntil((async () => {
  const cache = await caches.open(CACHE);
  // Bound concurrency avoids one sequential request per asset on mobile, while
  // preventing a 400-request burst on Codespaces and Chrome Android.
  try {
    for (let offset = 0; offset < SHELL.length; offset += 6) {
      await Promise.all(SHELL.slice(offset, offset + 6).map(async (url) => {
        const response = await fetch(url, { cache: 'reload' });
        if (!response.ok) throw new Error('Missing core asset: ' + url);
        await cache.put(url, response);
      }));
    }
  } catch (error) {
    await caches.delete(CACHE);
    throw error;
  }
  // Do not forcibly replace a worker during a live musical performance.
  // Existing clients transition naturally when their old tab is closed.
})()));
self.addEventListener('activate', event => event.waitUntil((async () => {
  const names = await caches.keys();
  await Promise.all(names.filter(n => n.startsWith('hz-poptart-') && n !== CACHE).map(n => caches.delete(n)));
  await self.clients.claim();
})()));
self.addEventListener('fetch', event => {
  const request = event.request;
  const u = new URL(request.url);
  if (request.method !== 'GET' || u.origin !== self.location.origin) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const existing = await cache.match(request);
    if (existing) return existing;
    try {
      const fresh = await fetch(request);
      if (fresh.ok && fresh.type === 'basic') await cache.put(request, fresh.clone());
      return fresh;
    } catch { return Response.error(); }
  })());
});
