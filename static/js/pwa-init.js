// Register Service Worker for PWA
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/js/service-worker.js')
      .then((registration) => {
        console.log('ServiceWorker registration successful:', registration.scope);

        // Check for updates periodically
        setInterval(() => {
          registration.update();
        }, 60000); // Check every minute
      })
      .catch((error) => {
        console.log('ServiceWorker registration failed:', error);
      });
  });
}

// Handle PWA install prompt
let deferredPrompt;

window.addEventListener('beforeinstallprompt', (e) => {
  // Prevent the mini-infobar from appearing on mobile
  e.preventDefault();
  // Stash the event so it can be triggered later.
  deferredPrompt = e;
  console.log('beforeinstallprompt fired - preventing default');
});

// Handle app installed event
window.addEventListener('appinstalled', () => {
  console.log('PWA was installed');
  // Remove install banner if it exists
  const banner = document.getElementById('pwa-install-banner');
  if (banner) {
    banner.remove();
  }
});

// Check if running in standalone mode
function isPWA() {
  return window.matchMedia('(display-mode: standalone)').matches ||
    window.navigator.standalone === true;
}

// Add PWA indicator to UI if running as app
if (isPWA()) {
  console.log('Running as PWA');
  // Add a class to body to indicate PWA mode
  document.addEventListener('DOMContentLoaded', () => {
    document.body.classList.add('pwa-mode');
  });
}

// Request notification permission
function requestNotificationPermission() {
  if ('Notification' in window && 'serviceWorker' in navigator) {
    Notification.requestPermission().then((permission) => {
      if (permission === 'granted') {
        console.log('Notification permission granted');
      }
    });
  }
}

// Export functions for use in other scripts
window.AgencySalesProPWA = {
  isPWA,
  requestNotificationPermission
};
