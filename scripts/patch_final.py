import pathlib, sys
sys.stdout.reconfigure(encoding="utf-8")
src = pathlib.Path("templates/marketplace/index.html")
txt = src.read_text(encoding="utf-8")

# ── chips section ──────────────────────────────────────────────────────────
cs = txt.find("3. ACTIVE FILTER")
cs = txt.rfind("{#", 0, cs)          # back up to the comment open
ce = txt.find("  {% endif %}", cs) + len("  {% endif %}")

NEW_CHIPS = """  {# ACTIVE FILTER CHIPS #}
  {% if selected_category or search or (sort and sort != 'price_asc') or district or min_price or max_price or availability %}
  <div class="container-app pt-3 pb-1">
    <div class="flex flex-wrap items-center gap-1.5">
      <span class="text-xs text-gray-500 font-semibold">Active:</span>
      {% if selected_category %}<span class="mp-chip">&#128194; {{ selected_category }}<a href="{{ url_for('marketplace.index', search=search, sort=sort, district=district, min_price=min_price, max_price=max_price, availability=availability) }}"><svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/></svg></a></span>{% endif %}
      {% if search %}<span class="mp-chip">&#128269; "{{ search }}"<a href="{{ url_for('marketplace.index', category=selected_category, sort=sort, district=district, min_price=min_price, max_price=max_price, availability=availability) }}"><svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/></svg></a></span>{% endif %}
      {% if district %}<span class="mp-chip">&#128205; {{ district }}<a href="{{ url_for('marketplace.index', category=selected_category, search=search, sort=sort, min_price=min_price, max_price=max_price, availability=availability) }}"><svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/></svg></a></span>{% endif %}
      {% if min_price or max_price %}<span class="mp-chip">Rs.{{ min_price or '0' }}-{{ max_price or 'Any' }}<a href="{{ url_for('marketplace.index', category=selected_category, search=search, sort=sort, district=district, availability=availability) }}"><svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/></svg></a></span>{% endif %}
      {% if sort and sort != 'price_asc' %}<span class="mp-chip">Sort: {{ 'Price: High to Low' if sort=='price_desc' else ('Nearest' if sort=='nearest' else 'Newest') }}<a href="{{ url_for('marketplace.index', category=selected_category, search=search, district=district, min_price=min_price, max_price=max_price, availability=availability) }}"><svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/></svg></a></span>{% endif %}
      {% if availability %}<span class="mp-chip">In stock<a href="{{ url_for('marketplace.index', category=selected_category, search=search, sort=sort, district=district, min_price=min_price, max_price=max_price) }}"><svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/></svg></a></span>{% endif %}
      <a href="{{ url_for('marketplace.index') }}" class="text-xs text-red-500 font-bold hover:underline ml-1">Clear all</a>
    </div>
  </div>
  {% endif %}"""

txt = txt[:cs] + NEW_CHIPS + txt[ce:]
print("OK chips:", cs, ce)

# ── grid section ───────────────────────────────────────────────────────────
gs = txt.find("4. MAIN PRODUCE GRID")
gs = txt.rfind("{#", 0, gs)
s6 = txt.find("6. MOBILE BOTTOM SHEET")
ge = txt.rfind("{#", 0, s6) - 1    # just before the section 6 comment

NEW_GRID = """  {# MAIN PRODUCE GRID #}
  <main class="container-app pt-6">
    <div class="flex items-center justify-between mb-5">
      <p class="text-sm font-semibold" style="color:#1F2A24">
        Showing <strong style="color:#2D6A4F">{{ products|length }}</strong> fresh listings
        {% if selected_category %} &mdash; <span style="color:#1B4332;font-weight:700">{{ selected_category }}</span>{% endif %}
        {% if district %} from <span style="color:#1B4332;font-weight:700">{{ district }}</span>{% endif %}
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
        <div style="font-size:4rem;margin-bottom:1.25rem">&#127806;</div>
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
print("OK grid:", gs, ge)

src.write_text(txt, encoding="utf-8")
print("DONE, total lines:", txt.count(chr(10)))
