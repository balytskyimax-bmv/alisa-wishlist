// State
let allGifts = [];
let activeStatusFilter = 'all';
let activeCategoryFilter = 'all';
let searchQuery = '';
let currentImageIndices = {}; // giftId -> 0 or 1

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
    
    // Initialize current image index for each gift
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
  document.getElementById('tab-reserved').textContent = `🎁 Заброньовано (${reserved})`;
}

// Render Gifts Grid
function renderGifts() {
  const container = document.getElementById('gifts-container');
  const emptyState = document.getElementById('empty-state');

  // Filter
  const filtered = allGifts.filter(g => {
    // Status
    if (activeStatusFilter === 'free' && g.reserved) return false;
    if (activeStatusFilter === 'reserved' && !g.reserved) return false;
    // Category
    if (activeCategoryFilter !== 'all' && g.category !== activeCategoryFilter) return false;
    // Search
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
  const currentIdx = currentImageIndices[gift.id] || 0;
  const images = (gift.images && gift.images.length > 0) ? gift.images : [
    'https://via.placeholder.com/600x600/fdf2f4/be185d?text=Alisa'
  ];
  const activeImg = images[currentIdx] || images[0];
  const hasMultipleImages = images.length > 1;

  return `
    <article class="gift-card bg-white rounded-3xl overflow-hidden border ${isReserved ? 'border-brand-200 bg-pink-50/20' : 'border-gray-100'} shadow-sm flex flex-col relative" id="card-${gift.id}">
      
      <!-- Top Image Container (2 photos) -->
      <div class="relative w-full aspect-square bg-gray-50 overflow-hidden group select-none">
        
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
        <div class="absolute top-3 left-3 z-10">
          <span class="px-3 py-1 rounded-full text-[11px] font-bold bg-white/90 backdrop-blur-md text-gray-700 shadow-sm border border-gray-100">
            ${gift.category || 'Подарунок'}
          </span>
        </div>

        <!-- Status Badge -->
        <div class="absolute top-3 right-3 z-10">
          ${isReserved ? `
            <span class="px-3 py-1 rounded-full text-xs font-extrabold bg-brand-500 text-white shadow-md flex items-center gap-1">
              <span>🔒</span> Зарезервовано
            </span>
          ` : `
            <span class="px-3 py-1 rounded-full text-xs font-extrabold bg-emerald-500 text-white shadow-md flex items-center gap-1">
              <span>✨</span> Вільно
            </span>
          `}
        </div>

        <!-- Switch Image Arrows (if 2 photos) -->
        ${hasMultipleImages ? `
          <button 
            type="button"
            onclick="switchImage('${gift.id}', -1, event)" 
            class="absolute left-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-white/80 hover:bg-white text-gray-700 flex items-center justify-center shadow-md backdrop-blur-sm transition opacity-0 group-hover:opacity-100 z-10"
            title="Попереднє фото">
            ❮
          </button>
          <button 
            type="button"
            onclick="switchImage('${gift.id}', 1, event)" 
            class="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-white/80 hover:bg-white text-gray-700 flex items-center justify-center shadow-md backdrop-blur-sm transition opacity-0 group-hover:opacity-100 z-10"
            title="Наступне фото">
            ❯
          </button>

          <!-- 2 Dots Indicator -->
          <div class="absolute bottom-3 left-1/2 -translate-x-1/2 flex items-center gap-1.5 z-10 bg-black/30 backdrop-blur-md px-2.5 py-1 rounded-full">
            <span onclick="setImageIndex('${gift.id}', 0, event)" class="cursor-pointer photo-dot ${currentIdx === 0 ? 'active' : ''}"></span>
            <span onclick="setImageIndex('${gift.id}', 1, event)" class="cursor-pointer photo-dot ${currentIdx === 1 ? 'active' : ''}"></span>
            <span class="text-[10px] text-white/90 font-bold ml-1">${currentIdx + 1}/2</span>
          </div>
        ` : ''}

        <!-- Zoom hint -->
        <button 
          onclick="openLightbox('${gift.id}')" 
          class="absolute bottom-3 right-3 w-7 h-7 rounded-full bg-white/80 hover:bg-white text-gray-600 flex items-center justify-center shadow-sm text-xs opacity-0 group-hover:opacity-100 transition z-10" 
          title="Збільшити фото">
          🔍
        </button>
      </div>

      <!-- Card Body -->
      <div class="p-5 flex-1 flex flex-col justify-between">
        
        <div>
          <!-- Price & Title -->
          <div class="flex items-start justify-between gap-2 mb-2">
            <h3 class="font-heading text-base sm:text-lg font-bold text-gray-900 leading-snug line-clamp-2" title="${gift.title}">
              ${gift.title}
            </h3>
          </div>

          <div class="mb-3">
            <span class="inline-block text-lg font-extrabold text-brand-600">
              ${gift.price || 'Дивіться на сайті'}
            </span>
          </div>

          <!-- Special Note if exists -->
          ${gift.note ? `
            <div class="mb-4 text-xs font-semibold px-3 py-1.5 rounded-xl ${gift.note.includes('розмір') ? 'bg-amber-50 text-amber-800 border border-amber-200' : 'bg-pastel-sage text-emerald-800'}">
              ${gift.note}
            </div>
          ` : ''}

          <!-- Store Link -->
          <div class="mb-4">
            <a 
              href="${gift.url}" 
              target="_blank" 
              rel="noopener noreferrer" 
              class="inline-flex items-center gap-1.5 text-xs font-bold text-gray-500 hover:text-brand-600 hover:underline">
              <span>🛍️ Переглянути в магазині</span>
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
            </a>
          </div>
        </div>

        <!-- Footer / Reservation Status & CTA -->
        <div class="pt-3 border-t border-gray-100">
          ${isReserved ? `
            <div class="bg-brand-50/70 border border-brand-200/60 rounded-2xl p-3 text-center">
              <p class="text-xs text-gray-500 font-medium">Зарезервовано гостем:</p>
              <p class="text-sm font-bold text-brand-700 flex items-center justify-center gap-1">
                <span>🎁</span> ${gift.reservedBy || 'Хтось із гостей'}
              </p>
              ${gift.wishes ? `
                <p class="text-[11px] text-gray-500 italic mt-1 bg-white/70 rounded-lg p-1.5">
                  «${gift.wishes}»
                </p>
              ` : ''}
              <button 
                onclick="unreserveGift('${gift.id}', '${gift.title}')" 
                class="mt-2 text-[11px] text-gray-400 hover:text-brand-600 underline font-medium">
                Це ви бронювали? Скасувати бронь
              </button>
            </div>
          ` : `
            <button 
              onclick="openReserveModal('${gift.id}')" 
              class="w-full py-3 px-4 rounded-2xl bg-brand-500 hover:bg-brand-600 active:scale-[0.98] text-white text-sm font-bold shadow-md hover:shadow-lg transition flex items-center justify-center gap-2">
              <span>🎁</span>
              <span>Зарезервувати цей подарунок</span>
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

  // Update dots
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

// Modal Handlers
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

    // Trigger celebration confetti
    if (typeof confetti === 'function') {
      confetti({
        particleCount: 100,
        spread: 70,
        origin: { y: 0.6 }
      });
    }

    // Refresh gifts
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
