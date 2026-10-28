import pathlib

src = pathlib.Path("templates/marketplace/index.html")
txt = src.read_text(encoding="utf-8")

# Replace the old sticky search+filter section
OLD_SEC = '  {# ─── 2. STICKY SEARCH & FILTER BAR ───────────────────────────────────── #}'
SEC_END_MARKER = '    </div>\n  </section>'

s = txt.find(OLD_SEC)
e = txt.find(SEC_END_MARKER, s) + len(SEC_END_MARKER)
if s == -1:
    print("ERROR: filter section not found"); exit(1)

NEW_SEC = """  {# STICKY FILTER BAR #}
  <section class="mp-fbar">
    <div class="container-app py-3">
      {# Hidden compat form for mobile drawer #}
      <form id="marketplace-search-form" method="GET" action="{{ url_for('marketplace.index') }}" style="display:none">
        {% if selected_category %}<input type="hidden" name="category" value="{{ selected_category }}">{% endif %}
        {% if sort and sort != 'price_asc' %}<input type="hidden" name="sort" value="{{ sort }}">{% endif %}
        {% if district %}<input type="hidden" name="district" value="{{ district }}">{% endif %}
        {% if min_price %}<input type="hidden" name="min_price" value="{{ min_price }}">{% endif %}
        {% if max_price %}<input type="hidden" name="max_price" value="{{ max_price }}">{% endif %}
        {% if availability %}<input type="hidden" name="availability" value="{{ availability }}">{% endif %}
        <input type="search" id="marketplace-search" name="search" value="{{ search }}">
        <button type="button" id="clear-search-btn" {% if not search %}style="display:none"{% endif %}></button>
      </form>

      {# Mobile row #}
      <div class="flex md:hidden items-center justify-between mb-2.5">
        <span class="text-sm font-semibold" style="color:#1F2A24">
          <strong style="color:#2D6A4F">{{ products|length }}</strong> listings
        </span>
        {% set afc = 0 %}
        {% if sort and sort != 'price_asc' %}{% set afc = afc + 1 %}{% endif %}
        {% if district %}{% set afc = afc + 1 %}{% endif %}
        {% if min_price or max_price %}{% set afc = afc + 1 %}{% endif %}
        {% if availability %}{% set afc = afc + 1 %}{% endif %}
        <button type="button" id="open-filters-sheet-btn"
                class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold"
                style="background:#F0FAF4;color:#1B4332;border:1.5px solid #B7E4C7"
                aria-expanded="false" aria-controls="mobile-filters-drawer">
          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"/>
          </svg>
          Filters
          {% if afc > 0 %}
          <span style="width:18px;height:18px;border-radius:50%;background:#2D6A4F;color:#fff;font-size:10px;font-weight:700;display:inline-flex;align-items:center;justify-content:center">{{ afc }}</span>
          {% endif %}
        </button>
      </div>

      {# Category pills #}
      {% set cat_emojis = {'Vegetables':'🥦','Fruits':'🍎','Grains & Rice':'🌾','Spices':'🌶️','Pulses':'🫘','Roots & Tubers':'🥕','Other':'🛒'} %}
      <div class="flex items-center gap-2 overflow-x-auto no-scrollbar pb-1" role="navigation" aria-label="Product categories">
        <a href="{{ url_for('marketplace.index', search=search, sort=sort, district=district, min_price=min_price, max_price=max_price, availability=availability) }}"
           class="mp-pill flex-shrink-0 {% if not selected_category %}on{% else %}off{% endif %}">
          <span>🌿</span> All
        </a>
        {% for cat in categories %}
        <a href="{{ url_for('marketplace.index', category=cat, search=search, sort=sort, district=district, min_price=min_price, max_price=max_price, availability=availability) }}"
           class="mp-pill flex-shrink-0 {% if selected_category == cat %}on{% else %}off{% endif %}">
          <span>{{ cat_emojis.get(cat, '🌱') }}</span> {{ cat }}
        </a>
        {% endfor %}
      </div>

      {# Desktop filter row #}
      <div class="hidden md:flex items-center justify-between gap-4 pt-2.5 mt-2.5 border-t border-gray-100 text-xs">
        <form id="desktop-filters-form" method="GET" action="{{ url_for('marketplace.index') }}" class="flex flex-wrap items-center gap-3">
          {% if search %}<input type="hidden" name="search" value="{{ search }}">{% endif %}
          {% if selected_category %}<input type="hidden" name="category" value="{{ selected_category }}">{% endif %}
          <div class="flex items-center gap-1.5">
            <label for="desktop-sort" class="text-muted font-medium whitespace-nowrap">Sort:</label>
            <select id="desktop-sort" name="sort" onchange="this.form.submit()"
                    class="bg-canvas border border-bdr rounded-lg px-2.5 py-1.5 text-xs text-ink font-medium cursor-pointer focus:ring-1 focus:ring-leaf focus:border-leaf">
              <option value="price_asc" {% if sort == 'price_asc' %}selected{% endif %}>Price: Low to High</option>
              <option value="price_desc" {% if sort == 'price_desc' %}selected{% endif %}>Price: High to Low</option>
              <option value="newest" {% if sort == 'newest' %}selected{% endif %}>Newest First</option>
              <option value="nearest" {% if sort == 'nearest' %}selected{% endif %}>Nearest First</option>
            </select>
          </div>
          <div class="flex items-center gap-1.5">
            <label for="desktop-district" class="text-muted font-medium whitespace-nowrap">District:</label>
            <select id="desktop-district" name="district" onchange="this.form.submit()"
                    class="bg-canvas border border-bdr rounded-lg px-2.5 py-1.5 text-xs text-ink font-medium cursor-pointer max-w-[150px] focus:ring-1 focus:ring-leaf focus:border-leaf">
              <option value="">All Districts</option>
              {% for d in districts %}<option value="{{ d }}" {% if district == d %}selected{% endif %}>{{ d }}</option>{% endfor %}
            </select>
          </div>
          <div class="flex items-center gap-1.5">
            <span class="text-muted font-medium">Price:</span>
            <input type="number" name="min_price" value="{{ min_price }}" placeholder="Min Rs" min="0" step="0.01"
                   class="w-24 px-2 py-1.5 rounded-lg border border-bdr bg-canvas text-xs focus:ring-1 focus:ring-leaf focus:border-leaf"/>
            <span class="text-muted">&ndash;</span>
            <input type="number" name="max_price" value="{{ max_price }}" placeholder="Max Rs" min="0" step="0.01"
                   class="w-24 px-2 py-1.5 rounded-lg border border-bdr bg-canvas text-xs focus:ring-1 focus:ring-leaf focus:border-leaf"/>
            <button type="submit" class="btn-secondary text-[11px] py-1 px-2.5 h-[28px]">Apply</button>
          </div>
          <label class="inline-flex items-center gap-1.5 cursor-pointer ml-1 text-inksoft">
            <input type="checkbox" name="availability" value="in_stock"
                   {% if availability == 'in_stock' %}checked{% endif %}
                   onchange="this.form.submit()" class="checkbox w-4 h-4 rounded text-leaf"/>
            <span class="text-xs font-medium">In stock only</span>
          </label>
          <div class="hidden" data-filter-slot="nearest-first" aria-hidden="true"></div>
        </form>
        <div class="flex items-center gap-3">
          <span class="text-muted"><strong class="text-ink font-semibold">{{ products|length }}</strong> listings</span>
          {% if selected_category or search or (sort and sort != 'price_asc') or district or min_price or max_price or availability %}
          <a href="{{ url_for('marketplace.index') }}"
             class="text-red-500 hover:underline font-semibold flex items-center gap-1 text-xs">
            <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
            Reset
          </a>
          {% endif %}
        </div>
      </div>
    </div>
  </section>"""

txt = txt[:s] + NEW_SEC + txt[e:]
src.write_text(txt, encoding="utf-8")
print("OK filter bar replaced, lines:", txt.count(chr(10)))
