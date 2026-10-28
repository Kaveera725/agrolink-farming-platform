import pathlib, sys

src = pathlib.Path("templates/marketplace/index.html")
txt = src.read_text(encoding="utf-8")

# ── 1. Replace extra_head ──────────────────────────────────────────────────
OLD1 = """{% block extra_head %}
<style>
  /* Guaranteed Breakpoints: 1 col < 400px, 2 cols >= 400px, 3 cols >= 1024px, 4 cols >= 1280px */
  .grid-marketplace {
    display: grid;
    grid-template-columns: repeat(1, minmax(0, 1fr));
  }
  @media (min-width: 400px) {
    .grid-marketplace {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
  @media (min-width: 1024px) {
    .grid-marketplace {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
  }
  @media (min-width: 1280px) {
    .grid-marketplace {
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }
  }

  /* Hide scrollbar for category pills container */
  .no-scrollbar::-webkit-scrollbar { display: none; }
  .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
</style>
{% endblock %}"""

NEW1 = """{% block extra_head %}
<style>
  .grid-marketplace{display:grid;grid-template-columns:repeat(1,minmax(0,1fr));}
  @media(min-width:400px) {.grid-marketplace{grid-template-columns:repeat(2,minmax(0,1fr));}}
  @media(min-width:1024px){.grid-marketplace{grid-template-columns:repeat(3,minmax(0,1fr));}}
  @media(min-width:1280px){.grid-marketplace{grid-template-columns:repeat(4,minmax(0,1fr));}}
  .no-scrollbar::-webkit-scrollbar{display:none}
  .no-scrollbar{-ms-overflow-style:none;scrollbar-width:none}

  /* HERO */
  .mp-hero{position:relative;overflow:hidden;
    background:linear-gradient(135deg,#081c11 0%,#1B4332 28%,#2D6A4F 58%,#40916C 80%,#52B788 100%);
    padding:3.5rem 0 5.5rem;}
  .mp-hero::before{content:'';position:absolute;inset:0;opacity:.4;
    background:url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='%23ffffff' fill-opacity='0.04'%3E%3Ccircle cx='30' cy='30' r='10'/%3E%3C/g%3E%3C/svg%3E");}
  .mp-bubble{position:absolute;border-radius:50%;
    background:radial-gradient(circle,rgba(183,228,199,.15),transparent);
    animation:mpf 9s ease-in-out infinite;}
  @keyframes mpf{0%,100%{transform:translateY(0)}50%{transform:translateY(-22px)}}
  .mp-badge{display:inline-flex;align-items:center;gap:.5rem;
    padding:.375rem 1rem;border-radius:9999px;
    background:rgba(255,255,255,.13);border:1px solid rgba(255,255,255,.22);
    backdrop-filter:blur(6px);font-size:.75rem;font-weight:700;
    color:#D8F3DC;letter-spacing:.05em;text-transform:uppercase;}
  .mp-hero h1{color:#fff;text-shadow:0 2px 20px rgba(0,0,0,.2);}
  .mp-hero p{color:rgba(255,255,255,.78);}

  /* HERO SEARCH */
  .mp-sw{display:flex;overflow:hidden;border-radius:1rem;background:#fff;
    box-shadow:0 6px 32px rgba(0,0,0,.18);
    border:1.5px solid rgba(255,255,255,.2);transition:box-shadow 200ms;max-width:600px;}
  .mp-sw:focus-within{box-shadow:0 6px 36px rgba(82,183,136,.45);}
  .mp-sw input{flex:1;border:none;background:transparent;
    padding:.9375rem 1rem .9375rem 3.25rem;font-size:.9375rem;
    color:#1F2A24;outline:none;min-width:0;}
  .mp-sw input::placeholder{color:#9DB5A0;}
  .mp-si{position:absolute;left:1rem;top:50%;transform:translateY(-50%);
    color:#2D6A4F;pointer-events:none;}
  .mp-sb{background:linear-gradient(135deg,#1B4332,#2D6A4F);
    color:#fff;border:none;cursor:pointer;padding:0 1.75rem;
    font-size:.875rem;font-weight:700;flex-shrink:0;
    display:flex;align-items:center;gap:.5rem;transition:opacity 150ms;}
  .mp-sb:hover{opacity:.9;}
  .mp-hero-cta{display:inline-flex;align-items:center;gap:.625rem;
    padding:.75rem 1.5rem;border-radius:.875rem;font-size:.9375rem;font-weight:700;
    background:#fff;color:#1B4332;text-decoration:none;
    box-shadow:0 4px 20px rgba(0,0,0,.15);transition:all 180ms;}
  .mp-hero-cta:hover{transform:translateY(-2px);box-shadow:0 8px 28px rgba(0,0,0,.2);}

  /* STATS BAR */
  .mp-stats{background:#fff;border-bottom:1.5px solid #E2E8E0;
    box-shadow:0 2px 12px rgba(27,67,50,.07);}
  .mp-stat{display:flex;align-items:center;gap:.75rem;
    padding:.875rem 1.5rem;border-right:1px solid #F0F4EF;flex-shrink:0;}
  .mp-stat:last-child{border-right:none;}
  .mp-stat-ic{width:40px;height:40px;border-radius:.625rem;
    background:#F0FAF4;display:flex;align-items:center;
    justify-content:center;font-size:1.1875rem;}
  .mp-stat-n{font-size:1.125rem;font-weight:800;color:#1B4332;line-height:1.1;}
  .mp-stat-l{font-size:.6875rem;color:#567361;font-weight:500;margin-top:.1rem;}

  /* FILTER BAR */
  .mp-fbar{position:sticky;top:64px;z-index:30;
    background:rgba(255,255,255,.97);backdrop-filter:blur(12px);
    border-bottom:1.5px solid #E2E8E0;
    box-shadow:0 2px 8px rgba(27,67,50,.06);}

  /* CATEGORY PILLS */
  .mp-pill{display:inline-flex;align-items:center;gap:.5rem;
    padding:.5rem 1.125rem;border-radius:9999px;font-size:.8125rem;
    font-weight:600;white-space:nowrap;text-decoration:none;
    border:1.5px solid transparent;transition:all 180ms;}
  .mp-pill.off{background:#F7FAF5;color:#3D4F44;border-color:#E2E8E0;}
  .mp-pill.off:hover{background:#D8F3DC;border-color:#B7E4C7;
    color:#1B4332;transform:translateY(-1px);
    box-shadow:0 2px 10px rgba(27,67,50,.1);}
  .mp-pill.on{background:linear-gradient(135deg,#1B4332,#2D6A4F);
    color:#fff;box-shadow:0 2px 12px rgba(27,67,50,.25);}

  /* CARD HOVER LIFT */
  .grid-marketplace > *{border-radius:.875rem;overflow:hidden;
    transition:transform 200ms cubic-bezier(.4,0,.2,1),
               box-shadow 200ms cubic-bezier(.4,0,.2,1);}
  .grid-marketplace > *:hover{transform:translateY(-5px);
    box-shadow:0 14px 36px rgba(27,67,50,.14),
               0 2px 8px rgba(27,67,50,.08);}

  /* FILTER CHIPS */
  .mp-chip{display:inline-flex;align-items:center;gap:.375rem;
    padding:.25rem .75rem;border-radius:9999px;
    background:#D8F3DC;border:1px solid #B7E4C7;
    font-size:.75rem;font-weight:600;color:#1B4332;}
  .mp-chip a{color:#40916C;display:flex;align-items:center;margin-left:.125rem;}
  .mp-chip a:hover{color:#EF4444;}
</style>
{% endblock %}"""

if OLD1 in txt:
    txt = txt.replace(OLD1, NEW1, 1); print("OK extra_head")
else:
    print("SKIP extra_head: not found")

src.write_text(txt, encoding="utf-8")
print("STEP1 done")
