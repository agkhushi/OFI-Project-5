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

    def _standardize_cols(self, df):
        # convert columns to snake_case lower
        df = df.rename(columns=lambda x: x.strip())
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
        # Standardize column names for joining
        orders = self.orders.copy()
        delivery = self.delivery.copy()
        routes = self.routes.copy()
        vehicles = self.vehicles.copy()
        costs = self.costs.copy()

        # Ensure order_id exists in all
        for df in [orders, delivery, routes, costs]:
            if 'order_id' not in df.columns:
                raise ValueError('One of the required files lacks Order_ID column after normalization')

        # Parse dates
        if 'order_date' in orders.columns:
            orders['order_date'] = pd.to_datetime(orders['order_date'], errors='coerce')

        # Build total_cost from cost_breakdown (costs are wide columns)
        cost_cols = [c for c in costs.columns if c != 'order_id']
        costs['total_cost'] = costs[cost_cols].sum(axis=1)

        # Merge orders <- routes (both keyed by order_id)
        merged = orders.merge(routes, on='order_id', how='left', suffixes=('', '_route'))

        # Merge delivery performance
        merged = merged.merge(delivery, on='order_id', how='left', suffixes=('', '_perf'))

        # Merge cost breakdown (wide) and total
        merged = merged.merge(costs[['order_id', 'total_cost'] + cost_cols], on='order_id', how='left')

        # Normalize column names to app-friendly names
        # origin_warehouse <- origin, destination_city <- destination
        if 'origin' in merged.columns:
            merged.rename(columns={'origin': 'origin_warehouse'}, inplace=True)
        if 'destination' in merged.columns:
            merged.rename(columns={'destination': 'destination_city'}, inplace=True)

        # Delivery status: create `status` field used by app
        if 'delivery_status' in merged.columns:
            merged['status'] = merged['delivery_status'].apply(lambda x: 'Delivered' if pd.notna(x) else 'Pending')
        else:
            merged['status'] = 'Delivered'

        # Compute on_time_percentage from promised vs actual days if present
        if 'promised_delivery_days' in merged.columns and 'actual_delivery_days' in merged.columns:
            merged['on_time_percentage'] = (merged['promised_delivery_days'] / merged['actual_delivery_days']) * 100
            merged['on_time_percentage'] = merged['on_time_percentage'].clip(upper=100)
        else:
            merged['on_time_percentage'] = 100

        # Distance
        if 'distance_km' in merged.columns:
            merged['distance_km'] = pd.to_numeric(merged['distance_km'], errors='coerce')
        elif 'distance' in merged.columns:
            merged['distance_km'] = pd.to_numeric(merged['distance'], errors='coerce')
        else:
            merged['distance_km'] = np.nan

        # Revenue (orders file uses order_value_inr or order_value)
        if 'order_value_inr' in merged.columns:
            merged['revenue'] = pd.to_numeric(merged['order_value_inr'], errors='coerce')
        elif 'order_value' in merged.columns:
            merged['revenue'] = pd.to_numeric(merged['order_value'], errors='coerce')
        else:
            merged['revenue'] = np.nan

        # Use delivery cost if present to fill missing total_cost
        if 'delivery_cost_inr' in merged.columns:
            merged['delivery_cost_inr'] = pd.to_numeric(merged['delivery_cost_inr'], errors='coerce')
            merged['total_cost'] = merged['total_cost'].fillna(merged['delivery_cost_inr'])

        # If total_cost still missing, fill with sum of available cost cols
        if merged['total_cost'].isnull().any():
            merged['total_cost'] = merged['total_cost'].fillna(merged[cost_cols].sum(axis=1))

        # CO2 emissions estimate: use average co2_per_km from fleet if available, else estimate from route fuel consumption
        if 'co2_emissions_kg_per_km' in vehicles.columns:
            avg_co2 = vehicles['co2_emissions_kg_per_km'].mean()
            merged['co2_per_km'] = avg_co2
        else:
            merged['co2_per_km'] = vehicles.filter(like='co2').mean().mean() if not vehicles.empty else 0.45

        # Final co2 per order
        merged['co2_emissions'] = merged['distance_km'] * merged['co2_per_km']

        # Profit and derived metrics
        merged['profit'] = merged['revenue'] - merged['total_cost']
        merged['profit_margin'] = (merged['profit'] / merged['revenue']) * 100
        merged['cost_per_km'] = merged['total_cost'] / merged['distance_km']
        merged['cost_per_km'].replace([np.inf, -np.inf], np.nan, inplace=True)

        # Cost of inefficiency: estimate from delays and quality issues
        if 'promised_delivery_days' in merged.columns and 'actual_delivery_days' in merged.columns:
            merged['delay_days'] = (merged['actual_delivery_days'] - merged['promised_delivery_days']).clip(lower=0)
        else:
            merged['delay_days'] = 0

        # Use a heuristic: each delay day costs 5% of delivery cost + 50 INR storage
        merged['delay_cost'] = 0
        if 'delivery_cost_inr' in merged.columns:
            merged['delay_cost'] = merged['delay_days'] * (merged['delivery_cost_inr'] * 0.05 + 50)
        else:
            merged['delay_cost'] = merged['delay_days'] * 100

        # Quality issues -> damage cost estimate
        def _damage_cost(row):
            q = row.get('quality_issue', None)
            if pd.isna(q) or q == 'Perfect':
                return 0
            # fallback: 15% of revenue if quality issue exists
            return 0.15 * row.get('revenue', 0)

        merged['damage_cost'] = merged.apply(_damage_cost, axis=1)

        merged['cost_of_inefficiency'] = merged['delay_cost'].fillna(0) + merged['damage_cost'].fillna(0)

        # Create columns expected by app functions for compatibility
        if 'customer_rating' in merged.columns:
            merged.rename(columns={'customer_rating': 'rating'}, inplace=True)

        # ensure priority column exists
        if 'priority' not in merged.columns and 'priority' in orders.columns:
            merged['priority'] = orders['priority']

        # Month/Year for trends
        if 'order_date' in merged.columns:
            merged['month'] = merged['order_date'].dt.to_period('M')
            merged['year'] = merged['order_date'].dt.year
        else:
            merged['month'] = pd.NaT
            merged['year'] = 0

        # Provide fallback columns used in app
        merged['origin_warehouse'] = merged.get('origin_warehouse', merged.get('origin_warehouse'))
        merged['destination_city'] = merged.get('destination_city', merged.get('destination_city'))

        # Fill missing simple numeric fields
        numeric_cols = merged.select_dtypes(include=[np.number]).columns
        merged[numeric_cols] = merged[numeric_cols].fillna(0)

        self.merged_data = merged
        return merged

    # --- Methods used by app ---
    def get_key_metrics(self):
        df = self.merged_data[self.merged_data['status'] == 'Delivered'].copy()
        total_revenue = df['revenue'].sum()
        total_cost = df['total_cost'].sum()
        profit_margin = (total_revenue - total_cost) / total_revenue * 100 if total_revenue != 0 else 0
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
        # cost breakdown is wide in this dataset
        costs = self.costs.copy()
        cost_cols = [c for c in costs.columns if c not in ('order_id', 'total_cost')]
        summary = costs[cost_cols].sum().reset_index()
        summary.columns = ['cost_category', 'cost_amount']
        return summary

    def get_revenue_cost_trend(self):
        df = self.merged_data[self.merged_data['status'] == 'Delivered'].copy()
        monthly = df.groupby('month').agg({'revenue': 'sum', 'total_cost': 'sum'}).reset_index()
        monthly['month'] = monthly['month'].astype(str)
        monthly.columns = ['month', 'revenue', 'cost']
        return monthly

    def get_carrier_performance(self):
        df = self.merged_data[self.merged_data['status'] == 'Delivered'].copy()
        carrier_perf = df.groupby('carrier').agg({'total_cost': 'mean', 'on_time_percentage': 'mean', 'order_id': 'count', 'rating': 'mean'}).reset_index()
        carrier_perf.columns = ['carrier', 'avg_cost', 'on_time_percentage', 'total_orders', 'avg_rating']
        return carrier_perf

    def get_unique_warehouses(self):
        if 'origin_warehouse' in self.merged_data.columns:
            return list(self.merged_data['origin_warehouse'].unique())
        return []

    def get_unique_carriers(self):
        if 'carrier' in self.merged_data.columns:
            return list(self.merged_data['carrier'].unique())
        return []

    def filter_data(self, regions, priorities, carriers):
        df = self.merged_data.copy()
        if regions:
            df = df[df['origin_warehouse'].isin(regions)]
        if priorities:
            df = df[df['priority'].isin(priorities)]
        if carriers:
            df = df[df['carrier'].isin(carriers)]
        return df

    def calculate_cost_leakage(self, df):
        delay_costs = df['delay_cost'].sum()
        damage_costs = df['damage_cost'].sum()
        # Carrier overcharges heuristic: difference between avg cost_per_km and min
        carrier_costs = df.groupby('carrier')['cost_per_km'].mean()
        if not carrier_costs.empty:
            min_cost = carrier_costs.min()
            df['potential_savings'] = (df['cost_per_km'] - min_cost) * df['distance_km']
            carrier_overcharges = df['potential_savings'].sum()
        else:
            carrier_overcharges = 0
        return {'delay_costs': delay_costs, 'damage_costs': damage_costs, 'carrier_overcharges': max(0, carrier_overcharges)}

    def get_route_cost_analysis(self, df):
        df_filtered = df[df['status'] == 'Delivered'].copy()
        route_analysis = df_filtered.groupby(['origin_warehouse', 'destination_city']).agg({'cost_per_km': 'mean', 'total_cost': 'mean', 'order_id': 'count'}).reset_index()
        route_analysis.columns = ['origin_warehouse', 'destination_city', 'avg_cost_per_km', 'avg_total_cost', 'order_count']
        return route_analysis

    def get_cost_waterfall(self, df):
        df_filtered = df[df['status'] == 'Delivered'].copy()
        # use the cost columns from costs
        cost_cols = [c for c in self.costs.columns if c not in ('order_id', 'total_cost')]
        amounts = [df_filtered[c].mean() if c in df_filtered.columns else 0 for c in cost_cols]
        categories = cost_cols
        waterfall = pd.DataFrame({'category': categories + ['Total'], 'amount': amounts + [sum(amounts)], 'measure': ['relative'] * len(categories) + ['total']})
        return waterfall

    def get_cost_speed_analysis(self, df):
        df_filtered = df[df['status'] == 'Delivered'].copy()
        # compute delivery_hours from promised/actual days
        if 'actual_delivery_days' in df_filtered.columns:
            df_filtered['delivery_hours'] = df_filtered['actual_delivery_days'] * 24
        else:
            df_filtered['delivery_hours'] = df_filtered.get('traffic_delay_minutes', 0) / 60
        result = df_filtered[['order_id', 'delivery_hours', 'total_cost', 'delivery_status', 'rating', 'carrier']].copy()
        return result

    def calculate_carrier_value_score(self):
        df = self.merged_data[self.merged_data['status'] == 'Delivered'].copy()
        carrier_metrics = df.groupby('carrier').agg({'total_cost': 'mean', 'on_time_percentage': 'mean', 'rating': 'mean', 'co2_emissions': 'mean', 'order_id': 'count'}).reset_index()
        carrier_metrics.columns = ['carrier', 'avg_cost', 'on_time_percentage', 'avg_rating', 'co2_per_order', 'total_orders']
        # Normalize
        cost_max = carrier_metrics['avg_cost'].replace(0, np.nan).max()
        carrier_metrics['cost_score'] = (1 - carrier_metrics['avg_cost'] / cost_max) * 100
        carrier_metrics['delivery_score'] = carrier_metrics['on_time_percentage']
        carrier_metrics['satisfaction_score'] = (carrier_metrics['avg_rating'] / 5) * 100
        co2_max = carrier_metrics['co2_per_order'].replace(0, np.nan).max()
        carrier_metrics['sustainability_score'] = (1 - carrier_metrics['co2_per_order'] / co2_max) * 100
        # weights
        carrier_metrics['carrier_value_score'] = carrier_metrics[['cost_score', 'delivery_score', 'satisfaction_score', 'sustainability_score']].fillna(0).dot(np.array([0.4, 0.3, 0.2, 0.1]))
        carrier_metrics = carrier_metrics.sort_values('carrier_value_score', ascending=False)
        return carrier_metrics

    def generate_optimization_recommendations(self):
        carrier_scores = self.calculate_carrier_value_score()
        if carrier_scores.shape[0] < 2:
            return []
        best = carrier_scores.iloc[0]
        worst = carrier_scores.iloc[-1]
        df = self.merged_data[self.merged_data['status'] == 'Delivered'].copy()
        worst_orders = df[df['carrier'] == worst['carrier']]
        current_cost = worst_orders['total_cost'].sum()
        potential_cost = len(worst_orders) * best['avg_cost']
        savings = current_cost - potential_cost
        rec = [{
            'title': f"Shift orders from {worst['carrier']} to {best['carrier']}",
            'action': f"Pilot 15% of {worst['carrier']} volume to {best['carrier']}",
            'impact': f"Estimated annual saving INR {savings:,.0f}",
            'implementation': 'Pilot then scale',
            'savings': f"INR {savings:,.0f}/year",
            'risk': 'Low',
            'timeline': '6 months'
        }]
        return rec

    def get_sustainability_metrics(self, scenario='current'):
        df = self.merged_data[self.merged_data['status'] == 'Delivered'].copy()
        total_co2 = df['co2_emissions'].sum()
        co2_per_order = df['co2_emissions'].mean()
        if scenario == 'optimized':
            reduction_pct = 20
            total_co2 = total_co2 * (1 - reduction_pct / 100)
            co2_per_order = co2_per_order * (1 - reduction_pct / 100)
        else:
            reduction_pct = 0
        return {'total_co2': total_co2, 'co2_per_order': co2_per_order, 'reduction_pct': reduction_pct}

    def calculate_green_logistics_benefit(self):
        df = self.merged_data[self.merged_data['status'] == 'Delivered'].copy()
        current_fuel_cost = df.get('fuel_cost', df.get('fuel_consumption_l', pd.Series(0))).sum()
        ev_adoption = 0.3
        fuel_savings = current_fuel_cost * ev_adoption * 0.6
        maintenance_savings = df.get('vehicle_maintenance', pd.Series(0)).sum() * ev_adoption * 0.4
        total_savings = fuel_savings + maintenance_savings
        current_co2 = df['co2_emissions'].sum()
        co2_reduction = current_co2 * ev_adoption * 0.85
        ev_investment = 50_000 * ev_adoption * max(1, len(self.vehicles))
        roi = (total_savings / ev_investment) * 100 if ev_investment else 0
        payback_months = int(ev_investment / (total_savings / 12)) if total_savings else 0
        return {'cost_savings': total_savings, 'co2_reduction': co2_reduction, 'reduction_pct': (co2_reduction / current_co2 * 100) if current_co2 else 0, 'roi': roi, 'payback_months': payback_months}
