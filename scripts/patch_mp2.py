import pathlib

src = pathlib.Path("templates/marketplace/index.html")
txt = src.read_text(encoding="utf-8")

# Find the content block opening line and replace everything up to </header>
HERO_MARKER = '<div class="bg-canvas min-h-screen pb-16">'
HEADER_END   = '  </header>\n'

s = txt.find(HERO_MARKER)
e = txt.find(HEADER_END, s) + len(HEADER_END)

if s == -1:
    print("ERROR hero marker not found"); exit(1)

NEW_HERO = '''<div class="min-h-screen pb-16" style="background:#F4F8F2">

  {# HERO BANNER #}
  <header class="mp-hero">
    <div class="mp-bubble" style="width:340px;height:340px;top:-100px;right:-80px;animation-delay:0s"></div>
    <div class="mp-bubble" style="width:200px;height:200px;bottom:-50px;left:4%;animation-delay:4s"></div>
    <div class="mp-bubble" style="width:130px;height:130px;top:30%;left:42%;animation-delay:7s"></div>
    <div class="container-app relative" style="z-index:2">
      <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-8">
        <div class="max-w-2xl">
          <div class="mp-badge mb-5">
            <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"/>
            </svg>
            Islandwide Wholesale &amp; Retail Marketplace
          </div>
          <h1 class="font-display font-extrabold text-3xl sm:text-4xl lg:text-5xl tracking-tight mb-3">
            Direct Farm Produce
          </h1>
          <p class="text-base sm:text-lg leading-relaxed mb-7">
            Browse genuine harvests from <strong class="text-green-200">verified Sri Lankan growers</strong>
            across 25 districts &mdash; farm-fresh prices, zero intermediary markups.
          </p>
          <form id="hero-search-form" method="GET" action="{{ url_for(\'marketplace.index\') }}">
            {% if selected_category %}<input type="hidden" name="category" value="{{ selected_category }}">{% endif %}
            {% if sort and sort != \'price_asc\' %}<input type="hidden" name="sort" value="{{ sort }}">{% endif %}
            {% if district %}<input type="hidden" name="district" value="{{ district }}">{% endif %}
            {% if min_price %}<input type="hidden" name="min_price" value="{{ min_price }}">{% endif %}
            {% if max_price %}<input type="hidden" name="max_price" value="{{ max_price }}">{% endif %}
            {% if availability %}<input type="hidden" name="availability" value="{{ availability }}">{% endif %}
            <div class="mp-sw">
              <div class="relative flex-1">
                <span class="mp-si">
                  <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                  </svg>
                </span>
                <input type="search" name="search" value="{{ search }}" autocomplete="off"
                       placeholder="Search produce (Tomato, Samba Rice, Ginger...)">
              </div>
              <button type="submit" class="mp-sb">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                </svg>
                Search
              </button>
            </div>
          </form>
        </div>
        <div class="flex flex-col items-start lg:items-end gap-3 shrink-0">
          {% if current_user.is_authenticated and current_user.role == \'farmer\' %}
          <a href="{{ url_for(\'marketplace.list_product\') }}" class="mp-hero-cta">
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
            </svg>
            List New Produce
          </a>
          {% elif not current_user.is_authenticated %}
          <a href="{{ url_for(\'auth.register\') }}" class="mp-hero-cta">
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
            </svg>
            Register as Farmer
          </a>
          <a href="{{ url_for(\'auth.login\') }}"
             class="text-green-200 text-sm font-semibold hover:text-white underline-offset-2 hover:underline">
            Already have an account? Sign in &rarr;
          </a>
          {% endif %}
        </div>
      </div>
    </div>
  </header>

  {# TRUST STATS BAR #}
  <div class="mp-stats">
    <div class="container-app">
      <div class="flex overflow-x-auto no-scrollbar">
        <div class="mp-stat"><div class="mp-stat-ic">&#127806;</div><div><div class="mp-stat-n">{{ products|length }}+</div><div class="mp-stat-l">Active listings</div></div></div>
        <div class="mp-stat"><div class="mp-stat-ic">&#128205;</div><div><div class="mp-stat-n">25</div><div class="mp-stat-l">Districts</div></div></div>
        <div class="mp-stat"><div class="mp-stat-ic">&#9989;</div><div><div class="mp-stat-n">100%</div><div class="mp-stat-l">Verified growers</div></div></div>
        <div class="mp-stat"><div class="mp-stat-ic">&#128683;</div><div><div class="mp-stat-n">Zero</div><div class="mp-stat-l">Hidden fees</div></div></div>
        <div class="mp-stat"><div class="mp-stat-ic">&#129309;</div><div><div class="mp-stat-n">Direct</div><div class="mp-stat-l">Farm to table</div></div></div>
      </div>
    </div>
  </div>
'''
txt = txt[:s] + NEW_HERO + txt[e:]
src.write_text(txt, encoding="utf-8")
print("OK hero+stats replaced")
