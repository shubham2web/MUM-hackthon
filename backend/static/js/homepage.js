console.log('📦 homepage.js LOADED');

// DOM Elements - with null safety
const promptInput = document.getElementById('prompt');
console.log('🔍 promptInput element:', promptInput);
const loader = document.getElementById('loader');
const optionButtons = document.querySelectorAll('.option-btn[data-mode]');
const ctaButton = document.querySelector('.cta-button');
const attachBtn = document.getElementById('attachBtn');
const attachmentArea = document.getElementById('attachmentArea');
const sendBtn = document.getElementById('sendBtn');
const attachmentMenu = document.getElementById('attachmentMenu');
const uploadFileBtn = document.getElementById('uploadFileBtn');
const addLinkBtn = document.getElementById('addLinkBtn');
const linkModal = document.getElementById('linkModal');
const linkInput = document.getElementById('linkInput');
const submitLinkBtn = document.getElementById('submitLinkBtn');
const closeModalBtn = document.getElementById('closeModalBtn');
const errorModal = document.getElementById('errorModal');
const errorMessage = document.getElementById('errorMessage');
const errorOkBtn = document.getElementById('errorOkBtn');

// State
let currentMode = 'analytical';
let attachedFiles = [];

// REMOVE THE DUPLICATE ANIMATION CODE - it's now in inline script
// The animation is handled by inline script in homepage.html

// ===== INITIALIZATION =====
window.addEventListener('pageshow', function(event) {
    console.log('📄 Page show event');
    loader.style.opacity = '0';
    setTimeout(() => {
        loader.style.display = 'none';
    }, 500);
});

// Start animation as soon as DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(() => {
        initAnimatedTagline();
    }, 100);
});

// ===== ABOUT BUTTON HANDLER =====
function setupAboutButton() {
    const aboutLink = document.getElementById('aboutLink');
    console.log('🔗 About button found:', !!aboutLink);
    if (aboutLink) {
        aboutLink.addEventListener('click', (event) => {
            console.log('✅ About button clicked');
            event.preventDefault();
            window.location.href = '/about';
        });
        console.log('✅ About button event listener attached');
    } else {
        console.error('❌ About button NOT found with ID "aboutLink"');
    }
}

// Setup about button when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupAboutButton);
} else {
    setupAboutButton();
}

// ===== MODE SELECTION =====
optionButtons.forEach(button => {
    button.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        optionButtons.forEach(btn => btn.classList.remove('active'));
        button.classList.add('active');
        currentMode = button.dataset.mode;
    });
});

// Prevent CTA button from navigating, make it behave like send button
if (ctaButton) {
    ctaButton.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        handleSubmit();
    });
}

// ===== ATTACHMENT FUNCTIONS =====
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(2) + ' ' + units[i];
}

function createAttachmentPreview(file) {
    console.log('🖼️ Creating preview for:', file.name);
    attachedFiles.push(file);
    const previewId = `preview-${Date.now()}-${Math.random()}`;
    const previewItem = document.createElement('div');
    previewItem.className = 'preview-item';
    previewItem.id = previewId;

    // Check if it's an OCR file with originalFile
    const actualFile = file.originalFile || file;
    
    // Create thumbnail container
    const thumbnailDiv = document.createElement('div');
    thumbnailDiv.className = 'preview-thumbnail';
    
    if (actualFile.type && actualFile.type.startsWith('image/')) {
        const imageUrl = URL.createObjectURL(actualFile);
        const img = document.createElement('img');
        img.src = imageUrl;
        img.alt = 'preview';
        img.style.width = '100%';
        img.style.height = '100%';
        img.style.objectFit = 'cover';
        img.style.borderRadius = '6px';
        thumbnailDiv.appendChild(img);
        
        console.log('✅ Image preview created:', imageUrl);
        
        // No OCR badge display
    } else if (file.textData) {
        // Text file with extracted content
        thumbnailDiv.textContent = '📄';
        thumbnailDiv.style.fontSize = '24px';
        
        // Add text badge
        const badge = document.createElement('div');
        badge.className = 'ocr-badge';
        badge.title = `Text extracted: ${file.textData.wordCount} words`;
        badge.textContent = '✓ TXT';
        thumbnailDiv.appendChild(badge);
    } else if (file.type === 'link') {
        thumbnailDiv.textContent = '🔗';
        thumbnailDiv.style.fontSize = '24px';
    } else {
        thumbnailDiv.textContent = '📄';
        thumbnailDiv.style.fontSize = '24px';
    }

    const fileSize = file.size ? formatFileSize(file.size) : 'Link';

    // Create info container - simplified without details
    const infoDiv = document.createElement('div');
    infoDiv.className = 'preview-info';
    infoDiv.innerHTML = `
        <div class="preview-name">${file.name}</div>
    `;

    // Create close button
    const closeBtn = document.createElement('button');
    closeBtn.className = 'preview-close-btn';
    closeBtn.textContent = '×';
    closeBtn.addEventListener('click', () => {
        previewItem.remove();
        attachedFiles = attachedFiles.filter(f => f !== file);
        updateSendButtonState();
    });

    // Append all elements
    previewItem.appendChild(thumbnailDiv);
    previewItem.appendChild(infoDiv);
    previewItem.appendChild(closeBtn);
    
    attachmentArea.appendChild(previewItem);
    console.log('✅ Preview added to attachment area');

    updateSendButtonState();
}

