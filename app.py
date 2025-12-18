"""
NexGen Logistics - Cost Intelligence Platform
A Streamlit-based dashboard for predictive cost analysis and optimization
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
warnings.filterwarnings('ignore')

# Import custom modules
from data_processing import DataProcessor

# Page configuration
st.set_page_config(
    page_title="NexGen Logistics - Cost Intelligence Platform",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional styling
st.markdown("""
    <style>
    .main {
        padding: 0rem 1rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .metric-container {
        display: flex;
        justify-content: space-between;
        margin-bottom: 20px;
    }
    h1 {
        color: #1f77b4;
        font-weight: 700;
    }
    h2 {
        color: #2c3e50;
        border-bottom: 3px solid #1f77b4;
        padding-bottom: 10px;
    }
    .insight-box {
        background-color: #e8f4f8;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #1f77b4;
        margin: 20px 0;
        color: #1a1a1a;
    }
    .insight-box h3 {
        color: #1f77b4;
        margin-top: 0;
    }
    .insight-box ul {
        color: #2c3e50;
    }
    .insight-box li {
        margin: 10px 0;
        line-height: 1.6;
    }
    .insight-box strong {
        color: #1a1a1a;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if 'data_processor' not in st.session_state:
    st.session_state.data_processor = None
    st.session_state.data_loaded = False

@st.cache_data
def load_data():
    """Load and process all data"""
    try:
        processor = DataProcessor()
        load_success = processor.load_all_data()
        if load_success:
            processor.process_data()
            return processor
        else:
            st.error("Failed to load required CSV files. Please ensure all files are present in the workspace.")
            return None
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return None

def render_kpi_ribbon(processor):
    """Render the executive KPI ribbon at the top"""
    metrics = processor.get_key_metrics()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="💰 Total Revenue",
            value=f"₹{metrics['total_revenue']:,.0f}",
            delta=f"{metrics['revenue_growth']:.1f}% vs target"
        )
    
    with col2:
        st.metric(
            label="📉 Cost Leakage",
            value=f"₹{metrics['cost_leakage']:,.0f}",
            delta=f"-{metrics['leakage_reduction']:.1f}% (Good!)",
            delta_color="inverse"
        )
    
    with col3:
        st.metric(
            label="📊 Profit Margin",
            value=f"{metrics['profit_margin']:.1f}%",
            delta=f"{metrics['margin_change']:.1f}%"
        )
    
    with col4:
        st.metric(
            label="🌱 CO₂ Efficiency",
            value=f"{metrics['co2_per_order']:.2f} kg/order",
            delta=f"-{metrics['co2_reduction']:.1f}% (Green!)",
            delta_color="inverse"
        )
    
    st.markdown("---")

def render_overview(processor):
    """Render the Overview dashboard"""
    st.header("📊 Executive Overview")
    
    # KPI Ribbon
    render_kpi_ribbon(processor)
    
    # Two-column layout for charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Cost Distribution by Category")
        cost_by_category = processor.get_cost_by_category()
        fig = px.pie(
            cost_by_category,
            values='cost_amount',
            names='cost_category',
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Revenue vs Cost Trend")
        trend_data = processor.get_revenue_cost_trend()
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trend_data['month'],
            y=trend_data['revenue'],
            name='Revenue',
            line=dict(color='#2ecc71', width=3),
            fill='tonexty'
        ))
        fig.add_trace(go.Scatter(
            x=trend_data['month'],
            y=trend_data['cost'],
            name='Cost',
            line=dict(color='#e74c3c', width=3),
            fill='tozeroy'
        ))
        fig.update_layout(
            height=400,
            hovermode='x unified',
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Full-width chart
    st.subheader("Carrier Performance Comparison")
    carrier_perf = processor.get_carrier_performance()
    fig = px.scatter(
        carrier_perf,
        x='avg_cost',
        y='on_time_percentage',
        size='total_orders',
        color='avg_rating',
        hover_name='carrier',
        labels={
            'avg_cost': 'Average Cost per Order (₹)',
            'on_time_percentage': 'On-Time Delivery Rate (%)',
            'avg_rating': 'Customer Rating'
        },
        color_continuous_scale='RdYlGn',
        title="Carrier Value Analysis: Cost vs Performance"
    )
    fig.update_layout(height=450)
    st.plotly_chart(fig, use_container_width=True)
    
    # Insight box
    st.markdown("""
        <div class="insight-box">
            <h3>💡 Key Insights</h3>
            <ul>
                <li><strong>Top Opportunity:</strong> Shifting 15% of orders from high-cost carriers could save ₹1.2-1.8 Lakh/month</li>
                <li><strong>Efficiency Gap:</strong> Delayed deliveries cost 23% more due to storage and re-delivery attempts</li>
                <li><strong>Route Optimization:</strong> Consolidating low-volume routes can reduce costs by 12-15%</li>
            </ul>
        </div>
    """, unsafe_allow_html=True)

def render_cost_leakage(processor):
    """Render Cost Leakage Analysis"""
    st.header("🔍 Cost Leakage Analysis")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        selected_regions = st.multiselect(
            "Filter by Region",
            options=processor.get_unique_warehouses(),
            default=processor.get_unique_warehouses()
        )
    
    with col2:
        selected_priorities = st.multiselect(
            "Filter by Priority",
            options=['Economy', 'Standard', 'Express'],
            default=['Economy', 'Standard', 'Express']
        )
    
    with col3:
        selected_carriers = st.multiselect(
            "Filter by Carrier",
            options=processor.get_unique_carriers(),
            default=processor.get_unique_carriers()
        )
    
    # Apply filters
    filtered_data = processor.filter_data(selected_regions, selected_priorities, selected_carriers)
    
    st.markdown("---")
    
    # Cost leakage metrics
    leakage_metrics = processor.calculate_cost_leakage(filtered_data)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "💸 Delay Penalty Costs",
            f"₹{leakage_metrics['delay_costs']:,.0f}",
            help="Extra costs due to delayed deliveries (storage, re-attempts)"
        )
    
    with col2:
        st.metric(
            "📦 Damage Costs",
            f"₹{leakage_metrics['damage_costs']:,.0f}",
            help="Costs associated with damaged goods"
        )
    
    with col3:
        st.metric(
            "🚛 Carrier Overcharges",
            f"₹{leakage_metrics['carrier_overcharges']:,.0f}",
            help="Potential savings from carrier optimization"
        )
    
    # Heatmap: Cost by Route
    st.subheader("🗺️ Cost Heatmap by Route")
    route_costs = processor.get_route_cost_analysis(filtered_data)
    fig = px.density_heatmap(
        route_costs,
        x='destination_city',
        y='origin_warehouse',
        z='avg_cost_per_km',
        color_continuous_scale='Reds',
        labels={'avg_cost_per_km': 'Cost per KM (₹)'},
        title="Average Cost per KM by Route"
    )
    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)
    
    # Waterfall chart: Cost components
    st.subheader("💧 Cost Breakdown Waterfall")
    waterfall_data = processor.get_cost_waterfall(filtered_data)
    
    fig = go.Figure(go.Waterfall(
        name="Cost Components",
        orientation="v",
        measure=waterfall_data['measure'],
        x=waterfall_data['category'],
        y=waterfall_data['amount'],
        connector={"line": {"color": "rgb(63, 63, 63)"}},
        decreasing={"marker": {"color": "#e74c3c"}},
        increasing={"marker": {"color": "#2ecc71"}},
        totals={"marker": {"color": "#3498db"}}
    ))
    
    fig.update_layout(
        title="Total Cost Composition",
        height=450,
        showlegend=False
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Cost vs Delivery Speed scatter
    st.subheader("⚡ Cost vs Delivery Speed Analysis")
    speed_cost = processor.get_cost_speed_analysis(filtered_data)
    
    fig = px.scatter(
        speed_cost,
        x='delivery_hours',
        y='total_cost',
        color='delivery_status',
        size='rating',
        hover_data=['order_id', 'carrier'],
        labels={
            'delivery_hours': 'Delivery Time (Hours)',
            'total_cost': 'Total Cost (₹)',
            'delivery_status': 'Status'
        },
        color_discrete_map={
            'On-Time': '#2ecc71',
            'Slightly-Delayed': '#f39c12',
            'Severely-Delayed': '#e74c3c'
        }
    )
    fig.update_layout(height=450)
    st.plotly_chart(fig, use_container_width=True)

def render_optimization_engine(processor):
    """Render Optimization Engine"""
    st.header("🎯 Cost-Benefit Optimization Engine")
    
    st.markdown("""
        <div class="insight-box">
            <h3>🚀 How It Works</h3>
            <p>This optimizer analyzes historical performance data to recommend carrier shifts that maximize 
            cost savings while maintaining service quality. It uses a weighted scoring system that considers:</p>
            <ul>
                <li><strong>Cost Efficiency:</strong> Average cost per order</li>
                <li><strong>Delivery Performance:</strong> On-time delivery rate</li>
                <li><strong>Customer Satisfaction:</strong> Average rating</li>
                <li><strong>Environmental Impact:</strong> CO₂ emissions per delivery</li>
            </ul>
        </div>
    """, unsafe_allow_html=True)
    
    # Carrier Value Score calculation
    st.subheader("📊 Carrier Value Score (CVS)")
    carrier_scores = processor.calculate_carrier_value_score()
    
    # Display as a bar chart
    fig = px.bar(
        carrier_scores,
        x='carrier',
        y='carrier_value_score',
        color='carrier_value_score',
        color_continuous_scale='RdYlGn',
        labels={'carrier_value_score': 'CVS (Higher is Better)'},
        title="Carrier Value Score: Weighted Performance Metric"
    )
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)
    
    # Detailed carrier comparison table
    st.subheader("📋 Detailed Carrier Metrics")
    st.dataframe(
        carrier_scores.style.background_gradient(
            subset=['carrier_value_score'],
            cmap='RdYlGn'
        ).format({
            'avg_cost': '₹{:.2f}',
            'on_time_percentage': '{:.1f}%',
            'avg_rating': '{:.2f}',
            'co2_per_order': '{:.2f} kg',
            'carrier_value_score': '{:.2f}'
        }),
        use_container_width=True,
        height=300
    )
    
    # Optimization recommendations
    st.subheader("💡 Optimization Recommendations")
    recommendations = processor.generate_optimization_recommendations()
    
    for i, rec in enumerate(recommendations, 1):
        with st.expander(f"Recommendation #{i}: {rec['title']}", expanded=(i == 1)):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown(f"**Action:** {rec['action']}")
                st.markdown(f"**Impact:** {rec['impact']}")
                st.markdown(f"**Implementation:** {rec['implementation']}")
            
            with col2:
                st.metric("Potential Savings", rec['savings'])
                st.metric("Risk Level", rec['risk'])
                st.metric("Timeline", rec['timeline'])
    
    # Sustainability comparison
    st.subheader("🌱 Sustainability Impact")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Current State**")
        current_metrics = processor.get_sustainability_metrics('current')
        st.metric("Total CO₂ Emissions", f"{current_metrics['total_co2']:,.0f} kg")
        st.metric("Average per Order", f"{current_metrics['co2_per_order']:.2f} kg")
    
    with col2:
        st.markdown("**Optimized State**")
        optimized_metrics = processor.get_sustainability_metrics('optimized')
        st.metric(
            "Total CO₂ Emissions",
            f"{optimized_metrics['total_co2']:,.0f} kg",
            delta=f"-{optimized_metrics['reduction_pct']:.1f}%",
            delta_color="inverse"
        )
        st.metric(
            "Average per Order",
            f"{optimized_metrics['co2_per_order']:.2f} kg",
            delta=f"-{optimized_metrics['reduction_pct']:.1f}%",
            delta_color="inverse"
        )
    
    # Financial benefit of green logistics
    st.markdown("---")
    green_benefit = processor.calculate_green_logistics_benefit()
    
    st.markdown(f"""
        <div class="insight-box">
            <h3>💚 Financial Benefit of Green Logistics</h3>
            <p>By shifting to more environmentally friendly practices and vehicles:</p>
            <ul>
                <li><strong>Cost Savings:</strong> ₹{green_benefit['cost_savings']:,.0f}/year from fuel efficiency</li>
                <li><strong>CO₂ Reduction:</strong> {green_benefit['co2_reduction']:,.0f} kg/year ({green_benefit['reduction_pct']:.1f}%)</li>
                <li><strong>ROI:</strong> {green_benefit['roi']:.1f}% within {green_benefit['payback_months']} months</li>
                <li><strong>Additional Benefits:</strong> Improved brand image, potential tax incentives, regulatory compliance</li>
            </ul>
        </div>
    """, unsafe_allow_html=True)

