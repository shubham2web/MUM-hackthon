console.log('📦 homepage.js LOADED');

// DOM Elements
const promptInput = document.getElementById('prompt');
const loader = document.getElementById('loader');
const optionButtons = document.querySelectorAll('.option-btn[data-mode]');
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

// ===== MODE SELECTION =====
optionButtons.forEach(button => {
    button.addEventListener('click', () => {
        optionButtons.forEach(btn => btn.classList.remove('active'));
        button.classList.add('active');
        currentMode = button.dataset.mode;
    });
});

// ===== ATTACHMENT FUNCTIONS =====
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(2) + ' ' + units[i];
}

function createAttachmentPreview(file) {
    attachedFiles.push(file);
    const previewId = `preview-${Date.now()}`;
    const previewItem = document.createElement('div');
    previewItem.className = 'preview-item';
    previewItem.id = previewId;

    let thumbnailHTML = '';
    if (file.type && file.type.startsWith('image/')) {
        thumbnailHTML = `<img src="${URL.createObjectURL(file)}" alt="preview" class="preview-thumbnail">`;
    } else if (file.type === 'link') {
        thumbnailHTML = `<div class="preview-thumbnail">🔗</div>`;
    } else {
        thumbnailHTML = `<div class="preview-thumbnail">📄</div>`;
    }

    const fileSize = file.size ? formatFileSize(file.size) : 'Link';

    previewItem.innerHTML = `
        ${thumbnailHTML}
        <div class="preview-info">
            <div class="preview-name">${file.name}</div>
            <div class="preview-details">${fileSize}</div>
        </div>
        <button class="preview-close-btn" data-preview-id="${previewId}">×</button>
    `;

    attachmentArea.appendChild(previewItem);

    previewItem.querySelector('.preview-close-btn').addEventListener('click', () => {
        previewItem.remove();
        attachedFiles = attachedFiles.filter(f => f !== file);
        updateSendButtonState();
    });

    updateSendButtonState();
}

// ===== ATTACHMENT MENU =====
attachBtn.addEventListener('click', (event) => {
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
uploadFileBtn.addEventListener('click', () => {
    attachmentMenu.style.display = 'none';
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*,.pdf,.doc,.docx,.txt';
    input.multiple = true;

    input.onchange = (e) => {
        const files = Array.from(e.target.files);

        if (attachedFiles.length + files.length > 5) {
            showErrorModal("Sorry, You can upload maximum 5 files");
            return;
        }

        files.forEach(file => {
            if (file.size > 10 * 1024 * 1024) {
                showErrorModal(`${file.name} - Maximum Size allowed 10MB`);
            } else {
                createAttachmentPreview(file);
            }
        });
    };

    input.click();
});

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
        const linkFile = { name: hostname, type: 'link', originalUrl: url };
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
    window.location.href = "./homepage.html";
});

// ===== FORM SUBMISSION =====
async function handleSubmit() {
    const promptValue = promptInput.value.trim();

    if (!promptValue && attachedFiles.length === 0) {
        return;
    }

    console.log('📤 Submitting from homepage:', promptValue);
    console.log('📤 Mode:', currentMode);

    sessionStorage.setItem('initialPrompt', promptValue);
    sessionStorage.setItem('chatMode', currentMode);

    console.log('✅ Stored in sessionStorage');
    console.log('✅ Redirecting to /chat...');

    loader.style.display = 'flex';
    setTimeout(() => loader.style.opacity = '1', 10);

    window.location.href = '/chat';
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