// ===== ATTACHMENT MENU =====
attachBtn.addEventListener('click', (event) => {
    event.preventDefault();
    event.stopPropagation();
    attachmentMenu.style.display = 'block';
    attachmentMenu.style.visibility = 'hidden';

    const rect = attachBtn.getBoundingClientRect();
    const menuHeight = attachmentMenu.offsetHeight;

    attachmentMenu.style.top = `${rect.top + window.scrollY - menuHeight - 8}px`;
    attachmentMenu.style.left = `${rect.left + window.scrollX}px`;
    attachmentMenu.style.visibility = 'visible';
});

document.addEventListener('click', function(event) {
    if (attachmentMenu.style.display !== 'block') return;
    if (attachmentMenu.contains(event.target) || attachBtn.contains(event.target)) return;
    attachmentMenu.style.display = 'none';
});

// ===== FILE UPLOAD =====
uploadFileBtn.addEventListener('click', (event) => {
    event.preventDefault();
    event.stopPropagation();
    console.log('📁 Upload button clicked');
    attachmentMenu.style.display = 'none';
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.jpg,.jpeg,.png,.md,.txt,image/jpeg,image/png';
    input.multiple = true;

    input.onchange = async (e) => {
        e.preventDefault();
        console.log('📁 Files selected:', e.target.files.length);
        const files = Array.from(e.target.files);

        // Check total file count
        if (attachedFiles.length + files.length > 5) {
            showErrorModal(`You can upload a maximum of 5 files at a time. Currently selected: ${files.length}, Already attached: ${attachedFiles.length}`);
            return;
        }

        // Allowed file extensions - only jpg, jpeg, png, md, txt
        const allowedExtensions = ['.jpg', '.jpeg', '.png', '.md', '.txt'];

        // Validate and process each file
        for (const file of files) {
            console.log('📁 Processing file:', file.name, 'Type:', file.type, 'Size:', formatFileSize(file.size));
            
            // Check file format
            const fileName = file.name.toLowerCase();
            const isValidFormat = allowedExtensions.some(ext => fileName.endsWith(ext));
            
            if (!isValidFormat) {
                showErrorModal(`File format not supported: "${file.name}"\n\nSupported formats: JPG, JPEG, PNG, MD, TXT`);
                continue; // Skip this file but process others
            }
            
            // Check file size (5MB limit)
            if (file.size > 5 * 1024 * 1024) {
                showErrorModal(`File "${file.name}" exceeds the maximum size limit.\n\nFile size: ${formatFileSize(file.size)}\nMaximum allowed: 5 MB`);
                continue; // Skip this file but process others
            }
            
            // All supported formats (jpg, jpeg, png, md, txt) need text extraction
            const isImage = fileName.endsWith('.jpg') || fileName.endsWith('.jpeg') || fileName.endsWith('.png');
            const isTextFile = fileName.endsWith('.md') || fileName.endsWith('.txt');
            
            if (isImage) {
                console.log('🖼️ Image file detected, starting OCR...');
                await processImageWithOCR(file);
                console.log('✅ OCR processing completed for', file.name);
            } else if (isTextFile) {
                console.log('📄 Text file detected, extracting content...');
                await processTextFile(file);
                console.log('✅ Text extraction completed for', file.name);
            }
        }
        console.log('✅ All files processed, staying on homepage');
    };

    input.click();
});

