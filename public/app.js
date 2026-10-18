// State
let allGifts = [];
let activeStatusFilter = 'all';
let activeCategoryFilter = 'all';
let searchQuery = '';
let currentImageIndices = {};

// Init
document.addEventListener('DOMContentLoaded', () => {
  fetchGifts();
});

// Fetch gifts from server
async function fetchGifts() {
  try {
    const res = await fetch('/api/gifts');
    if (!res.ok) throw new Error('Помилка завантаження даних');
    allGifts = await res.json();
    
    allGifts.forEach(g => {
      if (!(g.id in currentImageIndices)) {
        currentImageIndices[g.id] = 0;
      }
    });

    populateCategories();
    renderStats();
    renderGifts();
  } catch (err) {
    console.error('Fetch error:', err);
  }
}

// Populate Category Filter Dropdown
function populateCategories() {
  const select = document.getElementById('category-filter');
  const currentVal = select.value;
  const categories = [...new Set(allGifts.map(g => g.category).filter(Boolean))].sort();

  select.innerHTML = '<option value="all">Усі категорії</option>';
  categories.forEach(cat => {
    const opt = document.createElement('option');
    opt.value = cat;
    opt.textContent = cat;
    select.appendChild(opt);
  });
  select.value = currentVal;
}

// Render Header Stats
function renderStats() {
  const total = allGifts.length;
  const reserved = allGifts.filter(g => g.reserved).length;
  const free = total - reserved;

  document.getElementById('stat-total').textContent = total;
  document.getElementById('stat-available').textContent = free;
  document.getElementById('stat-reserved').textContent = reserved;

  document.getElementById('tab-all').textContent = `Всі (${total})`;
  document.getElementById('tab-free').textContent = `✨ Вільні (${free})`;
  document.getElementById('tab-reserved').textContent = `🎁 Заброньовані (${reserved})`;

  const parentBadge = document.getElementById('parent-reserved-badge');
  if (parentBadge) parentBadge.textContent = reserved;
}

// Render Gifts Grid
function renderGifts() {
  const container = document.getElementById('gifts-container');
  const emptyState = document.getElementById('empty-state');

  const filtered = allGifts.filter(g => {
    if (activeStatusFilter === 'free' && g.reserved) return false;
    if (activeStatusFilter === 'reserved' && !g.reserved) return false;
    if (activeCategoryFilter !== 'all' && g.category !== activeCategoryFilter) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const matchTitle = g.title && g.title.toLowerCase().includes(q);
      const matchCat = g.category && g.category.toLowerCase().includes(q);
      const matchNote = g.note && g.note.toLowerCase().includes(q);
      if (!matchTitle && !matchCat && !matchNote) return false;
    }
    return true;
  });

  if (filtered.length === 0) {
    container.innerHTML = '';
    emptyState.classList.remove('hidden');
    return;
  }

  emptyState.classList.add('hidden');
  container.innerHTML = filtered.map(gift => renderGiftCard(gift)).join('');
}

