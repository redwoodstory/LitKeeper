let currentMigrationSessionId = null;
let migrationPollInterval = null;

document.addEventListener('DOMContentLoaded', () => {
    const btnStartMigration = document.getElementById('btnStartMigration');
    const btnDryRun = document.getElementById('btnDryRun');
    const btnEnableDB = document.getElementById('btnEnableDB');
    const btnDisableDB = document.getElementById('btnDisableDB');
    const btnClearDB = document.getElementById('btnClearDB');

    if (btnStartMigration) {
        btnStartMigration.addEventListener('click', () => startMigration(false));
    }

    if (btnDryRun) {
        btnDryRun.addEventListener('click', () => startMigration(true));
    }

    if (btnEnableDB) {
        btnEnableDB.addEventListener('click', enableDatabaseMode);
    }

    if (btnDisableDB) {
        btnDisableDB.addEventListener('click', disableDatabaseMode);
    }

    if (btnClearDB) {
        btnClearDB.addEventListener('click', clearDatabase);
    }
});

async function startMigration(dryRun = false) {
    if (!confirm(`Are you sure you want to ${dryRun ? 'run a dry-run' : 'start the migration'}?`)) {
        return;
    }

    const progressSection = document.getElementById('migrationProgress');
    progressSection.classList.remove('hidden');

    resetProgressUI();

    try {
        const response = await fetch('/admin/migration/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ dry_run: dryRun })
        });

        const data = await response.json();

        if (data.success) {
            currentMigrationSessionId = data.session_id;

            if (data.result.completed) {
                updateProgressUI(data.result);
            } else {
                pollMigrationStatus();
            }
        } else {
            alert('Failed to start migration: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Migration error:', error);
        alert('Failed to start migration: ' + error.message);
    }
}

function pollMigrationStatus() {
    if (!currentMigrationSessionId) return;

    migrationPollInterval = setInterval(async () => {
        try {
            const response = await fetch(`/admin/migration/status/${currentMigrationSessionId}`);
            const data = await response.json();

            if (data.success) {
                updateProgressUI(data.result);

                if (data.result.completed) {
                    clearInterval(migrationPollInterval);
                    migrationPollInterval = null;
                    onMigrationComplete(data.result);
                }
            }
        } catch (error) {
            console.error('Failed to poll migration status:', error);
            clearInterval(migrationPollInterval);
            migrationPollInterval = null;
        }
    }, 1000);
}

function updateProgressUI(result) {
    const progressText = document.getElementById('progressText');
    const progressBar = document.getElementById('progressBar');
    const successCount = document.getElementById('successCount');
    const failedCount = document.getElementById('failedCount');
    const duplicateCount = document.getElementById('duplicateCount');
    const skippedCount = document.getElementById('skippedCount');
    const errorList = document.getElementById('errorList');
    const errorItems = document.getElementById('errorItems');

    const progress = result.total_files > 0
        ? (result.processed / result.total_files) * 100
        : 0;

    progressText.textContent = `${result.processed} / ${result.total_files}`;
    progressBar.style.width = `${progress}%`;

    successCount.textContent = result.successful;
    failedCount.textContent = result.failed;
    duplicateCount.textContent = result.duplicates;
    skippedCount.textContent = result.skipped;

    if (result.errors && result.errors.length > 0) {
        errorList.classList.remove('hidden');
        errorItems.innerHTML = '';
        result.errors.forEach(error => {
            const li = document.createElement('li');
            li.textContent = error;
            errorItems.appendChild(li);
        });
    } else {
        errorList.classList.add('hidden');
    }
}

function resetProgressUI() {
    document.getElementById('progressText').textContent = '0 / 0';
    document.getElementById('progressBar').style.width = '0%';
    document.getElementById('successCount').textContent = '0';
    document.getElementById('failedCount').textContent = '0';
    document.getElementById('duplicateCount').textContent = '0';
    document.getElementById('skippedCount').textContent = '0';
    document.getElementById('errorList').classList.add('hidden');
    document.getElementById('errorItems').innerHTML = '';
}

function onMigrationComplete(result) {
    const message = `Migration complete!\n\n` +
                   `Total: ${result.total_files}\n` +
                   `Successful: ${result.successful}\n` +
                   `Failed: ${result.failed}\n` +
                   `Duplicates: ${result.duplicates}\n` +
                   `Duration: ${result.duration_seconds?.toFixed(1) || 'N/A'}s`;

    alert(message);

    if (result.successful > 0 && result.failed === 0) {
        if (confirm('Migration successful! Enable database mode now?')) {
            enableDatabaseMode();
        }
    }

    setTimeout(() => {
        window.location.reload();
    }, 1000);
}

async function enableDatabaseMode() {
    if (!confirm('Enable database mode? The app will use the database instead of files.')) {
        return;
    }

    try {
        const response = await fetch('/admin/migration/enable-db-mode', {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            alert('Database mode enabled successfully!');
            window.location.reload();
        } else {
            alert('Failed to enable database mode: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Enable DB mode error:', error);
        alert('Failed to enable database mode: ' + error.message);
    }
}

async function disableDatabaseMode() {
    if (!confirm('Disable database mode? The app will use files instead. Database data will be preserved.')) {
        return;
    }

    try {
        const response = await fetch('/admin/migration/disable-db-mode', {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            alert('Database mode disabled. App rolled back to file-based mode.');
            window.location.reload();
        } else {
            alert('Failed to disable database mode: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Disable DB mode error:', error);
        alert('Failed to disable database mode: ' + error.message);
    }
}

async function clearDatabase() {
    const confirmation = prompt('This will permanently delete ALL migrated data. Type "DELETE" to confirm:');

    if (confirmation !== 'DELETE') {
        return;
    }

    try {
        const response = await fetch('/admin/migration/clear-database', {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            alert('Database cleared successfully!');
            window.location.reload();
        } else {
            alert('Failed to clear database: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Clear database error:', error);
        alert('Failed to clear database: ' + error.message);
    }
}