// ===== TEXT FILE PROCESSING =====
async function processTextFile(file) {
    console.log('📄 Processing text file:', file.name);
    
    // Show loading
    loader.style.display = 'flex';
    setTimeout(() => loader.style.opacity = '1', 10);

    try {
        const reader = new FileReader();
        
        reader.onload = (e) => {
            const textContent = e.target.result;
            
            // Hide loading
            loader.style.opacity = '0';
            setTimeout(() => loader.style.display = 'none', 500);
            
            // Create a file object with extracted text
            const textFileData = {
                name: file.name,
                type: file.type,
                size: file.size,
                textData: {
                    extractedText: textContent,
                    wordCount: textContent.split(/\s+/).filter(w => w.length > 0).length
                },
                originalFile: file
            };
            // Also expose as ocrData so submit flow treats it as OCR result
            textFileData.ocrData = {
                extractedText: textContent,
                wordCount: textFileData.textData.wordCount,
                confidence: 100
            };
            
            // Add to preview
            createAttachmentPreview(textFileData);
            
            console.log(`✅ Text extracted from ${file.name}: ${textFileData.textData.wordCount} words`);
        };
        
        reader.onerror = () => {
            loader.style.opacity = '0';
            setTimeout(() => loader.style.display = 'none', 500);
            showErrorModal('Failed to read text file: ' + file.name);
        };
        
        reader.readAsText(file);
        
    } catch (error) {
        console.error('❌ Text file error:', error);
        showErrorModal('Failed to process text file: ' + error.message);
        loader.style.opacity = '0';
        setTimeout(() => loader.style.display = 'none', 500);
    }
}

