let allPages = [];
let currentPageIndex = 0;
let notesMap = {};

const pageContent = document.getElementById('pageContent');
const chapterInfo = document.getElementById('chapterInfo');
const pageIndicator = document.getElementById('pageIndicator');
const pageIndicatorTop = document.getElementById('pageIndicatorTop');
const prevBtn = document.getElementById('prevPage');
const nextBtn = document.getElementById('nextPage');
const prevBtnTop = document.getElementById('prevPageTop');
const nextBtnTop = document.getElementById('nextPageTop');
const notePopup = document.getElementById('notePopup');
const noteContent = document.getElementById('noteContent');
const chapterSelect = document.getElementById('chapterSelect');
const pageJumpInput = document.getElementById('pageJumpInput');
const pageJumpBtn = document.getElementById('pageJumpBtn');

function escapeHtml(text) {
    return text
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;');
}

function extractDefinedTerm(noteHtml) {
    const temporary = document.createElement('div');
    temporary.innerHTML = noteHtml || '';
    const plainText = (temporary.textContent || '').trim();
    const colonIndex = plainText.indexOf(':');
    return colonIndex > 0 ? plainText.substring(0, colonIndex).trim() : null;
}

function processAnnotations(text, notes) {
    let result = escapeHtml(text);
    const markers = [...result.matchAll(/(\S+?)\[\^(\d+)\]/g)];

    for (let index = markers.length - 1; index >= 0; index -= 1) {
        const match = markers[index];
        const noteNumber = Number(match[2]);
        if (!notes[noteNumber]) continue;

        let wordToHighlight = match[1];
        let punctuation = '';
        let startIndex = match.index;
        const definedTerm = extractDefinedTerm(notes[noteNumber]);

        if (definedTerm) {
            const escaped = definedTerm
                .replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
                .replace(/\s+/g, '\\s+');
            const termRegex = new RegExp(`(${escaped})([\\s.,;!?"'):]*)$`, 'i');
            const beforeMarker = result.substring(0, match.index + match[1].length);
            const termMatch = beforeMarker.match(termRegex);
            if (termMatch) {
                const matchedWithPunctuation = termMatch[1] + (termMatch[2] || '');
                wordToHighlight = termMatch[1];
                punctuation = termMatch[2] || '';
                startIndex = match.index + match[1].length - matchedWithPunctuation.length;
            }
        }

        const annotated = `<span class="annotated" data-note="${noteNumber}" role="button" tabindex="0">${wordToHighlight}</span>`;
        result = result.substring(0, startIndex)
            + annotated
            + punctuation
            + result.substring(match.index + match[0].length);
    }

    return result;
}

function displayPage() {
    if (!allPages.length) return;

    const page = allPages[currentPageIndex];
    notesMap = Object.fromEntries(page.notes.map((note) => [note.n, note.note_html]));
    chapterInfo.textContent = page.chapterTitle;
    pageIndicator.textContent = `Page ${page.pageNum}`;
    pageIndicatorTop.textContent = `Page ${page.pageNum}`;
    pageContent.innerHTML = processAnnotations(page.text, notesMap);

    const firstPage = currentPageIndex === 0;
    const lastPage = currentPageIndex === allPages.length - 1;
    [prevBtn, prevBtnTop].forEach((button) => { button.disabled = firstPage; });
    [nextBtn, nextBtnTop].forEach((button) => { button.disabled = lastPage; });

    document.querySelectorAll('.annotated').forEach((element) => {
        element.addEventListener('click', (event) => showNote(event, element));
        element.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                showNote(event, element);
            }
        });
    });

    hideNote();
    window.scrollTo({ top: 0, behavior: 'instant' });
    chapterSelect.value = String(page.chant);
    localStorage.setItem('odyssee:lastPageIndex', String(currentPageIndex));
}

