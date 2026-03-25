self.addEventListener('fetch', (event) => {
    // Pass through all requests directly to network
    event.respondWith(fetch(event.request));
});
