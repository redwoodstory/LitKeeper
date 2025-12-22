window.syncStory = async function(filename, button) {
  const originalText = button.innerHTML;
  button.disabled = true;
  button.innerHTML = '⏳ Syncing...';

  try {
    const response = await fetch(`/read/${filename}`);
    if (response.ok) {
      button.innerHTML = '✅ Synced!';
      setTimeout(() => {
        button.innerHTML = originalText;
        button.disabled = false;
      }, 2000);
    } else {
      throw new Error('Failed to fetch story');
    }
  } catch (error) {
    console.error('Sync error:', error);
    button.innerHTML = '❌ Failed';
    setTimeout(() => {
      button.innerHTML = originalText;
      button.disabled = false;
    }, 2000);
  }
};

document.getElementById('syncAllStories').addEventListener('click', async function() {
  const button = this;
  const originalText = button.innerHTML;
  button.disabled = true;
  button.innerHTML = 'Syncing...';

  try {
    const response = await fetch('/api/library');
    const data = await response.json();

    if (!data.stories || data.stories.length === 0) {
      alert('No stories to sync');
      button.innerHTML = originalText;
      button.disabled = false;
      return;
    }

    const htmlStories = data.stories.filter(s => s.formats.includes('html'));

    if (htmlStories.length === 0) {
      alert('No HTML stories to sync');
      button.innerHTML = originalText;
      button.disabled = false;
      return;
    }

    let synced = 0;
    let failed = 0;

    for (const story of htmlStories) {
      try {
        const storyResponse = await fetch(`/read/${story.html_file}`);
        if (storyResponse.ok) {
          synced++;
          button.innerHTML = `Syncing... ${synced}/${htmlStories.length}`;
        } else {
          failed++;
        }
      } catch (error) {
        console.error(`Failed to sync ${story.title}:`, error);
        failed++;
      }
    }

    button.innerHTML = `Synced ${synced}/${htmlStories.length}`;
    if (failed > 0) {
      button.innerHTML += ` (${failed} failed)`;
    }

    setTimeout(() => {
      button.innerHTML = originalText;
      button.disabled = false;
    }, 3000);

  } catch (error) {
    console.error('Sync all error:', error);
    button.innerHTML = 'Failed';
    setTimeout(() => {
      button.innerHTML = originalText;
      button.disabled = false;
    }, 2000);
  }
});
