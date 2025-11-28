// Attachments Module for Chat Page - MUST BE DEFINED BEFORE DOMContentLoaded
const Attachments = {
    attachedFiles: [], // Store uploaded files here

    init() {
        console.log('📎 Initializing Attachments module...');

        const attachBtn = document.getElementById('attachBtn');
        const attachmentMenu = document.getElementById('attachmentMenu');
        const uploadFileBtn = document.getElementById('uploadFileBtn');
        const addLinkBtn = document.getElementById('addLinkBtn');
        const linkModal = document.getElementById('linkModal');
        const linkInput = document.getElementById('linkInput');
        const submitLinkBtn = document.getElementById('submitLinkBtn');
        const closeModalBtn = document.getElementById('closeModalBtn');

        console.log('Elements found:', {
            attachBtn: !!attachBtn,
            attachmentMenu: !!attachmentMenu,
            uploadFileBtn: !!uploadFileBtn
        });

        if (!attachBtn) {
            console.error('❌ Attach button not found!');
            return;
        }

        if (!attachmentMenu) {
            console.error('❌ Attachment menu not found!');
            return;
        }

        console.log('✅ All required elements found, setting up event listeners...');

        // Add multiple event listeners for debugging
        attachBtn.addEventListener('mouseenter', function () {
            console.log('🖱️ Mouse entered attach button');
        });

        attachBtn.addEventListener('mousedown', function () {
            console.log('🖱️ Mouse down on attach button');
        });

        // Toggle attachment menu with direct addEventListener
        attachBtn.addEventListener('click', function (event) {
            console.log('📎 Attach button clicked!');
            event.stopPropagation();
            event.preventDefault();

            const isVisible = attachmentMenu.classList.contains('active');
            console.log('Menu currently visible:', isVisible);

            if (!isVisible) {
                attachmentMenu.classList.add('active');
                console.log('📎 Menu opened - adding active class');
            } else {
                attachmentMenu.classList.remove('active');
                console.log('📎 Menu closed - removing active class');
            }
        }, true); // Use capture phase

        // Close menu when clicking outside
        document.addEventListener('click', (event) => {
            if (!attachmentMenu) return;
            if (!attachmentMenu.classList.contains('active')) return;
            if (attachmentMenu.contains(event.target) || attachBtn.contains(event.target)) return;
            attachmentMenu.classList.remove('active');
            console.log('📎 Menu closed (outside click)');
        });

        // Handle file upload
        if (uploadFileBtn && attachmentMenu) {
            uploadFileBtn.addEventListener('click', async () => {
                console.log('📁 Upload file button clicked');
                attachmentMenu.classList.remove('active');

                const input = document.createElement('input');
                input.type = 'file';
                input.accept = '.jpg,.jpeg,.png,.md,.txt';
                input.multiple = true; // Allow multiple files

                const self = this; // Capture context

                input.onchange = async (e) => {
                    const files = Array.from(e.target.files);
                    if (files.length === 0) return;

                    console.log(`📁 ${files.length} file(s) selected`);

                    // Check file limit (maximum 5 files combined)
                    if (self.attachedFiles.length + files.length > 5) {
                        Messages.addAIMessage(`❌ Maximum 5 files allowed. You have ${self.attachedFiles.length} files attached and trying to add ${files.length} more.`);
                        return;
                    }

                    // Validate each file
                    for (const file of files) {
                        console.log('📁 Validating file:', file.name, file.type, file.size);

                        // File size check (5MB limit)
                        if (file.size > 5 * 1024 * 1024) {
                            const fileSize = (file.size / (1024 * 1024)).toFixed(2);
                            Messages.addAIMessage(`❌ File "${file.name}" exceeds maximum size.\n\nFile size: ${fileSize} MB\nMaximum allowed: 5 MB`);
                            continue;
                        }

                        // Format validation - only jpg, jpeg, png, md, txt
                        const allowedExtensions = ['.jpg', '.jpeg', '.png', '.md', '.txt'];
                        const fileName = file.name.toLowerCase();
                        const isValidFormat = allowedExtensions.some(ext => fileName.endsWith(ext));

                        if (!isValidFormat) {
                            Messages.addAIMessage(`❌ Format not supported: "${file.name}"\n\nSupported formats: JPG, JPEG, PNG, MD, TXT`);
                            continue;
                        }

                        // Add file to attachedFiles array
                        self.attachedFiles.push(file);
                        console.log(`✅ File "${file.name}" attached. Total files: ${self.attachedFiles.length}`);

                        // Show preview for the file
                        self.showFilePreview(file);
                    }

                    if (self.attachedFiles.length > 0) {
                        Messages.addAIMessage(`✅ ${self.attachedFiles.length} file(s) ready. Type your message and click send to process.`);
                    }
                };

                input.click();
            });
        }

        // Handle link upload
        if (addLinkBtn && attachmentMenu && linkModal) {
            addLinkBtn.addEventListener('click', () => {
                console.log('🔗 Add link button clicked');
                attachmentMenu.classList.remove('active');
                linkModal.style.display = 'flex';
                linkInput.value = '';
                linkInput.focus();
            });
        }

        // Close link modal
        closeModalBtn?.addEventListener('click', () => {
            if (linkModal) linkModal.style.display = 'none';
        });

        // Submit link
        submitLinkBtn?.addEventListener('click', async () => {
            const url = linkInput.value.trim();
            if (!url) {
                Messages.addAIMessage('❌ Please enter a valid URL.');
                return;
            }

            const self = this; // Capture context

            if (self.isValidUrl(url)) {
                if (linkModal) linkModal.style.display = 'none';
                Messages.addUserMessage(`🔗 Link: ${url}`);
                Messages.addAIMessage('🔗 Link processing is not yet implemented.');
            } else {
                Messages.addAIMessage('❌ Invalid URL format.');
            }
        });

        console.log('✅ Attachments module initialized');
    },

    showFilePreview(file) {
        const attachmentArea = document.getElementById('attachmentArea');
        if (!attachmentArea) return;

        const previewId = `preview-${Date.now()}-${Math.random()}`;
        const previewItem = document.createElement('div');
        previewItem.className = 'preview-item';
        previewItem.id = previewId;
        previewItem.style.cssText = 'display: inline-flex; align-items: center; margin: 5px; padding: 8px; background: rgba(255,255,255,0.1); border-radius: 8px; position: relative;';

        const isImage = file.type && file.type.startsWith('image/');
        const isText = file.name.toLowerCase().endsWith('.md') || file.name.toLowerCase().endsWith('.txt');

        // Create thumbnail
        const thumbnailDiv = document.createElement('div');
        thumbnailDiv.style.cssText = 'width: 60px; height: 60px; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,0.3); border-radius: 6px; overflow: hidden; margin-right: 10px;';

        if (isImage) {
            const reader = new FileReader();
            reader.onload = (e) => {
                const img = document.createElement('img');
                img.src = e.target.result;
                img.style.cssText = 'width: 100%; height: 100%; object-fit: cover;';
                thumbnailDiv.appendChild(img);
            };
            reader.readAsDataURL(file);
        } else if (isText) {
            thumbnailDiv.innerHTML = '<span style="font-size: 24px;">📄</span>';
        } else {
            thumbnailDiv.innerHTML = '<span style="font-size: 24px;">📎</span>';
        }

        // File info
        const infoDiv = document.createElement('div');
        infoDiv.style.cssText = 'flex: 1; min-width: 0;';
        const fileName = document.createElement('div');
        fileName.textContent = file.name;
        fileName.style.cssText = 'font-size: 14px; color: #fff; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;';
        const fileSize = document.createElement('div');
        fileSize.textContent = (file.size / 1024).toFixed(1) + ' KB';
        fileSize.style.cssText = 'font-size: 12px; color: rgba(255,255,255,0.6);';
        infoDiv.appendChild(fileName);
        infoDiv.appendChild(fileSize);

        // Remove button
        const removeBtn = document.createElement('button');
        removeBtn.innerHTML = '×';
        removeBtn.style.cssText = 'width: 24px; height: 24px; border-radius: 50%; border: none; background: rgba(255,255,255,0.2); color: #fff; cursor: pointer; font-size: 18px; margin-left: 10px;';
        removeBtn.onclick = () => {
            previewItem.remove();
            const index = this.attachedFiles.indexOf(file);
            if (index > -1) {
                this.attachedFiles.splice(index, 1);
            }
            console.log(`📎 Removed "${file.name}". Total files: ${this.attachedFiles.length}`);
        };

        previewItem.appendChild(thumbnailDiv);
        previewItem.appendChild(infoDiv);
        previewItem.appendChild(removeBtn);
        attachmentArea.appendChild(previewItem);

        console.log(`📸 Preview added for "${file.name}"`);
    },

    isValidUrl(string) {
        try {
            new URL(string);
            return true;
        } catch (_) {
            return false;
        }
    },

    async processImageWithOCR(file) {
        console.log('🖼️ Starting OCR process for file:', file.name);

        try {
            // Create image preview - wait for it to load
            await new Promise((resolve) => {
                const reader = new FileReader();
                reader.onload = async (e) => {
                    const imageUrl = e.target.result;
                    const fileSize = (file.size / 1024).toFixed(1) + ' KB';
                    const previewHtml =
                        '<div class="compact-preview-message">' +
                        '<img src="' + imageUrl + '" alt="' + file.name + '" class="compact-preview-img">' +
                        '<div class="compact-preview-info">' +
                        '<span class="compact-preview-name">' + file.name + '</span>' +
                        '<span class="compact-preview-type">' +
                        'Image • ' + fileSize +
                        '</span>' +
                        '</div>' +
                        '</div>';

                    Messages.addUserMessageWithHTML(previewHtml);

                    // Persist to chat store
                    if (typeof ChatStore !== 'undefined' && ChatStore.currentChatId) {
                        try {
                            await ChatStore.appendMessage(
                                ChatStore.currentChatId,
                                'user',
                                previewHtml,
                                { is_html: true, type: 'image_preview', filename: file.name }
                            );
                        } catch (err) { console.warn('Failed to persist image preview', err); }
                    }

                    resolve();
                };
                reader.readAsDataURL(file);
            });

            Messages.showLoading('Processing "' + file.name + '" with OCR and gathering evidence...');

            const formData = new FormData();
            formData.append('image', file);
            formData.append('analyze', 'true');  // Enable AI analysis
            formData.append('use_scraper', 'true');  // Enable scraper for evidence gathering

            console.log('📤 Sending "' + file.name + '" to OCR endpoint with scraper enabled...');

            const response = await fetch('http://127.0.0.1:8000/ocr_upload', {
                method: 'POST',
                body: formData
            });

            console.log('📥 OCR Response for "' + file.name + '":', response.status);

            if (!response.ok) {
                throw new Error('Server error: ' + response.status);
            }

            const result = await response.json();
            console.log('📊 OCR Result for "' + file.name + '":', result);

            Messages.hideLoading();

            if (result.success) {
                const { ocr_result, ai_analysis, evidence_count, evidence_sources } = result;

                // Log the extracted text to console but don't show to user
                console.log('📝 "' + file.name + '" - Text Extracted (' + ocr_result.confidence.toFixed(1) + '% confidence)');
                console.log('Text: ' + ocr_result.text);
                console.log('Words found: ' + ocr_result.word_count);
                console.log('Evidence sources: ' + evidence_count);

                // Show evidence sources if available
                if (evidence_sources && evidence_sources.length > 0) {
                    let evidenceMessage = '**📚 Evidence gathered from ' + evidence_count + ' source(s):**\n\n';
                    evidence_sources.forEach((source, idx) => {
                        evidenceMessage += (idx + 1) + '. **' + source.title + '**\n';
                        evidenceMessage += '   🔗 [' + source.domain + '](' + source.url + ')\n';
                        if (source.summary) {
                            evidenceMessage += '   📄 ' + source.summary.substring(0, 150) + '...\n';
                        }
                        evidenceMessage += '\n';
                    });
                    Messages.addAIMessage(evidenceMessage);
                    if (typeof ChatStore !== 'undefined' && ChatStore.currentChatId) {
                        ChatStore.appendMessage(ChatStore.currentChatId, 'assistant', evidenceMessage).catch(e => console.warn('Failed to persist evidence', e));
                    }
                }

                // Show AI analysis to user with file context
                if (ai_analysis) {
                    Messages.addAIMessage('**🔍 Fact-Checked Analysis of "' + file.name + '":**\n\n' + ai_analysis);
                    if (typeof ChatStore !== 'undefined' && ChatStore.currentChatId) {
                        ChatStore.appendMessage(ChatStore.currentChatId, 'assistant', '**🔍 Fact-Checked Analysis of "' + file.name + '":**\n\n' + ai_analysis).catch(e => console.warn('Failed to persist analysis', e));
                    }
                } else {
                    const msg = '✅ "' + file.name + '" processed successfully, but no analysis was generated.';
                    Messages.addAIMessage(msg);
                    if (typeof ChatStore !== 'undefined' && ChatStore.currentChatId) {
                        ChatStore.appendMessage(ChatStore.currentChatId, 'assistant', msg).catch(e => console.warn('Failed to persist success msg', e));
                    }
                }
            } else {
                const errorMsg = '❌ OCR Error for "' + file.name + '": ' + (result.error || 'Unknown error');
                Messages.addAIMessage(errorMsg);
                if (typeof ChatStore !== 'undefined' && ChatStore.currentChatId) {
                    ChatStore.appendMessage(ChatStore.currentChatId, 'assistant', errorMsg).catch(e => console.warn('Failed to persist error', e));
                }
            }

        } catch (error) {
            console.error('❌ OCR Error:', error);
            Messages.hideLoading();
            const failMsg = '❌ Failed to process image: ' + error.message;
            Messages.addAIMessage(failMsg);
            if (typeof ChatStore !== 'undefined' && ChatStore.currentChatId) {
                ChatStore.appendMessage(ChatStore.currentChatId, 'assistant', failMsg).catch(e => console.warn('Failed to persist catch error', e));
            }
        }
    },

    async processTextFile(file) {
        console.log('📄 Starting text file processing for:', file.name);

        try {
            Messages.showLoading('Reading "' + file.name + '"...');

            // Read file content
            const textContent = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = (e) => resolve(e.target.result);
                reader.onerror = () => reject(new Error('Failed to read file'));
                reader.readAsText(file);
            });

            Messages.hideLoading();

            const wordCount = textContent.split(/\s+/).filter(w => w.length > 0).length;

            // Display file info
            Messages.addUserMessage('📄 ' + file.name + ' (' + wordCount + ' words)');

            // Persist to chat store
            if (typeof ChatStore !== 'undefined' && ChatStore.currentChatId) {
                try {
                    await ChatStore.appendMessage(
                        ChatStore.currentChatId,
                        'user',
                        '📄 Uploaded ' + file.name + ' (' + wordCount + ' words)',
                        { type: 'text_file', filename: file.name }
                    );
                } catch (err) { console.warn('Failed to persist text file info', err); }
            }

            console.log('✅ Text extracted from ' + file.name + ': ' + wordCount + ' words');

        } catch (error) {
            console.error('❌ Text file error:', error);
            Messages.hideLoading();
            Messages.addAIMessage('❌ Failed to process text file: ' + error.message);
        }
    }
};
