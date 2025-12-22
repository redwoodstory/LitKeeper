function updateSWStatus() {
  const statusDiv = document.getElementById('swStatus');

  if (!('serviceWorker' in navigator)) {
    statusDiv.innerHTML = '<p class="text-red-600 dark:text-red-400">❌ Service Workers not supported in this browser</p>';
    return;
  }

  const controller = navigator.serviceWorker.controller;
  const state = swRegistration ? swRegistration.active?.state : 'unknown';
  const ready = swRegistration?.active ? '✅ Yes' : '⏳ Installing...';
  const scope = swRegistration?.scope || 'unknown';

  console.log('[SW Status] Controller:', controller);
  console.log('[SW Status] Registration:', swRegistration);
  console.log('[SW Status] Active:', swRegistration?.active);
  console.log('[SW Status] Scope:', scope);
  console.log('[SW Status] Current URL:', window.location.href);

  statusDiv.innerHTML = `
    <div class="space-y-2">
      <p class="text-gray-700 dark:text-gray-300">
        <strong>Supported:</strong> ${('serviceWorker' in navigator) ? '✅ Yes' : '❌ No'}
      </p>
      <p class="text-gray-700 dark:text-gray-300">
        <strong>Registered:</strong> ${swRegistration ? '✅ Yes' : '❌ No'}
      </p>
      <p class="text-gray-700 dark:text-gray-300">
        <strong>Active:</strong> ${ready}
      </p>
      <p class="text-gray-700 dark:text-gray-300">
        <strong>Controlling Page:</strong> ${controller ? '✅ Yes' : '❌ No'}
      </p>
      <p class="text-gray-700 dark:text-gray-300">
        <strong>State:</strong> ${state}
      </p>
      <p class="text-gray-700 dark:text-gray-300 text-xs">
        <strong>Scope:</strong> ${scope}
      </p>
      <p class="text-gray-700 dark:text-gray-300 text-xs">
        <strong>Page URL:</strong> ${window.location.href}
      </p>
      ${!controller && swRegistration?.active ? '<p class="text-yellow-600 dark:text-yellow-400 mt-2 p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded">⚠️ <strong>Service worker is active but not controlling this page.</strong><br>Check the browser console for debug info. The scope might not match the page URL.</p>' : ''}
      ${controller ? '<p class="text-green-600 dark:text-green-400 mt-2 p-3 bg-green-50 dark:bg-green-900/20 rounded">✅ <strong>Offline support active!</strong> You can now use the app offline. Stories you read will be cached automatically.</p>' : ''}
    </div>
  `;
}

let swRegistration = null;
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js')
      .then((registration) => {
        swRegistration = registration;
        console.log('Service Worker registered successfully:', registration.scope);
        updateSWStatus();

        registration.update();

        if (registration.active) {
          loadStorageInfo();
        } else {
          registration.addEventListener('updatefound', () => {
            const newWorker = registration.installing;
            console.log('New service worker found, installing...');
            newWorker.addEventListener('statechange', () => {
              console.log('Service Worker state:', newWorker.state);
              if (newWorker.state === 'activated') {
                console.log('New service worker activated!');
                updateSWStatus();
                loadStorageInfo();
              }
            });
          });
        }
      })
      .catch((error) => {
        console.log('Service Worker registration failed:', error);
        document.getElementById('swStatus').innerHTML =
          `<p class="text-red-600 dark:text-red-400">❌ Registration failed: ${error.message}</p>`;
      });

    navigator.serviceWorker.addEventListener('controllerchange', () => {
      console.log('Service Worker controller changed - reloading page');
      updateSWStatus();
      window.location.reload();
    });

    setTimeout(updateSWStatus, 100);
  });
} else {
  updateSWStatus();
}