// ===== OCR PROCESSING =====
async function processImageWithOCR(file) {
    console.log('🔍 processImageWithOCR started for:', file.name);
    console.log('📊 File details - Type:', file.type, 'Size:', file.size, 'Name:', file.name);
    console.log('🏠 Current location:', window.location.href);
    
    // Show loading
    loader.style.display = 'flex';
    setTimeout(() => loader.style.opacity = '1', 10);

    try {
        const formData = new FormData();
        formData.append('image', file);
        formData.append('analyze', 'false');  // Don't analyze yet, just extract text
        formData.append('question', '');

        console.log('📤 Sending OCR request for:', file.name);
        console.log('📤 FormData created with file:', file);
        
        const response = await fetch('/ocr_upload', {
            method: 'POST',
            body: formData
        });

        console.log('📥 OCR response received:', response.status, response.statusText);
        console.log('🏠 Location after fetch:', window.location.href);
        
        const result = await response.json();
        console.log('📊 OCR result:', result);

        // Hide loading
        loader.style.opacity = '0';
        setTimeout(() => loader.style.display = 'none', 500);

        if (result.success) {
            const extractedText = result.ocr_result.text;
            const confidence = result.ocr_result.confidence;

            console.log('✅ OCR successful! Words:', result.ocr_result.word_count, 'Confidence:', confidence);
            console.log('📝 Extracted text preview:', extractedText.substring(0, 100));

            // Create a simplified file object
            const ocrFile = {
                name: file.name,
                type: file.type,
                size: file.size,
                originalFile: file,
                ocrData: {
                    extractedText: result.ocr_result.text,
                    confidence: result.ocr_result.confidence,
                    wordCount: result.ocr_result.word_count
                }
            };

            // Add to preview like regular file
            console.log('📸 Adding preview for OCR file...');
            createAttachmentPreview(ocrFile);

            console.log(`✅ Complete! OCR extracted from ${file.name}: ${result.ocr_result.word_count} words (${confidence.toFixed(1)}% confidence)`);
            console.log('🏠 Staying on homepage - no redirect. Current URL:', window.location.href);
        } else {
            console.error('❌ OCR failed! Error:', result.error);
            showErrorModal('OCR failed: ' + (result.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('❌ OCR error caught:', error);
        console.error('❌ Error stack:', error.stack);
        showErrorModal('Failed to process image: ' + error.message);
        loader.style.opacity = '0';
        setTimeout(() => loader.style.display = 'none', 500);
    }
    
    console.log('🔍 processImageWithOCR completed for:', file.name);
    console.log('🏠 Final location:', window.location.href);
    
    // Explicitly prevent any navigation
    return false;
}

// ===== LINK MODAL =====
addLinkBtn.addEventListener('click', () => {
    attachmentMenu.style.display = 'none';
    linkModal.style.display = 'flex';
    linkInput.focus();
});

function hideLinkModal() {
    linkModal.style.display = 'none';
    linkInput.value = '';
}

closeModalBtn.addEventListener('click', hideLinkModal);

submitLinkBtn.addEventListener('click', () => {
    const url = linkInput.value.trim();
    if (isValidUrl(url)) {
        const hostname = new URL(url).hostname;
        const linkFile = { name: hostname, type: 'link', originalUrl: url, ocrData: { extractedText: url, wordCount: 0, confidence: 100 } };
        createAttachmentPreview(linkFile);
        hideLinkModal();
    } else {
        alert('Please enter a valid URL.');
    }
});

// ===== ERROR MODAL =====
function showErrorModal(message) {
    errorMessage.textContent = message;
    errorModal.style.display = 'flex';
}

errorOkBtn.addEventListener('click', () => {
    errorModal.style.display = 'none';
    // Don't redirect, just close the modal
});

// ===== FORM SUBMISSION =====
async function handleSubmit() {
    if (!promptInput) {
        console.error('❌ promptInput element not found!');
        return;
    }
    const promptValue = promptInput.value.trim();
    console.log('📝 promptValue:', promptValue);

    if (!promptValue && attachedFiles.length === 0) {
        return;
    }

    console.log('📤 Submitting from homepage:', promptValue);
    console.log('📤 Mode:', currentMode);
    console.log('📤 Attached files:', attachedFiles.length);

    // Check if any attached files have OCR/text/link data
    const ocrFiles = attachedFiles.filter(f => f.ocrData || f.textData || f.type === 'link');
    
    if (ocrFiles.length > 0) {
        // Store OCR results in sessionStorage (normalize fields)
        const ocrResults = ocrFiles.map(f => ({
            filename: f.name,
            extractedText: (f.ocrData && f.ocrData.extractedText) || (f.textData && f.textData.extractedText) || (f.originalUrl || ''),
            confidence: (f.ocrData && f.ocrData.confidence) || 100,
            wordCount: (f.ocrData && f.ocrData.wordCount) || (f.textData && f.textData.wordCount) || 0
        }));
        
        sessionStorage.setItem('ocrResults', JSON.stringify(ocrResults));
        console.log('✅ Stored OCR/text/link results for', ocrFiles.length, 'files');
    }

    // If user didn't type a prompt but attached a link, use the first link as initial prompt
    let finalPrompt = promptValue;
    if (!finalPrompt || finalPrompt.length === 0) {
        const firstLink = attachedFiles.find(f => f.type === 'link' && f.originalUrl);
        if (firstLink) finalPrompt = firstLink.originalUrl;
    }

    sessionStorage.setItem('initialPrompt', finalPrompt || '');
    sessionStorage.setItem('chatMode', currentMode);
    // Flag to tell chat page to create a brand new chat session
    sessionStorage.setItem('forceNewChat', 'true');

    console.log('✅ Stored in sessionStorage');
    console.log('✅ Redirecting to /chat with mode:', currentMode);
    console.log('✅ forceNewChat flag set - will create brand new chat');

    loader.style.display = 'flex';
    setTimeout(() => loader.style.opacity = '1', 10);

    // Navigate to chat page with mode parameter if debate mode is selected
    if (currentMode === 'debate') {
        window.location.href = '/chat?mode=debate';
    } else {
        window.location.href = '/chat';
    }
}

sendBtn.addEventListener('click', handleSubmit);

promptInput.addEventListener('keypress', function(event) {
    if (event.key === 'Enter') {
        event.preventDefault();
        handleSubmit();
    }
});

// ===== UTILITY FUNCTIONS =====
function isValidUrl(string) {
    try {
        new URL(string);
        return true;
    } catch (_) {
        return false;
    }
}

function updateSendButtonState() {
    sendBtn.disabled = (promptInput.value.trim().length === 0) && (attachedFiles.length === 0);
}

promptInput.addEventListener('input', updateSendButtonState);
updateSendButtonState();

// ===== VANTA FOG =====
let vantaFog = null;

if (window.innerWidth > 480 && typeof VANTA !== 'undefined') {
    vantaFog = VANTA.FOG({
        el: "#vanta-fog",
        highlightColor: 0xcfe6ff,
        midtoneColor: 0x6fa8ff,
        lowlightColor: 0x2f3f6a,
        baseColor: 0x000000,
        speed: 1,
        zoom: 0.2
    });
}

// ===== INITIALIZATION =====
window.addEventListener('pageshow', function(event) {
    loader.style.opacity = '0';
    setTimeout(() => {
        loader.style.display = 'none';
    }, 500);
});
