import pathlib

src = pathlib.Path("templates/marketplace/index.html")
txt = src.read_text(encoding="utf-8")

# Replace active filter chips section
OLD_CHIPS = "  {# \u2500\u2500\u2500 3. ACTIVE FILTER CHIPS (IF ANY) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 #}"

s = txt.find(OLD_CHIPS)
# find the endif closing this block
e = txt.find("  {% endif %}", s) + len("  {% endif %}")

if s == -1:
    print("ERROR chips not found"); exit(1)

NEW_CHIPS = """  {# ACTIVE FILTER CHIPS #}
  {% if selected_category or search or (sort and sort != 'price_asc') or district or min_price or max_price or availability %}
  <div class="container-app pt-3 pb-1">
    <div class="flex flex-wrap items-center gap-1.5">
      <span class="text-xs text-gray-500 font-semibold">Active:</span>
      {% if selected_category %}<span class="mp-chip">&#128194; {{ selected_category }} <a href="{{ url_for('marketplace.index', search=search, sort=sort, district=district, min_price=min_price, max_price=max_price, availability=availability) }}"><svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/></svg></a></span>{% endif %}
      {% if search %}<span class="mp-chip">&#128269; &#34;{{ search }}&#34; <a href="{{ url_for('marketplace.index', category=selected_category, sort=sort, district=district, min_price=min_price, max_price=max_price, availability=availability) }}"><svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/></svg></a></span>{% endif %}
      {% if district %}<span class="mp-chip">&#128205; {{ district }} <a href="{{ url_for('marketplace.index', category=selected_category, search=search, sort=sort, min_price=min_price, max_price=max_price, availability=availability) }}"><svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/></svg></a></span>{% endif %}
      {% if min_price or max_price %}<span class="mp-chip">Rs.{{ min_price or '0' }}&ndash;{{ max_price or 'Any' }} <a href="{{ url_for('marketplace.index', category=selected_category, search=search, sort=sort, district=district, availability=availability) }}"><svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/></svg></a></span>{% endif %}
      {% if sort and sort != 'price_asc' %}<span class="mp-chip">&#8597; {{ 'Price&#8595;' if sort=='price_desc' else ('Nearest' if sort=='nearest' else 'Newest') }} <a href="{{ url_for('marketplace.index', category=selected_category, search=search, district=district, min_price=min_price, max_price=max_price, availability=availability) }}"><svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/></svg></a></span>{% endif %}
      {% if availability %}<span class="mp-chip">&#9989; In stock <a href="{{ url_for('marketplace.index', category=selected_category, search=search, sort=sort, district=district, min_price=min_price, max_price=max_price) }}"><svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/></svg></a></span>{% endif %}
      <a href="{{ url_for('marketplace.index') }}" class="text-xs text-red-500 font-bold hover:underline ml-1">Clear all</a>
    </div>
  </div>
  {% endif %}"""

txt = txt[:s] + NEW_CHIPS + txt[e:]

# Replace the main grid section
OLD_GRID_MARKER = "  {# \u2500\u2500\u2500 4. MAIN PRODUCE GRID \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 #}"
GRID_END_MARKER  = "\n{# \u2500\u2500\u2500 6. MOBILE BOTTOM SHEET"

gs = txt.find(OLD_GRID_MARKER)
ge = txt.find(GRID_END_MARKER, gs)

if gs == -1:
    print("ERROR grid not found"); exit(1)

NEW_GRID = """  {# MAIN PRODUCE GRID #}
  <main class="container-app pt-6">
    <div class="flex items-center justify-between mb-5">
      <p class="text-sm font-semibold" style="color:#1F2A24">
        Showing <strong style="color:#2D6A4F">{{ products|length }}</strong> fresh listings
        {% if selected_category %} &mdash; <span style="color:#1B4332">{{ selected_category }}</span>{% endif %}
        {% if district %} from <span style="color:#1B4332">{{ district }}</span>{% endif %}
      </p>
      {% if selected_category or search or district or min_price or max_price or availability %}
      <a href="{{ url_for('marketplace.index') }}" class="text-xs text-red-500 font-semibold hover:underline">Clear all</a>
      {% endif %}
    </div>

    {% if products %}
      <div class="grid-marketplace">
        {% for product in products %}
          {{ cards.product_card(product) }}
        {% endfor %}
      </div>
    {% else %}
      <div class="text-center py-20 px-6 max-w-sm mx-auto">
        <div class="text-6xl mb-5">&#127806;</div>
        <h2 class="font-bold text-xl mb-2" style="color:#1F2A24">No produce found</h2>
        <p class="text-sm mb-6 leading-relaxed" style="color:#567361">
          {% if selected_category or search or district or min_price or max_price %}
            No listings match your current filters. Try broadening your search.
          {% else %}
            The marketplace is being stocked. Check back soon!
          {% endif %}
        </p>
        <div class="flex flex-col sm:flex-row items-center justify-center gap-3">
          <a href="{{ url_for('marketplace.index') }}" class="btn-primary text-sm py-2.5 px-5">Reset Filters</a>
          {% if current_user.is_authenticated and current_user.role == 'farmer' %}
          <a href="{{ url_for('marketplace.list_product') }}" class="btn-secondary text-sm py-2.5 px-5">List Produce</a>
          {% endif %}
        </div>
      </div>
    {% endif %}
  </main>

</div>

"""

txt = txt[:gs] + NEW_GRID + txt[ge:]
src.write_text(txt, encoding="utf-8")
print("OK chips+grid replaced")
