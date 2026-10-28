/**
 * AgroLink Google Maps Async Loader (static/js/maps-loader.js)
 * 
 * Recommended async pattern with dynamic library importing for 'maps', 'marker', and 'places'.
 * Loads Maps JavaScript API exactly once per page.
 * Exposes window.AgroMaps and the promise window.AgroMaps.ready.
 * Gracefully handles gm_authFailure and script load errors without breaking the page.
 */

(function (window, document) {
  'use strict';

  // Common Google Maps error messages and actionable guidance
  const ERROR_MESSAGES = {
    RefererNotAllowedMapError: {
      title: 'Referrer Not Allowed',
      message: 'This API key has HTTP referrer restrictions that do not allow requests from this URL. Add your local URL (e.g. http://localhost:5000/* and http://127.0.0.1:5000/*) to authorized website referrers in Google Cloud Console.'
    },
    ApiNotActivatedMapError: {
      title: 'API Not Activated',
      message: 'The required Google Maps API is not activated for this Google Cloud project. Enable Maps JavaScript API and Places API (New) in Google Cloud Console.'
    },
    BillingNotEnabledMapError: {
      title: 'Billing Not Enabled',
      message: 'Billing is not enabled on your Google Cloud project. Google Maps requires an active billing account linked to the project.'
    },
    InvalidKeyMapError: {
      title: 'Invalid API Key',
      message: 'The provided Google Maps browser API key is invalid or unrecognized.'
    },
    MissingKey: {
      title: 'Missing Browser API Key',
      message: 'Google Maps Browser Key (GOOGLE_MAPS_BROWSER_KEY) is not configured in .env.'
    },
    MissingMapId: {
      title: 'Missing Map ID',
      message: 'Google Maps Map ID (GOOGLE_MAPS_MAP_ID) is not configured in .env. A Map ID is required for Advanced Markers.'
    },
    NetworkError: {
      title: 'Network / Script Load Error',
      message: 'Failed to load Google Maps script. Check your internet connection or ad-blocker settings.'
    },
    AuthFailure: {
      title: 'Authentication Failure (gm_authFailure)',
      message: 'Google Maps authentication failed. Please verify your browser API key, HTTP referrer restrictions, and project billing.'
    }
  };

  // AgroMaps Global State
  const AgroMaps = {
    isLoaded: false,
    isLoading: false,
    authFailed: false,
    error: null,
    errorCode: null,
    libraries: {},
    mapId: null,
    ready: null,
    _resolveReady: null,
    _rejectReady: null
  };

  // Initialize the singleton ready promise
  AgroMaps.ready = new Promise((resolve, reject) => {
    AgroMaps._resolveReady = resolve;
    AgroMaps._rejectReady = reject;
  });

  // Helper: Return friendly error message object
  AgroMaps.getErrorMessage = function (code) {
    if (ERROR_MESSAGES[code]) {
      return ERROR_MESSAGES[code];
    }
    return {
      title: 'Google Maps Error',
      message: typeof code === 'string' ? code : 'An unexpected error occurred while loading Google Maps.'
    };
  };

  // Helper: Render user-friendly fallback notice
  AgroMaps.showNotice = function (container, errorTypeOrMessage, isManualFallback = true) {
    const target = typeof container === 'string' ? document.querySelector(container) : container;
    if (!target) return;

    let title = 'Map is unavailable';
    let text = typeof errorTypeOrMessage === 'string' ? errorTypeOrMessage : 'Please enter your location manually.';

    if (ERROR_MESSAGES[errorTypeOrMessage]) {
      const err = ERROR_MESSAGES[errorTypeOrMessage];
      title = err.title;
      text = err.message;
    }

    const noticeHtml = `
      <div class="rounded-xl border border-amber-200 bg-amber-50 p-4 text-amber-900 shadow-sm transition-all duration-200" role="alert" data-maps-alert>
        <div class="flex items-start gap-3">
          <svg class="h-5 w-5 flex-shrink-0 text-amber-600 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
          </svg>
          <div class="flex-1 text-sm">
            <h4 class="font-semibold text-amber-900">${title}</h4>
            <p class="mt-1 text-amber-800 leading-relaxed">${text}</p>
            ${isManualFallback ? '<p class="mt-2 text-xs font-semibold uppercase tracking-wider text-amber-700">Map is unavailable, enter your location manually</p>' : ''}
          </div>
        </div>
      </div>
    `;

    const existing = target.querySelector('[data-maps-alert]');
    if (existing) {
      existing.outerHTML = noticeHtml;
    } else {
      target.insertAdjacentHTML('afterbegin', noticeHtml);
    }
  };

  function dispatch(eventName, detail) {
    try {
      window.dispatchEvent(new CustomEvent(eventName, { detail }));
    } catch (e) {
      // safe fallback
    }
  }

  // Handle Google Maps authentication failure
  const previousAuthFailure = window.gm_authFailure;
  window.gm_authFailure = function () {
    AgroMaps.authFailed = true;
    AgroMaps.errorCode = 'AuthFailure';
    AgroMaps.error = ERROR_MESSAGES.AuthFailure.message;
    console.error('[AgroMaps] gm_authFailure: Google Maps API authentication failed.');

    document.querySelectorAll('.agro-map-container, [data-maps-container]').forEach(el => {
      AgroMaps.showNotice(el, 'AuthFailure');
    });

    dispatch('agromaps:authfailure', { code: 'AuthFailure', error: AgroMaps.error });
    dispatch('agromaps:error', { code: 'AuthFailure', error: AgroMaps.error });

    if (AgroMaps._rejectReady) {
      AgroMaps._rejectReady(new Error(AgroMaps.error));
    }

    if (typeof previousAuthFailure === 'function') {
      try {
        previousAuthFailure();
      } catch (e) {
        // preserve external handler
      }
    }
  };

  // Intercept window error events for known Google Maps JS error codes
  window.addEventListener('error', (event) => {
    const msg = event?.message || '';
    for (const code of ['RefererNotAllowedMapError', 'ApiNotActivatedMapError', 'BillingNotEnabledMapError', 'InvalidKeyMapError']) {
      if (msg.includes(code)) {
        AgroMaps.errorCode = code;
        AgroMaps.error = ERROR_MESSAGES[code].message;
        console.error(`[AgroMaps] Detected Google Maps Error: ${code}`);
        document.querySelectorAll('.agro-map-container, [data-maps-container]').forEach(el => {
          AgroMaps.showNotice(el, code);
        });
        dispatch('agromaps:error', { code, error: AgroMaps.error });
        break;
      }
    }
  });

  /**
   * Load Google Maps JS API once per page using modern dynamic library imports.
   *
   * @param {Object} [options]
   * @param {string} [options.apiKey] Browser API key
   * @param {string} [options.mapId] Map ID
   * @param {string} [options.v='weekly'] Version
   * @param {string} [options.region='lk'] Region code (Sri Lanka by default)
   * @param {string} [options.language='en'] Language
   * @returns {Promise<Object>} Resolves with { google, maps, marker, places, mapId }
   */
  AgroMaps.load = function (options = {}) {
    if (Array.isArray(options)) {
      options = {};
    }
    if (AgroMaps.isLoaded) {
      return AgroMaps.ready;
    }
    if (AgroMaps.isLoading) {
      return AgroMaps.ready;
    }

    const apiKey = (options && options.apiKey) ||
      window.__AGRO_MAPS_CONFIG__?.browserKey ||
      document.querySelector('meta[name="maps-browser-key"]')?.getAttribute('content') ||
      '';

    const mapId = options.mapId ||
      window.__AGRO_MAPS_CONFIG__?.mapId ||
      document.querySelector('meta[name="maps-map-id"]')?.getAttribute('content') ||
      '';

    AgroMaps.mapId = mapId;

    if (!apiKey) {
      AgroMaps.errorCode = 'MissingKey';
      AgroMaps.error = ERROR_MESSAGES.MissingKey.message;
      dispatch('agromaps:error', { code: 'MissingKey', error: AgroMaps.error });
      AgroMaps._rejectReady(new Error(AgroMaps.error));
      return AgroMaps.ready;
    }

    AgroMaps.isLoading = true;

    // Dynamic library bootstrap loader recommended by Google Maps JavaScript API
    if (!window.google?.maps?.importLibrary) {
      (g => {
        let h;
        let a;
        let k;
        const p = "The Google Maps JavaScript API";
        const c = "google";
        const l = "importLibrary";
        const q = "__ib__";
        const m = document;
        window.google = window.google || {};
        window.google.maps = window.google.maps || {};
        const d = window.google.maps;
        const r = new Set();
        const e = new URLSearchParams();
        const u = () => h || (h = new Promise(async (f, n) => {
          await (a = m.createElement("script"));
          a.id = "google-maps-api-script";
          a.async = true;
          e.set("libraries", [...r] + "");
          for (k in g) {
            e.set(k.replace(/[A-Z]/g, t => "_" + t[0].toLowerCase()), g[k]);
          }
          e.set("callback", c + ".maps." + q);
          a.src = `https://maps.googleapis.com/maps/api/js?` + e;
          d[q] = f;
          a.onerror = () => {
            AgroMaps.errorCode = 'NetworkError';
            AgroMaps.error = ERROR_MESSAGES.NetworkError.message;
            AgroMaps.isLoading = false;
            dispatch('agromaps:error', { code: 'NetworkError', error: AgroMaps.error });
            AgroMaps._rejectReady(new Error(AgroMaps.error));
            n(new Error(p + " could not load."));
          };
          const nonceEl = m.querySelector("script[nonce]");
          if (nonceEl && nonceEl.nonce) a.nonce = nonceEl.nonce;
          m.head.appendChild(a);
        }));
        if (!d[l]) {
          d[l] = (f, ...n) => r.add(f) && u().then(() => d[l](f, ...n));
        }
      })({
        key: apiKey,
        v: options.v || 'weekly',
        loading: 'async',
        region: options.region || 'lk',
        language: options.language || 'en'
      });
    }

    // Load 'maps', 'marker', and 'places' libraries concurrently
    Promise.all([
      window.google.maps.importLibrary('maps'),
      window.google.maps.importLibrary('marker'),
      window.google.maps.importLibrary('places')
    ])
      .then(([mapsLib, markerLib, placesLib]) => {
        AgroMaps.libraries = {
          maps: mapsLib,
          marker: markerLib,
          places: placesLib
        };
        AgroMaps.isLoaded = true;
        AgroMaps.isLoading = false;

        const payload = {
          google: window.google,
          maps: mapsLib,
          marker: markerLib,
          places: placesLib,
          mapId: AgroMaps.mapId
        };

        dispatch('agromaps:ready', payload);
        AgroMaps._resolveReady(payload);
      })
      .catch((err) => {
        AgroMaps.isLoading = false;
        if (!AgroMaps.error) {
          AgroMaps.error = err?.message || 'Failed to import Google Maps libraries.';
          for (const code of ['RefererNotAllowedMapError', 'ApiNotActivatedMapError', 'BillingNotEnabledMapError', 'InvalidKeyMapError']) {
            if (err?.message && err.message.includes(code)) {
              AgroMaps.errorCode = code;
              break;
            }
          }
        }
        dispatch('agromaps:error', { code: AgroMaps.errorCode || 'ImportError', error: AgroMaps.error });
        AgroMaps._rejectReady(err);
      });

    return AgroMaps.ready;
  };

  // Expose AgroMaps globally
  window.AgroMaps = AgroMaps;

  // AgroMapsLoader compatibility alias used by order and marketplace templates.
  // Provides isAvailable(), getMapId(), and a promise-based load() wrapper.
  window.AgroMapsLoader = {
    /**
     * Returns true when a browser API key is present in meta tags or config.
     * Maps may still fail to render if the key is invalid or billing is off,
     * but this check gates whether we attempt to load at all.
     */
    isAvailable: function () {
      const key =
        window.__AGRO_MAPS_CONFIG__?.browserKey ||
        document.querySelector('meta[name="maps-browser-key"]')?.getAttribute('content') ||
        '';
      return !!key && !AgroMaps.authFailed;
    },

    /** Return the Map ID (needed for AdvancedMarkerElement). */
    getMapId: function () {
      return (
        AgroMaps.mapId ||
        window.__AGRO_MAPS_CONFIG__?.mapId ||
        document.querySelector('meta[name="maps-map-id"]')?.getAttribute('content') ||
        ''
      );
    },

    /**
     * Load Google Maps (delegates to AgroMaps.load).
     * The `_libraries` argument is accepted for backwards-compat but ignored
     * because AgroMaps.load always imports maps + marker + places.
     *
     * @param {string[]} [_libraries] Ignored – kept for call-site compatibility.
     * @returns {Promise} Resolves when Google Maps is ready.
     */
    load: function (_libraries) {
      return AgroMaps.load();
    }
  };

  // Auto-initialize if credentials exist on DOMContentLoaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      const autoKey = window.__AGRO_MAPS_CONFIG__?.browserKey ||
        document.querySelector('meta[name="maps-browser-key"]')?.getAttribute('content');
      if (autoKey && !AgroMaps.isLoading && !AgroMaps.isLoaded) {
        AgroMaps.load();
      }
    });
  } else {
    const autoKey = window.__AGRO_MAPS_CONFIG__?.browserKey ||
      document.querySelector('meta[name="maps-browser-key"]')?.getAttribute('content');
    if (autoKey && !AgroMaps.isLoading && !AgroMaps.isLoaded) {
      AgroMaps.load();
    }
  }

})(window, document);