// Render Single Gift Card
function renderGiftCard(gift) {
  const isReserved = Boolean(gift.reserved);
  const isJoke = Boolean(gift.isJoke);
  const isCrypto = Boolean(gift.isCrypto);
  const currentIdx = currentImageIndices[gift.id] || 0;
  const images = (gift.images && gift.images.length > 0) ? gift.images : [
    'https://via.placeholder.com/600x600/fdf2f4/be185d?text=Alisa'
  ];
  const activeImg = images[currentIdx] || images[0];
  const hasMultipleImages = images.length > 1;

  return `
    <article class="gift-card bg-white rounded-3xl overflow-hidden border ${isReserved ? 'border-brand-200 bg-rose-50/20' : (isJoke ? 'border-amber-200 bg-amber-50/10' : 'border-rose-100/70')} flex flex-col relative" id="card-${gift.id}">
      
      <!-- Top Image Container (2 photos) -->
      <div class="relative w-full aspect-square bg-gray-50/50 overflow-hidden group select-none">
        
        <img 
          id="img-${gift.id}" 
          src="${activeImg}" 
          alt="${gift.title}" 
          onclick="openLightbox('${gift.id}')"
          class="w-full h-full object-contain p-4 transition-transform duration-300 group-hover:scale-105 cursor-pointer"
          loading="lazy"
          onerror="this.onerror=null; this.src='https://via.placeholder.com/600x600/fdf2f4/be185d?text=Фото+товару';"
        />

        <!-- Category Tag -->
        <div class="absolute top-3 left-3 z-10 flex flex-col gap-1 items-start">
          <span class="px-2.5 py-1 rounded-full text-[10px] sm:text-[11px] font-bold ${isJoke ? 'bg-amber-100 text-amber-800 border border-amber-200' : (isCrypto ? 'bg-indigo-100 text-indigo-800 border border-indigo-200' : 'bg-white/95 text-gray-700 border border-gray-100')} shadow-sm backdrop-blur-md">
            ${isJoke ? '👑 Прикол' : (isCrypto ? '🪙 Інвестиція' : (gift.category || 'Подарунок'))}
          </span>
        </div>

        <!-- Status Badge -->
        <div class="absolute top-3 right-3 z-10">
          ${isReserved ? `
            <span class="px-2.5 py-1 rounded-full text-[11px] font-extrabold bg-brand-500 text-white shadow-sm flex items-center gap-1">
              <span>🔒</span> Зарезервовано
            </span>
          ` : `
            <span class="px-2.5 py-1 rounded-full text-[11px] font-extrabold bg-emerald-500 text-white shadow-sm flex items-center gap-1">
              <span>✨</span> Вільно
            </span>
          `}
        </div>

        <!-- Switch Image Arrows (if 2 photos) -->
        ${hasMultipleImages ? `
          <button 
            type="button"
            onclick="switchImage('${gift.id}', -1, event)" 
            class="absolute left-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-white/90 hover:bg-white text-gray-700 flex items-center justify-center shadow-md backdrop-blur-sm transition opacity-0 group-hover:opacity-100 z-10"
            title="Попереднє фото">
            ❮
          </button>
          <button 
            type="button"
            onclick="switchImage('${gift.id}', 1, event)" 
            class="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-white/90 hover:bg-white text-gray-700 flex items-center justify-center shadow-md backdrop-blur-sm transition opacity-0 group-hover:opacity-100 z-10"
            title="Наступне фото">
            ❯
          </button>

          <!-- 2 Dots Indicator -->
          <div class="absolute bottom-3 left-1/2 -translate-x-1/2 flex items-center gap-1.5 z-10 bg-black/35 backdrop-blur-md px-2.5 py-1 rounded-full">
            <span onclick="setImageIndex('${gift.id}', 0, event)" class="cursor-pointer photo-dot ${currentIdx === 0 ? 'active' : ''}"></span>
            <span onclick="setImageIndex('${gift.id}', 1, event)" class="cursor-pointer photo-dot ${currentIdx === 1 ? 'active' : ''}"></span>
            <span class="text-[10px] text-white/90 font-bold ml-1">${currentIdx + 1}/2</span>
          </div>
        ` : ''}

        <!-- Zoom hint -->
        <button 
          onclick="openLightbox('${gift.id}')" 
          class="absolute bottom-3 right-3 w-7 h-7 rounded-full bg-white/90 hover:bg-white text-gray-600 flex items-center justify-center shadow-sm text-xs opacity-0 group-hover:opacity-100 transition z-10" 
          title="Збільшити фото">
          🔍
        </button>
      </div>

      <!-- Card Body -->
      <div class="p-5 flex-1 flex flex-col justify-between">
        
        <div>
          <!-- Title -->
          <div class="mb-2">
            <h3 class="font-heading text-base font-bold text-gray-900 leading-snug line-clamp-2" title="${gift.title}">
              ${gift.title}
            </h3>
          </div>

          <!-- Price -->
          <div class="mb-2.5">
            <span class="inline-block text-base sm:text-lg font-extrabold ${isJoke ? 'text-amber-700' : 'text-brand-600'}">
              ${gift.price || 'Дивіться на сайті'}
            </span>
          </div>

          <!-- Note -->
          ${gift.note ? `
            <div class="mb-3.5 text-xs font-medium px-3 py-1.5 rounded-xl ${gift.note.includes('розмір') ? 'bg-rose-50 text-brand-800 border border-brand-200' : (isJoke ? 'bg-amber-50/80 text-amber-900 border border-amber-200/60' : 'bg-gray-50 text-gray-600 border border-gray-100')}">
              ${gift.note}
            </div>
          ` : ''}

          <!-- Store Link or Crypto Info -->
          <div class="mb-4">
            ${isCrypto ? `
              <button 
                onclick="openCryptoModal()" 
                class="inline-flex items-center gap-1.5 text-xs font-bold text-brand-600 hover:text-brand-800">
                <span>🪙 Як подарувати (звернутися до тата Максима)</span>
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"></path></svg>
              </button>
            ` : `
              <a 
                href="${gift.url}" 
                target="_blank" 
                rel="noopener noreferrer" 
                class="inline-flex items-center gap-1.5 text-xs font-bold text-gray-500 hover:text-brand-600 hover:underline">
                <span>🛍️ Переглянути в магазині</span>
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
              </a>
            `}
          </div>
        </div>

        <!-- Footer / Reservation Status & CTA -->
        <div class="pt-3 border-t border-rose-100/60">
          ${isReserved ? `
            <div class="bg-rose-50/70 border border-brand-100 rounded-2xl p-3 text-center">
              <p class="text-[11px] text-gray-400 font-medium">Зарезервовано гостем:</p>
              <p class="text-xs sm:text-sm font-bold text-brand-700 flex items-center justify-center gap-1">
                <span>🎁</span> ${gift.reservedBy || 'Хтось із гостей'}
              </p>
              ${gift.wishes ? `
                <p class="text-[11px] text-gray-500 italic mt-1 bg-white/80 rounded-lg p-1.5 border border-rose-50">
                  «${gift.wishes}»
                </p>
              ` : ''}
              <button 
                onclick="unreserveGift('${gift.id}', '${gift.title.replace(/'/g, "\\'")}')" 
                class="mt-2 text-[11px] text-gray-400 hover:text-brand-600 underline font-medium">
                Це ви бронювали? Скасувати бронь
              </button>
            </div>
          ` : `
            <button 
              onclick="openReserveModal('${gift.id}')" 
              class="w-full py-2.5 sm:py-3 px-4 rounded-2xl ${isJoke ? 'bg-amber-600 hover:bg-amber-700' : 'bg-brand-500 hover:bg-brand-600'} active:scale-[0.98] text-white text-xs sm:text-sm font-bold shadow-sm hover:shadow transition flex items-center justify-center gap-2">
              <span>🎁</span>
              <span>${isJoke ? 'Зарезервувати (якщо подужаєте 😄)' : 'Зарезервувати цей подарунок'}</span>
            </button>
          `}
        </div>

      </div>

    </article>
  `;
}

