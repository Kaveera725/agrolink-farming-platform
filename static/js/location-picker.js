/**
 * AgroLink Location Picker Component (static/js/location-picker.js)
 * 
 * Reusable location picker supporting:
 * - Google Maps AdvancedMarkerElement (draggable)
 * - Places Autocomplete restricted to Sri Lanka ('lk')
 * - "Use my current location" via navigator.geolocation with clear permission/timeout handling
 * - Client-side reverse geocoding
 * - Loading skeleton & automatic manual fallback when maps are unavailable
 * - Synchronization with hidden form inputs (latitude, longitude, address_text)
 */

(function (window, document) {
  'use strict';

  const SL_DEFAULT_CENTER = { lat: 7.8731, lng: 80.7718 };
  const SL_BOUNDS = {
    latMin: 5.8,
    latMax: 9.9,
    lngMin: 79.4,
    lngMax: 82.0
  };

  function isWithinSriLanka(lat, lng) {
    return lat >= SL_BOUNDS.latMin && lat <= SL_BOUNDS.latMax &&
           lng >= SL_BOUNDS.lngMin && lng <= SL_BOUNDS.lngMax;
  }

  class AgroLocationPicker {
    constructor(options = {}) {
      this.prefix = options.prefix || 'location-picker';
      this.initialLat = options.initialLat ? parseFloat(options.initialLat) : null;
      this.initialLng = options.initialLng ? parseFloat(options.initialLng) : null;
      this.initialAddress = options.initialAddress || '';
      this.required = Boolean(options.required);

      // DOM Elements
      this.mapContainer = document.getElementById(`${this.prefix}-map`);
      this.skeleton = document.getElementById(`${this.prefix}-skeleton`);
      this.fallbackContainer = document.getElementById(`${this.prefix}-fallback`);
      this.searchInput = document.getElementById(`${this.prefix}-search`);
      this.btnUseLocation = document.getElementById(`${this.prefix}-use-location`);
      this.geoNotice = document.getElementById(`${this.prefix}-geo-notice`);
      this.addressDisplay = document.getElementById(`${this.prefix}-address-display`);
      this.coordsDisplay = document.getElementById(`${this.prefix}-coords-display`);
      this.statusBadge = document.getElementById(`${this.prefix}-status-badge`);

      // Hidden Form Inputs
      this.inputLat = document.getElementById(`${this.prefix}-latitude`);
      this.inputLng = document.getElementById(`${this.prefix}-longitude`);
      this.inputAddress = document.getElementById(`${this.prefix}-address-text`);

      // Manual Fallback Inputs
      this.manualLat = document.getElementById(`${this.prefix}-manual-lat`);
      this.manualLng = document.getElementById(`${this.prefix}-manual-lng`);
      this.manualAddress = document.getElementById(`${this.prefix}-manual-address`);

      this.mapInstance = null;
      this.markerInstance = null;
      this.geocoderInstance = null;
      this.autocompleteInstance = null;

      this.init();
    }

    init() {
      this.bindManualInputs();
      this.bindGeolocationButton();

      // If initial coordinates exist, display them immediately
      if (this.initialLat && this.initialLng && !isNaN(this.initialLat) && !isNaN(this.initialLng)) {
        this.updateDisplays(this.initialLat, this.initialLng, this.initialAddress);
      }

      // Check if AgroMaps is available
      if (window.AgroMaps && typeof window.AgroMaps.load === 'function') {
        window.AgroMaps.load()
          .then((mapsPayload) => {
            this.setupInteractiveMap(mapsPayload);
          })
          .catch((err) => {
            console.warn('[AgroLocationPicker] Map loading failed, enabling fallback:', err);
            this.enableManualFallback();
          });
      } else {
        this.enableManualFallback();
      }
    }

    setupInteractiveMap({ google, maps, marker, places, mapId }) {
      if (!this.mapContainer) return;

      // Hide skeleton
      if (this.skeleton) {
        this.skeleton.classList.add('hidden');
      }

      const hasInitialCoords = (this.initialLat && this.initialLng && !isNaN(this.initialLat) && !isNaN(this.initialLng));
      const center = hasInitialCoords
        ? { lat: this.initialLat, lng: this.initialLng }
        : SL_DEFAULT_CENTER;

      // Create Map
      this.mapInstance = new maps.Map(this.mapContainer, {
        center: center,
        zoom: hasInitialCoords ? 14 : 8,
        mapId: mapId,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: true
      });

      // Create Draggable Advanced Marker
      this.markerInstance = new marker.AdvancedMarkerElement({
        map: this.mapInstance,
        position: center,
        title: 'Drag to set exact location',
        gmpDraggable: true
      });

      // Initialize Geocoder for reverse-geocoding
      this.geocoderInstance = new google.maps.Geocoder();

      // Listen for marker dragend
      this.markerInstance.addListener('dragend', () => {
        const pos = this.markerInstance.position;
        const lat = typeof pos.lat === 'function' ? pos.lat() : pos.lat;
        const lng = typeof pos.lng === 'function' ? pos.lng() : pos.lng;
        this.onCoordinatesSelected(lat, lng, null);
      });

      // Listen for click on map canvas
      this.mapInstance.addListener('click', (event) => {
        if (event.latLng) {
          const lat = event.latLng.lat();
          const lng = event.latLng.lng();
          this.markerInstance.position = { lat, lng };
          this.onCoordinatesSelected(lat, lng, null);
        }
      });

      // Setup Places Autocomplete restricted to Sri Lanka (lk)
      if (this.searchInput && places) {
        this.setupPlacesAutocomplete(places);
      }
    }

    setupPlacesAutocomplete(places) {
      this.autocompleteInstance = new places.Autocomplete(this.searchInput, {
        componentRestrictions: { country: 'lk' },
        fields: ['geometry', 'name', 'formatted_address']
      });

      this.autocompleteInstance.addListener('place_changed', () => {
        const place = this.autocompleteInstance.getPlace();
        if (place && place.geometry && place.geometry.location) {
          const lat = place.geometry.location.lat();
          const lng = place.geometry.location.lng();
          const addr = place.formatted_address || place.name || this.searchInput.value;

          if (this.markerInstance) {
            this.markerInstance.position = { lat, lng };
          }
          if (this.mapInstance) {
            this.mapInstance.setCenter({ lat, lng });
            this.mapInstance.setZoom(15);
          }

          this.onCoordinatesSelected(lat, lng, addr);
        }
      });
    }

    onCoordinatesSelected(lat, lng, addressOverride = null) {
      const parsedLat = parseFloat(lat);
      const parsedLng = parseFloat(lng);

      if (isNaN(parsedLat) || isNaN(parsedLng)) return;

      this.updateDisplays(parsedLat, parsedLng, addressOverride);

      // Perform reverse geocode if no address override was given
      if (!addressOverride && this.geocoderInstance) {
        this.geocoderInstance.geocode({ location: { lat: parsedLat, lng: parsedLng } }, (results, status) => {
          if (status === 'OK' && results && results[0]) {
            const formatted = results[0].formatted_address;
            this.updateDisplays(parsedLat, parsedLng, formatted);
          }
        });
      }
    }

    updateDisplays(lat, lng, addressText) {
      const fixedLat = lat.toFixed(6);
      const fixedLng = lng.toFixed(6);

      // Hidden Form Inputs
      if (this.inputLat) this.inputLat.value = fixedLat;
      if (this.inputLng) this.inputLng.value = fixedLng;
      if (this.inputAddress && addressText) this.inputAddress.value = addressText;

      // Manual Inputs
      if (this.manualLat && document.activeElement !== this.manualLat) this.manualLat.value = fixedLat;
      if (this.manualLng && document.activeElement !== this.manualLng) this.manualLng.value = fixedLng;
      if (this.manualAddress && addressText && document.activeElement !== this.manualAddress) {
        this.manualAddress.value = addressText;
      }

      // Visual Readout
      if (this.coordsDisplay) {
        this.coordsDisplay.textContent = `${fixedLat}, ${fixedLng}`;
      }
      if (this.addressDisplay) {
        this.addressDisplay.textContent = addressText || 'Exact location pinned';
      }

      if (this.statusBadge) {
        if (isWithinSriLanka(lat, lng)) {
          this.statusBadge.className = 'inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200';
          this.statusBadge.textContent = 'In Sri Lanka';
        } else {
          this.statusBadge.className = 'inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-200';
          this.statusBadge.textContent = 'Outside Sri Lanka';
        }
      }
    }

    bindGeolocationButton() {
      if (!this.btnUseLocation) return;

      this.btnUseLocation.addEventListener('click', () => {
        if (!navigator.geolocation) {
          this.showGeoNotice('Geolocation is not supported by your browser.', 'error');
          return;
        }

        this.clearGeoNotice();
        const originalHtml = this.btnUseLocation.innerHTML;
        this.btnUseLocation.disabled = true;
        this.btnUseLocation.innerHTML = '<span class="animate-spin inline-block h-3.5 w-3.5 border-2 border-leaf border-t-transparent rounded-full mr-1.5"></span> Locating...';

        navigator.geolocation.getCurrentPosition(
          (position) => {
            this.btnUseLocation.disabled = false;
            this.btnUseLocation.innerHTML = originalHtml;

            const lat = position.coords.latitude;
            const lng = position.coords.longitude;

            if (!isWithinSriLanka(lat, lng)) {
              this.showGeoNotice('Your detected location is outside Sri Lanka bounds. Please pin your Sri Lankan address.', 'warning');
            } else {
              this.showGeoNotice('Location detected successfully via GPS.', 'success');
            }

            if (this.markerInstance) {
              this.markerInstance.position = { lat, lng };
            }
            if (this.mapInstance) {
              this.mapInstance.setCenter({ lat, lng });
              this.mapInstance.setZoom(15);
            }

            this.onCoordinatesSelected(lat, lng, 'My Current Device Location');
          },
          (error) => {
            this.btnUseLocation.disabled = false;
            this.btnUseLocation.innerHTML = originalHtml;

            let message = 'Unable to retrieve location.';
            if (error.code === error.PERMISSION_DENIED) {
              message = 'Location access was denied. Please allow location permissions in your browser or search above.';
            } else if (error.code === error.TIMEOUT) {
              message = 'Location request timed out. Please try again or search your town manually.';
            } else if (error.code === error.POSITION_UNAVAILABLE) {
              message = 'Location information is unavailable on your device. Please enter your location manually.';
            }
            this.showGeoNotice(message, 'error');
          },
          { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 }
        );
      });
    }

    bindManualInputs() {
      const syncManual = () => {
        const lat = parseFloat(this.manualLat?.value);
        const lng = parseFloat(this.manualLng?.value);
        const addr = this.manualAddress?.value.trim();

        if (!isNaN(lat) && !isNaN(lng)) {
          this.updateDisplays(lat, lng, addr);
          if (this.mapInstance && this.markerInstance) {
            this.markerInstance.position = { lat, lng };
            this.mapInstance.panTo({ lat, lng });
          }
        }
      };

      if (this.manualLat) this.manualLat.addEventListener('input', syncManual);
      if (this.manualLng) this.manualLng.addEventListener('input', syncManual);
      if (this.manualAddress) {
        this.manualAddress.addEventListener('input', () => {
          if (this.inputAddress) this.inputAddress.value = this.manualAddress.value;
          if (this.addressDisplay) this.addressDisplay.textContent = this.manualAddress.value || 'Custom address';
        });
      }
    }

    enableManualFallback() {
      if (this.skeleton) this.skeleton.classList.add('hidden');
      if (this.fallbackContainer) this.fallbackContainer.classList.remove('hidden');
      if (this.mapContainer) this.mapContainer.classList.add('hidden');
      if (this.searchInput) this.searchInput.setAttribute('disabled', 'disabled');
      if (this.btnUseLocation) this.btnUseLocation.classList.add('hidden');
    }

    showGeoNotice(msg, type = 'info') {
      if (!this.geoNotice) return;
      this.geoNotice.classList.remove('hidden');

      const colorMap = {
        error: 'bg-rose-50 border-rose-200 text-rose-800',
        warning: 'bg-amber-50 border-amber-200 text-amber-800',
        success: 'bg-emerald-50 border-emerald-200 text-emerald-800',
        info: 'bg-sky-50 border-sky-200 text-sky-800'
      };

      this.geoNotice.className = `p-3 rounded-xl border text-xs leading-relaxed ${colorMap[type] || colorMap.info}`;
      this.geoNotice.textContent = msg;
    }

    clearGeoNotice() {
      if (!this.geoNotice) return;
      this.geoNotice.classList.add('hidden');
      this.geoNotice.textContent = '';
    }
  }

  window.AgroLocationPicker = AgroLocationPicker;

})(window, document);
