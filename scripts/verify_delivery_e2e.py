"""
End-to-end verification script for AgroLink delivery pricing & routing.
Tests 3 realistic locations around Colombo:
1. ~10 km away (Real Google Routes API)
2. ~50 km away (Estimated fallback mode)
3. ~72 km away (Estimated fallback mode)

Outputs a formatted table of distance, distance source, delivery fee, and grand total.
"""
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from decimal import Decimal
from app import create_app
from services.distance import get_driving_distance_km
from services.pricing import calculate_delivery_fee, calculate_order_totals

def run_walkthrough():
    app = create_app()
    with app.app_context():
        # Colombo Reference point (e.g., Colombo Central / Fort)
        farmer_lat = 6.9271
        farmer_lng = 79.8612
        
        # Test targets:
        # 1. Mount Lavinia (~10-12 km driving from Colombo)
        loc_10km = {"name": "Mount Lavinia", "lat": 6.8400, "lng": 79.8700}
        
        # 2. Kalutara (~45-50 km driving from Colombo)
        loc_50km = {"name": "Kalutara", "lat": 6.5854, "lng": 79.9607}
        
        # 3. Aluthgama / Bentota (~70-75 km driving from Colombo)
        loc_72km = {"name": "Aluthgama", "lat": 6.4258, "lng": 80.0022}
        
        # Example produce: 15 kg of produce @ LKR 300 / kg -> Items total = LKR 4,500.00
        qty = Decimal("15.0")
        price_per_kg = Decimal("300.00")
        items_total = qty * price_per_kg
        
        results = []
        
        # --- Case 1: Real Routes API (~10 km) ---
        dist_1, src_1 = get_driving_distance_km(farmer_lat, farmer_lng, loc_10km["lat"], loc_10km["lng"])
        fee_1 = calculate_delivery_fee(dist_1)
        totals_1 = calculate_order_totals(items_total, fee_1)
        results.append({
            "scenario": f"~10 km ({loc_10km['name']})",
            "distance_km": dist_1,
            "source": src_1,
            "fee": fee_1,
            "items_total": items_total,
            "grand_total": totals_1["grand_total"]
        })
        
        # --- Case 2: Estimated Fallback Mode (~50 km) ---
        with patch('services.distance.get_server_key', return_value=''):
            dist_2, src_2 = get_driving_distance_km(farmer_lat, farmer_lng, loc_50km["lat"], loc_50km["lng"])
        fee_2 = calculate_delivery_fee(dist_2)
        totals_2 = calculate_order_totals(items_total, fee_2)
        results.append({
            "scenario": f"~50 km ({loc_50km['name']})",
            "distance_km": dist_2,
            "source": src_2,
            "fee": fee_2,
            "items_total": items_total,
            "grand_total": totals_2["grand_total"]
        })
        
        # --- Case 3: Estimated Fallback Mode (~72 km) ---
        with patch('services.distance.get_server_key', return_value=''):
            dist_3, src_3 = get_driving_distance_km(farmer_lat, farmer_lng, loc_72km["lat"], loc_72km["lng"])
        fee_3 = calculate_delivery_fee(dist_3)
        totals_3 = calculate_order_totals(items_total, fee_3)
        results.append({
            "scenario": f"~72 km ({loc_72km['name']})",
            "distance_km": dist_3,
            "source": src_3,
            "fee": fee_3,
            "items_total": items_total,
            "grand_total": totals_3["grand_total"]
        })
        
        print("\n==========================================================================================")
        print(" AgroLink Delivery Pricing End-to-End Walkthrough (15 kg @ LKR 300 = Items LKR 4,500.00)")
        print("==========================================================================================")
        print(f"{'Scenario / Destination':<26} | {'Distance':<11} | {'Source':<10} | {'Delivery Fee':<14} | {'Grand Total':<14}")
        print("---------------------------+-------------+------------+----------------+---------------")
        for r in results:
            dist_str = f"{r['distance_km']:.2f} km"
            fee_str = f"LKR {r['fee']:,.2f}"
            tot_str = f"LKR {r['grand_total']:,.2f}"
            print(f"{r['scenario']:<26} | {dist_str:<11} | {r['source']:<10} | {fee_str:<14} | {tot_str:<14}")
        print("==========================================================================================\n")

if __name__ == "__main__":
    run_walkthrough()
