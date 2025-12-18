"""
Mock Data Generator for NexGen Logistics Cost Intelligence Platform
Generates 7 interconnected CSV files with realistic relationships and some missing data.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# Set random seed for reproducibility
np.random.seed(42)
random.seed(42)

def generate_mock_data():
    """Generate all 7 CSV files with interconnected relationships"""
    
    # ==================== 1. VEHICLE FLEET ====================
    print("Generating vehicle_fleet.csv...")
    
    vehicle_types = ['Box Truck', 'Van', 'Semi-Truck', 'Refrigerated Truck', 'Flatbed']
    fuel_types = ['Diesel', 'Electric', 'Hybrid', 'CNG']
    
    vehicles = []
    for i in range(50):
        vehicle_type = random.choice(vehicle_types)
        fuel_type = random.choice(fuel_types)
        
        # CO2 emissions based on fuel type
        co2_factor = {
            'Diesel': random.uniform(2.5, 3.2),
            'Electric': random.uniform(0.1, 0.3),
            'Hybrid': random.uniform(1.2, 1.8),
            'CNG': random.uniform(1.8, 2.4)
        }
        
        vehicles.append({
            'vehicle_id': f'VEH{1000+i}',
            'vehicle_type': vehicle_type,
            'fuel_type': fuel_type,
            'capacity_kg': random.randint(500, 15000),
            'fuel_efficiency_kmpl': random.uniform(5, 25),
            'co2_per_km': co2_factor[fuel_type],
            'maintenance_cost_per_km': random.uniform(0.15, 0.45),
            'year': random.randint(2015, 2024),
            'status': random.choice(['Active', 'Active', 'Active', 'Maintenance', 'Retired'])
        })
    
    vehicle_fleet_df = pd.DataFrame(vehicles)
    vehicle_fleet_df.to_csv('vehicle_fleet.csv', index=False)
    print(f"✓ Generated {len(vehicle_fleet_df)} vehicle records")
    
    # ==================== 2. ROUTES/DISTANCE ====================
    print("Generating routes_distance.csv...")
    
    cities = ['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix', 
              'Philadelphia', 'San Antonio', 'San Diego', 'Dallas', 'Austin',
              'Jacksonville', 'Fort Worth', 'Columbus', 'Charlotte', 'Seattle']
    
    warehouses = ['WH_East', 'WH_West', 'WH_Central', 'WH_South', 'WH_North']
    
    routes = []
    route_id = 1
    for warehouse in warehouses:
        for city in cities:
            if random.random() > 0.3:  # Not all warehouse-city combinations exist
                distance_km = random.randint(50, 2500)
                
                # Traffic patterns affect delivery time
                traffic_level = random.choice(['Low', 'Medium', 'High'])
                traffic_factor = {'Low': 1.0, 'Medium': 1.3, 'High': 1.6}
                
                routes.append({
                    'route_id': f'RT{1000+route_id}',
                    'origin_warehouse': warehouse,
                    'destination_city': city,
                    'distance_km': distance_km,
                    'avg_traffic_level': traffic_level,
                    'estimated_time_hours': (distance_km / 70) * traffic_factor[traffic_level],
                    'toll_cost': random.uniform(10, 150) if random.random() > 0.4 else 0,
                    'route_difficulty': random.choice(['Easy', 'Medium', 'Hard'])
                })
                route_id += 1
    
    routes_df = pd.DataFrame(routes)
    routes_df.to_csv('routes_distance.csv', index=False)
    print(f"✓ Generated {len(routes_df)} route records")
    
    # ==================== 3. ORDERS ====================
    print("Generating orders.csv...")
    
    carriers = ['FastShip Express', 'EcoLogistics', 'QuickMove Inc', 'PrimeTransport', 'GreenHaul Co']
    priorities = ['Standard', 'Express', 'Overnight']
    
    start_date = datetime(2024, 1, 1)
    orders = []
    
    for i in range(200):
        order_date = start_date + timedelta(days=random.randint(0, 350))
        
        # Some recent orders may have missing data
        is_recent = order_date > datetime(2024, 11, 1)
        
        route = random.choice(routes)
        priority = random.choice(priorities)
        carrier = random.choice(carriers)
        
        # Weight and dimensions
        weight_kg = random.uniform(10, 5000)
        volume_m3 = random.uniform(0.5, 50)
        
        # Revenue based on priority and weight
        base_rate = {'Standard': 0.8, 'Express': 1.5, 'Overnight': 2.5}
        revenue = weight_kg * base_rate[priority] * random.uniform(0.8, 1.2)
        
        orders.append({
            'order_id': f'ORD{10000+i}',
            'order_date': order_date.strftime('%Y-%m-%d'),
            'customer_id': f'CUST{random.randint(1000, 1500)}',
            'origin_warehouse': route['origin_warehouse'],
            'destination_city': route['destination_city'],
            'route_id': route['route_id'],
            'carrier': carrier,
            'priority': priority,
            'weight_kg': round(weight_kg, 2),
            'volume_m3': round(volume_m3, 2),
            'revenue': round(revenue, 2) if not (is_recent and random.random() > 0.7) else np.nan,
            'vehicle_assigned': random.choice(vehicle_fleet_df['vehicle_id'].tolist()) if not (is_recent and random.random() > 0.8) else np.nan,
            'status': random.choice(['Delivered', 'Delivered', 'Delivered', 'In Transit', 'Cancelled']) if not is_recent else 'Pending'
        })
    
    orders_df = pd.DataFrame(orders)
    orders_df.to_csv('orders.csv', index=False)
    print(f"✓ Generated {len(orders_df)} order records")
    
    # ==================== 4. DELIVERY PERFORMANCE ====================
    print("Generating delivery_performance.csv...")
    
    # Only delivered orders have performance data
    delivered_orders = orders_df[orders_df['status'] == 'Delivered']['order_id'].tolist()
    
    performance = []
    for order_id in delivered_orders:
        order = orders_df[orders_df['order_id'] == order_id].iloc[0]
        route_info = routes_df[routes_df['route_id'] == order['route_id']].iloc[0]
        
        # Expected delivery time
        expected_hours = route_info['estimated_time_hours']
        
        # Actual delivery time (with variability)
        delay_factor = random.uniform(0.8, 1.5)
        actual_hours = expected_hours * delay_factor
        
        # Delivery status
        if actual_hours <= expected_hours:
            delivery_status = 'On Time'
        elif actual_hours <= expected_hours * 1.1:
            delivery_status = 'Minor Delay'
        else:
            delivery_status = 'Delayed'
        
        performance.append({
            'order_id': order_id,
            'expected_delivery_date': (pd.to_datetime(order['order_date']) + timedelta(hours=expected_hours)).strftime('%Y-%m-%d'),
            'actual_delivery_date': (pd.to_datetime(order['order_date']) + timedelta(hours=actual_hours)).strftime('%Y-%m-%d'),
            'delivery_status': delivery_status,
            'delay_hours': round(max(0, actual_hours - expected_hours), 2),
            'on_time_percentage': round(min(100, (expected_hours / actual_hours) * 100), 2),
            'damage_reported': random.choice([True, False, False, False]),  # 25% damage rate
            'delivery_attempts': random.randint(1, 3)
        })
    
    delivery_performance_df = pd.DataFrame(performance)
    delivery_performance_df.to_csv('delivery_performance.csv', index=False)
    print(f"✓ Generated {len(delivery_performance_df)} delivery performance records")
    
    # ==================== 5. COST BREAKDOWN ====================
    print("Generating cost_breakdown.csv...")
    
    cost_categories = ['Fuel', 'Labor', 'Toll', 'Maintenance', 'Insurance', 'Carrier Fee', 'Storage']
    
    costs = []
    cost_id = 1
    
    for order_id in delivered_orders[:150]:  # 150 cost records as specified
        order = orders_df[orders_df['order_id'] == order_id].iloc[0]
        route_info = routes_df[routes_df['route_id'] == order['route_id']].iloc[0]
        
        # Get vehicle info if available
        vehicle_id = order['vehicle_assigned']
        if pd.notna(vehicle_id):
            vehicle_info = vehicle_fleet_df[vehicle_fleet_df['vehicle_id'] == vehicle_id].iloc[0]
        else:
            vehicle_info = vehicle_fleet_df.iloc[0]  # Default vehicle
        
        distance = route_info['distance_km']
        
        # Calculate various costs
        fuel_cost = (distance / vehicle_info['fuel_efficiency_kmpl']) * random.uniform(1.2, 1.8)  # fuel price per liter
        labor_cost = (distance / 70) * random.uniform(25, 45)  # driver hourly rate
        maintenance_cost = distance * vehicle_info['maintenance_cost_per_km']
        toll_cost = route_info['toll_cost']
        insurance_cost = random.uniform(15, 50)
        
        # Carrier fee (for outsourced carriers)
        carrier_fee = order['weight_kg'] * random.uniform(0.3, 0.8) if order['carrier'] != 'In-House' else 0
        
        # Storage cost (for delayed orders)
        delivery_perf = delivery_performance_df[delivery_performance_df['order_id'] == order_id]
        if not delivery_perf.empty and delivery_perf.iloc[0]['delivery_status'] == 'Delayed':
            storage_cost = random.uniform(20, 100)
        else:
            storage_cost = random.uniform(5, 20)
        
        # Add each cost component
        cost_components = {
            'Fuel': fuel_cost,
            'Labor': labor_cost,
            'Maintenance': maintenance_cost,
            'Toll': toll_cost,
            'Insurance': insurance_cost,
            'Carrier Fee': carrier_fee,
            'Storage': storage_cost
        }
        
        for category, amount in cost_components.items():
            costs.append({
                'cost_id': f'CST{10000+cost_id}',
                'order_id': order_id,
                'cost_category': category,
                'cost_amount': round(amount, 2),
                'date_incurred': order['order_date'],
                'vendor': order['carrier'] if category == 'Carrier Fee' else f'{category} Vendor {random.randint(1, 5)}',
                'payment_status': random.choice(['Paid', 'Paid', 'Pending'])
            })
            cost_id += 1
    
    cost_breakdown_df = pd.DataFrame(costs)
    cost_breakdown_df.to_csv('cost_breakdown.csv', index=False)
    print(f"✓ Generated {len(cost_breakdown_df)} cost records")
    
    # ==================== 6. WAREHOUSE INVENTORY ====================
    print("Generating warehouse_inventory.csv...")
    
    product_categories = ['Electronics', 'Furniture', 'Apparel', 'Food', 'Industrial', 'Healthcare', 'Automotive']
    
    inventory = []
    for warehouse in warehouses:
        for i in range(random.randint(30, 50)):
            category = random.choice(product_categories)
            
            # Storage costs vary by category
            storage_cost_map = {
                'Electronics': random.uniform(0.5, 1.2),
                'Furniture': random.uniform(0.3, 0.8),
                'Apparel': random.uniform(0.2, 0.5),
                'Food': random.uniform(0.8, 1.5),  # Higher due to refrigeration
                'Industrial': random.uniform(0.4, 0.9),
                'Healthcare': random.uniform(0.6, 1.3),
                'Automotive': random.uniform(0.5, 1.0)
            }
            
            inventory.append({
                'warehouse_id': warehouse,
                'product_sku': f'SKU{random.randint(10000, 99999)}',
                'product_category': category,
                'quantity_on_hand': random.randint(10, 1000),
                'unit_value': random.uniform(10, 500),
                'storage_cost_per_day': storage_cost_map[category],
                'days_in_storage': random.randint(1, 180),
                'reorder_point': random.randint(20, 100),
                'last_updated': (datetime.now() - timedelta(days=random.randint(0, 30))).strftime('%Y-%m-%d')
            })
    
    warehouse_inventory_df = pd.DataFrame(inventory)
    warehouse_inventory_df.to_csv('warehouse_inventory.csv', index=False)
    print(f"✓ Generated {len(warehouse_inventory_df)} inventory records")
    
    # ==================== 7. CUSTOMER FEEDBACK ====================
    print("Generating customer_feedback.csv...")
    
    feedback = []
    for order_id in delivered_orders[:100]:  # Feedback for 100 orders
        order = orders_df[orders_df['order_id'] == order_id].iloc[0]
        delivery_perf = delivery_performance_df[delivery_performance_df['order_id'] == order_id].iloc[0]
        
        # Rating based on delivery performance
        if delivery_perf['delivery_status'] == 'On Time':
            rating = random.randint(4, 5)
        elif delivery_perf['delivery_status'] == 'Minor Delay':
            rating = random.randint(3, 4)
        else:
            rating = random.randint(1, 3)
        
        # Damage affects rating
        if delivery_perf['damage_reported']:
            rating = max(1, rating - random.randint(1, 2))
        
        feedback_texts = {
            5: ['Excellent service!', 'Very fast delivery', 'Perfect condition', 'Highly recommend'],
            4: ['Good service', 'Minor issues but overall satisfied', 'Will use again'],
            3: ['Average service', 'Some delays', 'Could be better'],
            2: ['Poor service', 'Significant delays', 'Not satisfied'],
            1: ['Terrible experience', 'Package damaged', 'Never again']
        }
        
        feedback.append({
            'feedback_id': f'FB{10000+len(feedback)}',
            'order_id': order_id,
            'customer_id': order['customer_id'],
            'rating': rating,
            'feedback_text': random.choice(feedback_texts[rating]),
            'feedback_date': delivery_perf['actual_delivery_date'],
            'carrier': order['carrier'],
            'would_recommend': rating >= 4
        })
    
    customer_feedback_df = pd.DataFrame(feedback)
    customer_feedback_df.to_csv('customer_feedback.csv', index=False)
    print(f"✓ Generated {len(customer_feedback_df)} customer feedback records")
    
    print("\n" + "="*60)
    print("✓ ALL MOCK DATA GENERATED SUCCESSFULLY!")
    print("="*60)
    print("\nSummary:")
    print(f"  • vehicle_fleet.csv: {len(vehicle_fleet_df)} records")
    print(f"  • routes_distance.csv: {len(routes_df)} records")
    print(f"  • orders.csv: {len(orders_df)} records")
    print(f"  • delivery_performance.csv: {len(delivery_performance_df)} records")
    print(f"  • cost_breakdown.csv: {len(cost_breakdown_df)} records")
    print(f"  • warehouse_inventory.csv: {len(warehouse_inventory_df)} records")
    print(f"  • customer_feedback.csv: {len(customer_feedback_df)} records")
    print("\nNote: Some recent orders have missing data to simulate real-world scenarios.")
    print("="*60)

if __name__ == "__main__":
    generate_mock_data()