document.getElementById('forceUpdate').addEventListener('click', async () => {
  if (!swRegistration) {
    alert('No service worker registered yet');
    return;
  }

  const button = document.getElementById('forceUpdate');
  button.textContent = 'Updating...';
  button.disabled = true;

  try {
    await swRegistration.unregister();
    console.log('Old service worker unregistered');

    const cacheNames = await caches.keys();
    await Promise.all(cacheNames.map(name => caches.delete(name)));
    console.log('All caches cleared');

    window.location.reload();
  } catch (error) {
    console.error('Force update failed:', error);
    button.textContent = 'Force Update';
    button.disabled = false;
    alert('Update failed: ' + error.message);
  }
});

let deferredPrompt;
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
  console.log('PWA install prompt available');
});

async function loadStorageInfo() {
  const storageInfoDiv = document.getElementById('storageInfo');

  if (!navigator.serviceWorker || !navigator.serviceWorker.controller) {
    storageInfoDiv.innerHTML = '<p class="text-yellow-600 dark:text-yellow-400">Service Worker not active yet. Refresh the page.</p>';
    return;
  }

  try {
    const messageChannel = new MessageChannel();

    const response = await new Promise((resolve, reject) => {
      messageChannel.port1.onmessage = (event) => {
        if (event.data.success) {
          resolve(event.data.storage);
        } else {
          reject(new Error(event.data.error));
        }
      };

      navigator.serviceWorker.controller.postMessage(
        { type: 'GET_STORAGE_INFO' },
        [messageChannel.port2]
      );

      setTimeout(() => reject(new Error('Timeout')), 5000);
    });

    const usedMB = (response.usage / (1024 * 1024)).toFixed(2);
    const quotaMB = (response.quota / (1024 * 1024)).toFixed(2);
    const quotaGB = (response.quota / (1024 * 1024 * 1024)).toFixed(2);
    const percentUsed = ((response.usage / response.quota) * 100).toFixed(1);

    storageInfoDiv.innerHTML = `
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <p class="font-semibold text-gray-700 dark:text-gray-300">Storage Type:</p>
          <p class="text-gray-600 dark:text-gray-400">OPFS (Origin Private File System)</p>
        </div>
        <div>
          <p class="font-semibold text-gray-700 dark:text-gray-300">Persistent:</p>
          <p class="text-gray-600 dark:text-gray-400">
            ${response.persistent ? '✅ Yes (won\'t be evicted)' : '⚠️ No (request permission)'}
          </p>
        </div>
        <div>
          <p class="font-semibold text-gray-700 dark:text-gray-300">Stories Cached:</p>
          <p class="text-gray-600 dark:text-gray-400">${response.storiesCount} HTML files</p>
        </div>
        <div>
          <p class="font-semibold text-gray-700 dark:text-gray-300">Storage Used:</p>
          <p class="text-gray-600 dark:text-gray-400">${usedMB} MB of ${quotaGB} GB (${percentUsed}%)</p>
        </div>
      </div>
      <div class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
        <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
          <div class="bg-primary h-2 rounded-full transition-all" style="width: ${percentUsed}%"></div>
        </div>
        <p class="text-xs text-gray-500 dark:text-gray-400 mt-2">
          Available space: ${(quotaMB - usedMB).toFixed(2)} MB (~${Math.floor((response.quota - response.usage) / (200 * 1024))} more stories at 200KB each)
        </p>
      </div>
    `;

    if (!response.persistent) {
      const requestBtn = document.createElement('button');
      requestBtn.className = 'mt-4 px-4 py-2 bg-primary hover:bg-primary-dark text-white rounded transition-colors';
      requestBtn.textContent = 'Request Persistent Storage';
      requestBtn.onclick = async () => {
        const granted = await navigator.storage.persist();
        if (granted) {
          alert('Persistent storage granted! Your stories won\'t be evicted.');
          loadStorageInfo();
        } else {
          alert('Persistent storage denied. Your stories may be evicted under storage pressure.');
        }
      };
      storageInfoDiv.appendChild(requestBtn);
    }
  } catch (error) {
    console.error('Failed to load storage info:', error);
    storageInfoDiv.innerHTML = `<p class="text-red-600 dark:text-red-400">Failed to load storage info: ${error.message}</p>`;
  }
}

document.getElementById('refreshStorage').addEventListener('click', loadStorageInfo);