function showNote(event, element) {
    event.stopPropagation();
    const noteHtml = notesMap[Number(element.dataset.note)];
    if (!noteHtml) return;

    noteContent.innerHTML = noteHtml;
    notePopup.classList.add('active');
    notePopup.setAttribute('aria-hidden', 'false');

    if (window.innerWidth <= 768) return;

    const rect = element.getBoundingClientRect();
    const popupWidth = Math.min(420, window.innerWidth - 32);
    notePopup.style.width = `${popupWidth}px`;
    notePopup.style.left = `${Math.max(16, Math.min(rect.left, window.innerWidth - popupWidth - 16))}px`;

    const popupHeight = notePopup.offsetHeight;
    const below = rect.bottom + 12;
    const top = below + popupHeight <= window.innerHeight
        ? below
        : Math.max(16, rect.top - popupHeight - 12);
    notePopup.style.top = `${top}px`;
}

function hideNote() {
    notePopup.classList.remove('active');
    notePopup.setAttribute('aria-hidden', 'true');
    notePopup.removeAttribute('style');
}

function goToPage(index) {
    if (index < 0 || index >= allPages.length) return;
    currentPageIndex = index;
    displayPage();
}

function populateChapterSelect() {
    const chapters = new Map();
    allPages.forEach((page) => chapters.set(page.chant, page.chapterTitle));
    chapterSelect.innerHTML = '';
    chapters.forEach((title, chant) => {
        const option = document.createElement('option');
        option.value = String(chant);
        option.textContent = title;
        chapterSelect.appendChild(option);
    });
}

function jumpToPrintedPage(pageNumber) {
    const target = allPages.findIndex((page) => page.pageNum === pageNumber);
    if (target === -1) {
        pageJumpInput.setCustomValidity('Cette page ne figure pas dans le texte de l’Odyssée.');
        pageJumpInput.reportValidity();
        return;
    }
    pageJumpInput.setCustomValidity('');
    pageJumpInput.value = '';
    goToPage(target);
}

prevBtn.addEventListener('click', () => goToPage(currentPageIndex - 1));
prevBtnTop.addEventListener('click', () => goToPage(currentPageIndex - 1));
nextBtn.addEventListener('click', () => goToPage(currentPageIndex + 1));
nextBtnTop.addEventListener('click', () => goToPage(currentPageIndex + 1));

chapterSelect.addEventListener('change', () => {
    const chant = Number(chapterSelect.value);
    goToPage(allPages.findIndex((page) => page.chant === chant));
});

pageJumpBtn.addEventListener('click', () => {
    if (pageJumpInput.value) jumpToPrintedPage(Number(pageJumpInput.value));
});
pageJumpInput.addEventListener('input', () => pageJumpInput.setCustomValidity(''));
pageJumpInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') pageJumpBtn.click();
});

document.addEventListener('click', (event) => {
    if (!notePopup.contains(event.target)) hideNote();
});
document.addEventListener('keydown', (event) => {
    if (event.target === pageJumpInput || event.target === chapterSelect) return;
    if (event.key === 'ArrowRight') goToPage(currentPageIndex + 1);
    if (event.key === 'ArrowLeft') goToPage(currentPageIndex - 1);
    if (event.key === 'Escape') hideNote();
});

async function init() {
    try {
        const response = await fetch('text_data/Odyssee.json');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        allPages = await response.json();
        populateChapterSelect();

        const savedIndex = Number(localStorage.getItem('odyssee:lastPageIndex'));
        if (Number.isInteger(savedIndex) && savedIndex >= 0 && savedIndex < allPages.length) {
            currentPageIndex = savedIndex;
        }
        displayPage();
    } catch (error) {
        console.error('Impossible de charger le livre :', error);
        pageContent.innerHTML = `
            <div class="error-message">
                <strong>Le texte n’a pas pu être chargé.</strong>
                <span>Lancez le site avec <code>python3 server.py</code>, puis ouvrez <a href="http://localhost:8000">localhost:8000</a>.</span>
            </div>`;
    }
}

init();