// Photo Switcher Logic
function switchImage(giftId, direction, event) {
  if (event) event.stopPropagation();
  const gift = allGifts.find(g => g.id === giftId);
  if (!gift || !gift.images || gift.images.length <= 1) return;

  const total = gift.images.length;
  let current = currentImageIndices[giftId] || 0;
  current = (current + direction + total) % total;
  currentImageIndices[giftId] = current;

  updateCardImage(giftId);
}

function setImageIndex(giftId, index, event) {
  if (event) event.stopPropagation();
  currentImageIndices[giftId] = index;
  updateCardImage(giftId);
}

function updateCardImage(giftId) {
  const gift = allGifts.find(g => g.id === giftId);
  if (!gift) return;

  const currentIdx = currentImageIndices[giftId] || 0;
  const imgEl = document.getElementById(`img-${giftId}`);
  if (imgEl && gift.images[currentIdx]) {
    imgEl.src = gift.images[currentIdx];
  }

  const card = document.getElementById(`card-${giftId}`);
  if (card) {
    const dots = card.querySelectorAll('.photo-dot');
    dots.forEach((dot, idx) => {
      if (idx === currentIdx) {
        dot.classList.add('active');
      } else {
        dot.classList.remove('active');
      }
    });
  }
}

// Lightbox
function openLightbox(giftId) {
  const gift = allGifts.find(g => g.id === giftId);
  if (!gift) return;
  const currentIdx = currentImageIndices[giftId] || 0;
  const imgUrl = gift.images[currentIdx] || gift.images[0];

  const modal = document.getElementById('lightbox-modal');
  const img = document.getElementById('lightbox-img');
  const caption = document.getElementById('lightbox-caption');

  img.src = imgUrl;
  caption.textContent = `${gift.title} (Фото ${currentIdx + 1} з ${gift.images.length})`;
  modal.classList.remove('hidden');
}

function closeLightbox() {
  document.getElementById('lightbox-modal').classList.add('hidden');
}

// Filter Handlers
function setStatusFilter(status) {
  activeStatusFilter = status;
  document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
  document.getElementById(`tab-${status}`).classList.add('active');
  renderGifts();
}

function setCategoryFilter(category) {
  activeCategoryFilter = category;
  renderGifts();
}

function setSearchQuery(query) {
  searchQuery = query.trim();
  renderGifts();
}

function resetFilters() {
  activeStatusFilter = 'all';
  activeCategoryFilter = 'all';
  searchQuery = '';
  document.getElementById('category-filter').value = 'all';
  document.getElementById('search-input').value = '';
  document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-all').classList.add('active');
  renderGifts();
}

// Reserve Modal Handlers
function openReserveModal(giftId) {
  const gift = allGifts.find(g => g.id === giftId);
  if (!gift) return;

  document.getElementById('reserve-gift-id').value = gift.id;
  document.getElementById('modal-gift-title').textContent = gift.title;
  document.getElementById('modal-gift-price').textContent = `${gift.price} • ${gift.category}`;
  document.getElementById('reserve-name').value = '';
  document.getElementById('reserve-wishes').value = '';

  const modal = document.getElementById('reserve-modal');
  modal.classList.remove('hidden');
  setTimeout(() => modal.classList.add('active'), 10);
  document.getElementById('reserve-name').focus();
}

