class MetadataModal {
    constructor() {
        this.modal = null;
        this.metadata = null;
        this.onSaveCallback = null;
        this.boundHandleEscape = this.handleEscape.bind(this);
    }

    show(metadata, onSave) {
        this.metadata = metadata;
        this.onSaveCallback = onSave;
        this.render();
        this.attachEventListeners();
        document.body.style.overflow = 'hidden';
    }

    hide() {
        if (this.modal) {
            this.modal.remove();
            this.modal = null;
        }
        document.removeEventListener('keydown', this.boundHandleEscape);
        document.body.style.overflow = '';
    }

    render() {
        const tagsString = Array.isArray(this.metadata.tags)
            ? this.metadata.tags.join(', ')
            : '';

        const modalHTML = `
            <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm" id="metadata-modal-overlay">
                <div class="bg-white dark:bg-slate-800 rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
                    <div class="px-6 py-4 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
                        <h2 class="text-xl font-semibold text-slate-900 dark:text-slate-100">Edit Story Metadata</h2>
                        <button type="button" class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors" id="metadata-modal-close">
                            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                            </svg>
                        </button>
                    </div>

                    <div class="flex-1 overflow-y-auto p-6">
                        <form id="metadata-form" class="space-y-5">
                            <div>
                                <label for="metadata-title" class="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">
                                    Title <span class="text-red-500">*</span>
                                </label>
                                <input
                                    type="text"
                                    id="metadata-title"
                                    name="title"
                                    value="${this.escapeHtml(this.metadata.title)}"
                                    required
                                    class="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-slate-700 dark:text-slate-100 transition-all"
                                    placeholder="Story Title"
                                />
                                <p class="mt-1 text-xs text-red-500 hidden" id="title-error">Title is required</p>
                            </div>

                            <div>
                                <label for="metadata-author" class="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">
                                    Author
                                </label>
                                <input
                                    type="text"
                                    id="metadata-author"
                                    name="author"
                                    value="${this.escapeHtml(this.metadata.author)}"
                                    class="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-slate-700 dark:text-slate-100 transition-all"
                                    placeholder="Unknown Author"
                                />
                            </div>

                            <div>
                                <label for="metadata-category" class="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">
                                    Category
                                </label>
                                <input
                                    type="text"
                                    id="metadata-category"
                                    name="category"
                                    value="${this.escapeHtml(this.metadata.category || '')}"
                                    class="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-slate-700 dark:text-slate-100 transition-all"
                                    placeholder="e.g., Romance, Sci-Fi"
                                />
                            </div>

                            <div>
                                <label for="metadata-tags" class="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">
                                    Tags
                                </label>
                                <input
                                    type="text"
                                    id="metadata-tags"
                                    name="tags"
                                    value="${this.escapeHtml(tagsString)}"
                                    class="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-slate-700 dark:text-slate-100 transition-all"
                                    placeholder="tag1, tag2, tag3"
                                />
                                <p class="mt-1 text-xs text-slate-500 dark:text-slate-400">Separate tags with commas</p>
                            </div>

                            <input type="hidden" name="url" value="${this.escapeHtml(this.metadata.url)}" />
                        </form>
                    </div>

                    <div class="px-6 py-4 border-t border-slate-200 dark:border-slate-700 flex gap-3 justify-end bg-slate-50 dark:bg-slate-900/50">
                        <button
                            type="button"
                            id="metadata-modal-cancel"
                            class="px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-lg transition-all"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            form="metadata-form"
                            id="metadata-modal-save"
                            class="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-all shadow-sm hover:shadow flex items-center gap-2"
                        >
                            <span id="save-text">Save & Import</span>
                            <svg id="save-spinner" class="hidden animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                        </button>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.modal = document.getElementById('metadata-modal-overlay');

        setTimeout(() => {
            document.getElementById('metadata-title')?.focus();
        }, 100);
    }

    attachEventListeners() {
        const overlay = document.getElementById('metadata-modal-overlay');
        const closeBtn = document.getElementById('metadata-modal-close');
        const cancelBtn = document.getElementById('metadata-modal-cancel');
        const form = document.getElementById('metadata-form');

        overlay?.addEventListener('click', (e) => {
            if (e.target === overlay) {
                this.hide();
            }
        });

        closeBtn?.addEventListener('click', () => this.hide());
        cancelBtn?.addEventListener('click', () => this.hide());

        document.addEventListener('keydown', this.boundHandleEscape);

        form?.addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.handleSave(e);
        });
    }

    handleEscape(e) {
        if (e.key === 'Escape' && this.modal) {
            this.hide();
        }
    }

    async handleSave(e) {
        const form = e.target;
        const formData = new FormData(form);

        const title = formData.get('title')?.trim();
        if (!title) {
            const titleError = document.getElementById('title-error');
            const titleInput = document.getElementById('metadata-title');
            titleError?.classList.remove('hidden');
            titleInput?.classList.add('border-red-500');
            titleInput?.focus();
            return;
        }

        const tagsString = formData.get('tags')?.trim() || '';
        const tags = tagsString
            ? tagsString.split(',').map(tag => tag.trim()).filter(tag => tag)
            : [];

        const metadata = {
            url: formData.get('url'),
            title: title,
            author: formData.get('author')?.trim() || 'Unknown Author',
            category: formData.get('category')?.trim() || null,
            tags: tags,
            formats: this.metadata.formats
        };

        const saveBtn = document.getElementById('metadata-modal-save');
        const saveText = document.getElementById('save-text');
        const saveSpinner = document.getElementById('save-spinner');

        saveBtn.disabled = true;
        saveText.textContent = 'Saving...';
        saveSpinner?.classList.remove('hidden');

        try {
            if (this.onSaveCallback) {
                await this.onSaveCallback(metadata);
            }
            this.hide();
        } catch (error) {
            console.error('Error saving metadata:', error);
            saveBtn.disabled = false;
            saveText.textContent = 'Save & Import';
            saveSpinner?.classList.add('hidden');
        }
    }

    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return String(text).replace(/[&<>"']/g, m => map[m]);
    }
}

window.MetadataModal = MetadataModal;