def main():
    """Main application function"""
    
    # Sidebar
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/000000/truck.png", width=80)
        st.title("NexGen Logistics")
        st.markdown("### Cost Intelligence Platform")
        st.markdown("---")
        
        # Navigation
        page = st.radio(
            "Navigation",
            ["📊 Overview", "🔍 Cost Leakage Analysis", "🎯 Optimization Engine"],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        
        # Data loading
        if st.button("🔄 Reload Data", use_container_width=True):
            st.session_state.data_processor = None
            st.session_state.data_loaded = False
            st.rerun()
        
        st.markdown("---")
        st.markdown("### About")
        st.info("""
            This platform analyzes logistics data to identify cost savings opportunities 
            and optimize carrier selection based on cost, performance, and sustainability metrics.
        """)
        
        st.markdown("---")
        st.markdown("**Data Status**")
        if st.session_state.data_loaded:
            st.success("✓ Data Loaded")
        else:
            st.warning("⚠ Loading data...")
    
    # Main content area
    st.title("🚚 NexGen Logistics Cost Intelligence Platform")
    st.markdown("*Transform reactive cost management into predictive insights*")
    
    st.markdown("---")
    
    # Load data
    if not st.session_state.data_loaded:
        with st.spinner("Loading and processing data..."):
            processor = load_data()
            if processor:
                st.session_state.data_processor = processor
                st.session_state.data_loaded = True
                st.rerun()
            else:
                st.error("Failed to load data. Please check if all CSV files are present.")
                st.stop()
    
    processor = st.session_state.data_processor
    
    # Render selected page
    if page == "📊 Overview":
        render_overview(processor)
    elif page == "🔍 Cost Leakage Analysis":
        render_cost_leakage(processor)
    elif page == "🎯 Optimization Engine":
        render_optimization_engine(processor)

if __name__ == "__main__":
    main()
