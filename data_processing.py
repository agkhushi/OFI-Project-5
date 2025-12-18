"""
Data Processor adapted to the user's provided CSV files

This module standardizes column names from the existing CSVs (Order_ID, Order_Date, etc.),
merges them on Order_ID, and computes derived metrics used by the Streamlit app.
"""

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')


class DataProcessor:
    """Data handling, cleaning, merging and analytics for the provided CSVs."""

    def __init__(self):
        self.orders = None
        self.delivery = None
        self.routes = None
        self.vehicles = None
        self.costs = None
        self.merged_data = None
        self._delivered_cache = None  # Cache for delivered orders
        self._cost_cols_cache = None  # Cache for cost columns
        self._carrier_scores_cache = None  # Cache for carrier value scores

    def _standardize_cols(self, df):
        """Convert columns to snake_case lower - optimized with list comprehension"""
        df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]
        return df

    def load_all_data(self):
        """Load CSVs that exist in the workspace and standardize column names.

        Expected files: orders.csv, delivery_performance.csv, routes_distance.csv,
        vehicle_fleet.csv, cost_breakdown.csv
        """
        try:
            self.orders = self._standardize_cols(pd.read_csv('orders.csv'))
            self.delivery = self._standardize_cols(pd.read_csv('delivery_performance.csv'))
            self.routes = self._standardize_cols(pd.read_csv('routes_distance.csv'))
            self.vehicles = self._standardize_cols(pd.read_csv('vehicle_fleet.csv'))
            self.costs = self._standardize_cols(pd.read_csv('cost_breakdown.csv'))
            return True
        except FileNotFoundError as e:
            print(f"Missing file: {e}")
            return False
        except Exception as e:
            print(f"Error loading data: {e}")
            return False

    def process_data(self):
        """Clean, merge and create derived metrics compatible with app expectations."""
        # Use direct references instead of copies for merging
        orders = self.orders
        delivery = self.delivery
        routes = self.routes
        vehicles = self.vehicles
        costs = self.costs

        # Ensure order_id exists in all
        required_dfs = {'orders': orders, 'delivery': delivery, 'routes': routes, 'costs': costs}
        for name, df in required_dfs.items():
            if 'order_id' not in df.columns:
                raise ValueError(f'{name} lacks Order_ID column after normalization')

        # Parse dates once
        if 'order_date' in orders.columns:
            orders['order_date'] = pd.to_datetime(orders['order_date'], errors='coerce')

        # Build total_cost from cost_breakdown and cache cost columns
        self._cost_cols_cache = [c for c in costs.columns if c != 'order_id']
        costs['total_cost'] = costs[self._cost_cols_cache].sum(axis=1)

        # Merge all dataframes efficiently
        merged = (orders
                  .merge(routes, on='order_id', how='left', suffixes=('', '_route'))
                  .merge(delivery, on='order_id', how='left', suffixes=('', '_perf'))
                  .merge(costs[['order_id', 'total_cost'] + self._cost_cols_cache], on='order_id', how='left'))

        # Batch rename columns
        column_renames = {
            'origin': 'origin_warehouse',
            'destination': 'destination_city',
            'customer_rating': 'rating'
        }
        merged.rename(columns={k: v for k, v in column_renames.items() if k in merged.columns}, inplace=True)

        # Delivery status: vectorized operation
        merged['status'] = np.where(merged.get('delivery_status', pd.Series()).notna(), 'Delivered', 'Pending')

        # Compute on_time_percentage - vectorized
        if 'promised_delivery_days' in merged.columns and 'actual_delivery_days' in merged.columns:
            merged['on_time_percentage'] = ((merged['promised_delivery_days'] / merged['actual_delivery_days']) * 100).clip(upper=100)
        else:
            merged['on_time_percentage'] = 100

        # Numeric conversions - batch process
        numeric_conversions = {
            'distance_km': merged.get('distance_km', merged.get('distance', pd.Series())),
            'revenue': merged.get('order_value_inr', merged.get('order_value', pd.Series())),
            'delivery_cost_inr': merged.get('delivery_cost_inr', pd.Series())
        }
        
        for col, series in numeric_conversions.items():
            merged[col] = pd.to_numeric(series, errors='coerce')

        # Fill missing total_cost
        merged['total_cost'] = merged['total_cost'].fillna(merged['delivery_cost_inr'])
        merged['total_cost'] = merged['total_cost'].fillna(merged[self._cost_cols_cache].sum(axis=1))

        # CO2 emissions estimate
        avg_co2 = vehicles.get('co2_emissions_kg_per_km', pd.Series()).mean()
        merged['co2_per_km'] = avg_co2 if pd.notna(avg_co2) else 0.45
        merged['co2_emissions'] = merged['distance_km'] * merged['co2_per_km']

        # Profit and derived metrics - vectorized
        merged['profit'] = merged['revenue'] - merged['total_cost']
        merged['profit_margin'] = (merged['profit'] / merged['revenue']) * 100
        merged['cost_per_km'] = merged['total_cost'] / merged['distance_km']
        merged['cost_per_km'].replace([np.inf, -np.inf], np.nan, inplace=True)

        # Cost of inefficiency - vectorized
        merged['delay_days'] = (merged.get('actual_delivery_days', 0) - merged.get('promised_delivery_days', 0)).clip(lower=0)
        merged['delay_cost'] = merged['delay_days'] * (merged['delivery_cost_inr'] * 0.05 + 50)
        
        # Vectorized damage cost calculation
        merged['damage_cost'] = np.where(
            (merged.get('quality_issue', 'Perfect') != 'Perfect') & merged.get('quality_issue').notna(),
            merged['revenue'] * 0.15,
            0
        )
        
        merged['cost_of_inefficiency'] = merged['delay_cost'].fillna(0) + merged['damage_cost'].fillna(0)

        # Month/Year for trends - vectorized
        if 'order_date' in merged.columns:
            merged['month'] = merged['order_date'].dt.to_period('M')
            merged['year'] = merged['order_date'].dt.year
        else:
            merged['month'] = pd.NaT
            merged['year'] = 0

        # Fill missing numeric fields once
        numeric_cols = merged.select_dtypes(include=[np.number]).columns
        merged[numeric_cols] = merged[numeric_cols].fillna(0)

        self.merged_data = merged
        self._delivered_cache = None  # Reset cache when data changes
        self._carrier_scores_cache = None  # Reset cache
        return merged

    def _get_delivered_data(self):
        """Cache and return delivered orders to avoid repeated filtering"""
        if self._delivered_cache is None:
            self._delivered_cache = self.merged_data[self.merged_data['status'] == 'Delivered']
        return self._delivered_cache

    # --- Methods used by app ---
    def get_key_metrics(self):
        """Calculate key metrics from delivered orders"""
        df = self._get_delivered_data()
        total_revenue = df['revenue'].sum()
        total_cost = df['total_cost'].sum()
        profit_margin = ((total_revenue - total_cost) / total_revenue * 100) if total_revenue != 0 else 0
        cost_leakage = df['cost_of_inefficiency'].sum()
        co2_per_order = df['co2_emissions'].mean()
        return {
            'total_revenue': total_revenue,
            'revenue_growth': 0.0,
            'cost_leakage': cost_leakage,
            'leakage_reduction': 0.0,
            'profit_margin': profit_margin,
            'margin_change': 0.0,
            'co2_per_order': co2_per_order,
            'co2_reduction': 0.0
        }

    def get_cost_by_category(self):
        """Get cost breakdown by category"""
        summary = self.costs[self._cost_cols_cache].sum().reset_index()
        summary.columns = ['cost_category', 'cost_amount']
        return summary

    def get_revenue_cost_trend(self):
        """Get monthly revenue and cost trends"""
        df = self._get_delivered_data()
        monthly = df.groupby('month', observed=True).agg({'revenue': 'sum', 'total_cost': 'sum'}).reset_index()
        monthly['month'] = monthly['month'].astype(str)
        monthly.columns = ['month', 'revenue', 'cost']
        return monthly

    def get_carrier_performance(self):
        """Get carrier performance metrics"""
        df = self._get_delivered_data()
        carrier_perf = df.groupby('carrier').agg({
            'total_cost': 'mean',
            'on_time_percentage': 'mean',
            'order_id': 'count',
            'rating': 'mean'
        }).reset_index()
        carrier_perf.columns = ['carrier', 'avg_cost', 'on_time_percentage', 'total_orders', 'avg_rating']
        return carrier_perf

    def get_unique_warehouses(self):
        """Get list of unique warehouses"""
        return self.merged_data['origin_warehouse'].unique().tolist() if 'origin_warehouse' in self.merged_data.columns else []

    def get_unique_carriers(self):
        """Get list of unique carriers"""
        return self.merged_data['carrier'].unique().tolist() if 'carrier' in self.merged_data.columns else []

    def filter_data(self, regions, priorities, carriers):
        """Filter data by regions, priorities and carriers - optimized"""
        df = self.merged_data
        
        # Apply filters only if values provided
        masks = []
        if regions:
            masks.append(df['origin_warehouse'].isin(regions))
        if priorities:
            masks.append(df['priority'].isin(priorities))
        if carriers:
            masks.append(df['carrier'].isin(carriers))
        
        # Combine all masks with AND operation
        if masks:
            combined_mask = masks[0]
            for mask in masks[1:]:
                combined_mask &= mask
            return df[combined_mask]
        return df

    def calculate_cost_leakage(self, df):
        """Calculate cost leakage components"""
        delay_costs = df['delay_cost'].sum()
        damage_costs = df['damage_cost'].sum()
        
        # Carrier overcharges - vectorized calculation
        carrier_costs = df.groupby('carrier')['cost_per_km'].mean()
        carrier_overcharges = 0
        
        if not carrier_costs.empty:
            min_cost = carrier_costs.min()
            potential_savings = ((df['cost_per_km'] - min_cost) * df['distance_km']).clip(lower=0).sum()
            carrier_overcharges = potential_savings
            
        return {
            'delay_costs': delay_costs,
            'damage_costs': damage_costs,
            'carrier_overcharges': carrier_overcharges
        }

    def get_route_cost_analysis(self, df):
        """Analyze costs by route"""
        df_filtered = df[df['status'] == 'Delivered']
        route_analysis = df_filtered.groupby(['origin_warehouse', 'destination_city']).agg({
            'cost_per_km': 'mean',
            'total_cost': 'mean',
            'order_id': 'count'
        }).reset_index()
        route_analysis.columns = ['origin_warehouse', 'destination_city', 'avg_cost_per_km', 'avg_total_cost', 'order_count']
        return route_analysis

    def get_cost_waterfall(self, df):
        """Generate cost waterfall data"""
        df_filtered = df[df['status'] == 'Delivered']
        amounts = [df_filtered[c].mean() for c in self._cost_cols_cache if c in df_filtered.columns]
        categories = [c for c in self._cost_cols_cache if c in df_filtered.columns]
        
        return pd.DataFrame({
            'category': categories + ['Total'],
            'amount': amounts + [sum(amounts)],
            'measure': ['relative'] * len(categories) + ['total']
        })

    def get_cost_speed_analysis(self, df):
        """Analyze relationship between cost and delivery speed"""
        df_filtered = df[df['status'] == 'Delivered'].copy()
        df_filtered['delivery_hours'] = df_filtered.get('actual_delivery_days', 0) * 24
        return df_filtered[['order_id', 'delivery_hours', 'total_cost', 'delivery_status', 'rating', 'carrier']]

    def calculate_carrier_value_score(self):
        """Calculate carrier value scores with caching"""
        if self._carrier_scores_cache is not None:
            return self._carrier_scores_cache
            
        df = self._get_delivered_data()
        carrier_metrics = df.groupby('carrier').agg({
            'total_cost': 'mean',
            'on_time_percentage': 'mean',
            'rating': 'mean',
            'co2_emissions': 'mean',
            'order_id': 'count'
        }).reset_index()
        carrier_metrics.columns = ['carrier', 'avg_cost', 'on_time_percentage', 'avg_rating', 'co2_per_order', 'total_orders']
        
        # Normalize scores - vectorized
        cost_max = carrier_metrics['avg_cost'].max()
        co2_max = carrier_metrics['co2_per_order'].max()
        
        carrier_metrics['cost_score'] = (1 - carrier_metrics['avg_cost'] / cost_max) * 100 if cost_max > 0 else 0
        carrier_metrics['delivery_score'] = carrier_metrics['on_time_percentage']
        carrier_metrics['satisfaction_score'] = (carrier_metrics['avg_rating'] / 5) * 100
        carrier_metrics['sustainability_score'] = (1 - carrier_metrics['co2_per_order'] / co2_max) * 100 if co2_max > 0 else 0
        
        # Calculate weighted score - vectorized
        weights = np.array([0.4, 0.3, 0.2, 0.1])
        score_cols = ['cost_score', 'delivery_score', 'satisfaction_score', 'sustainability_score']
        carrier_metrics['carrier_value_score'] = carrier_metrics[score_cols].fillna(0).dot(weights)
        carrier_metrics = carrier_metrics.sort_values('carrier_value_score', ascending=False)
        
        self._carrier_scores_cache = carrier_metrics
        return carrier_metrics

    def generate_optimization_recommendations(self):
        """Generate optimization recommendations based on carrier scores"""
        carrier_scores = self.calculate_carrier_value_score()
        if len(carrier_scores) < 2:
            return []
            
        best = carrier_scores.iloc[0]
        worst = carrier_scores.iloc[-1]
        df = self._get_delivered_data()
        
        worst_orders = df[df['carrier'] == worst['carrier']]
        current_cost = worst_orders['total_cost'].sum()
        potential_cost = len(worst_orders) * best['avg_cost']
        savings = max(0, current_cost - potential_cost)
        
        return [{
            'title': f"Shift orders from {worst['carrier']} to {best['carrier']}",
            'action': f"Pilot 15% of {worst['carrier']} volume to {best['carrier']}",
            'impact': f"Estimated annual saving INR {savings:,.0f}",
            'implementation': 'Pilot then scale',
            'savings': f"INR {savings:,.0f}/year",
            'risk': 'Low',
            'timeline': '6 months'
        }]

    def get_sustainability_metrics(self, scenario='current'):
        """Get sustainability metrics for current or optimized scenario"""
        df = self._get_delivered_data()
        total_co2 = df['co2_emissions'].sum()
        co2_per_order = df['co2_emissions'].mean()
        
        reduction_pct = 20 if scenario == 'optimized' else 0
        if reduction_pct > 0:
            total_co2 *= (1 - reduction_pct / 100)
            co2_per_order *= (1 - reduction_pct / 100)
            
        return {
            'total_co2': total_co2,
            'co2_per_order': co2_per_order,
            'reduction_pct': reduction_pct
        }

    def calculate_green_logistics_benefit(self):
        """Calculate benefits of green logistics initiatives"""
        df = self._get_delivered_data()
        current_fuel_cost = df['fuel_cost'].sum() if 'fuel_cost' in df.columns else 0
        
        ev_adoption = 0.3
        fuel_savings = current_fuel_cost * ev_adoption * 0.6
        maintenance_savings = df['vehicle_maintenance'].sum() * ev_adoption * 0.4 if 'vehicle_maintenance' in df.columns else 0
        total_savings = fuel_savings + maintenance_savings
        
        current_co2 = df['co2_emissions'].sum()
        co2_reduction = current_co2 * ev_adoption * 0.85
        
        ev_investment = 50_000 * ev_adoption * max(1, len(self.vehicles))
        roi = (total_savings / ev_investment) * 100 if ev_investment else 0
        payback_months = int(ev_investment / (total_savings / 12)) if total_savings > 0 else 0
        
        return {
            'cost_savings': total_savings,
            'co2_reduction': co2_reduction,
            'reduction_pct': (co2_reduction / current_co2 * 100) if current_co2 else 0,
            'roi': roi,
            'payback_months': payback_months
        }