function closeReserveModal() {
  const modal = document.getElementById('reserve-modal');
  modal.classList.remove('active');
  setTimeout(() => modal.classList.add('hidden'), 200);
}

// Crypto Modal Handlers
function openCryptoModal() {
  const modal = document.getElementById('crypto-modal');
  modal.classList.remove('hidden');
  setTimeout(() => modal.classList.add('active'), 10);
}

function closeCryptoModal() {
  const modal = document.getElementById('crypto-modal');
  modal.classList.remove('active');
  setTimeout(() => modal.classList.add('hidden'), 200);
}

// Parent Dashboard Modal
function openParentModal() {
  const modal = document.getElementById('parent-modal');
  const container = document.getElementById('parent-list-container');
  const reservedGifts = allGifts.filter(g => g.reserved);

  document.getElementById('parent-stats-text').textContent = 
    `Зарезервовано подарунків: ${reservedGifts.length} з ${allGifts.length}`;

  if (reservedGifts.length === 0) {
    container.innerHTML = `
      <div class="text-center py-10 text-gray-400">
        <p class="text-3xl mb-2">🎈</p>
        <p class="text-sm">Поки що жоден гість не зарезервував подарунок.</p>
      </div>
    `;
  } else {
    container.innerHTML = reservedGifts.map((g, idx) => `
      <div class="py-3 flex items-start justify-between gap-3">
        <div class="flex items-start gap-3">
          <span class="w-6 h-6 rounded-full bg-brand-50 text-brand-600 font-bold text-xs flex items-center justify-center shrink-0 mt-0.5">
            ${idx + 1}
          </span>
          <div>
            <h4 class="text-xs sm:text-sm font-bold text-gray-900">${g.title}</h4>
            <p class="text-[11px] text-brand-600 font-extrabold mt-0.5">${g.price}</p>
            <p class="text-xs text-gray-700 mt-1">
              <span class="font-bold text-gray-900">Зарезервував(ла):</span> ${g.reservedBy}
            </p>
            ${g.wishes ? `
              <p class="text-[11px] text-gray-500 italic mt-0.5">Побажання: «${g.wishes}»</p>
            ` : ''}
            ${g.reservedAt ? `
              <span class="text-[10px] text-gray-400 block mt-1">Час: ${g.reservedAt}</span>
            ` : ''}
          </div>
        </div>
        <button onclick="unreserveGift('${g.id}', '${g.title.replace(/'/g, "\\")}'); closeParentModal();" class="text-[11px] text-red-500 hover:text-red-700 font-semibold underline shrink-0">
          Звільнити
        </button>
      </div>
    `).join('');
  }

  modal.classList.remove('hidden');
  setTimeout(() => modal.classList.add('active'), 10);
}

function closeParentModal() {
  const modal = document.getElementById('parent-modal');
  modal.classList.remove('active');
  setTimeout(() => modal.classList.add('hidden'), 200);
}

// Submit Reservation
async function submitReservation(event) {
  event.preventDefault();
  const giftId = document.getElementById('reserve-gift-id').value;
  const name = document.getElementById('reserve-name').value.trim();
  const wishes = document.getElementById('reserve-wishes').value.trim();
  const submitBtn = document.getElementById('reserve-submit-btn');

  if (!name) {
    alert("Будь ласка, вкажіть ваше ім'я");
    return;
  }

  submitBtn.disabled = true;
  submitBtn.innerHTML = 'Бронюємо... ⏳';

  try {
    const res = await fetch('/api/reserve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: giftId, name, wishes })
    });

    const data = await res.json();
    if (!res.ok) {
      alert(data.error || 'Помилка при бронюванні');
      return;
    }

    closeReserveModal();

    if (typeof confetti === 'function') {
      confetti({
        particleCount: 110,
        spread: 70,
        origin: { y: 0.6 }
      });
    }

    allGifts = data.gifts;
    renderStats();
    renderGifts();

  } catch (err) {
    alert('Не вдалося з\'єднатися із сервером. Спробуйте ще раз.');
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = 'Підтвердити бронь ✨';
  }
}

// Unreserve Gift
async function unreserveGift(giftId, giftTitle) {
  if (!confirm(`Звільнити бронь для «${giftTitle}»? Подарунок знову стане доступним для всіх.`)) {
    return;
  }

  try {
    const res = await fetch('/api/unreserve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: giftId })
    });

    const data = await res.json();
    if (!res.ok) {
      alert(data.error || 'Помилка при скасуванні');
      return;
    }

    allGifts = data.gifts;
    renderStats();
    renderGifts();
  } catch (err) {
    alert('Не вдалося скасувати бронь.');
  }
}
