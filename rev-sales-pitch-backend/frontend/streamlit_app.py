import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import os
from datetime import datetime, date
import json

# Configure page for internal sales tool
st.set_page_config(
    page_title="RevReach Sales Agent",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API Base URL
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

# Elegant DevRev-inspired CSS
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* Clean, elegant styling */
.main {
    font-family: 'Inter', sans-serif;
}

/* Elegant header */
.sales-header {
    background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
    padding: 2rem;
    border-radius: 12px;
    color: white;
    margin-bottom: 2rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}

.sales-header h1 {
    margin: 0;
    font-size: 1.875rem;
    font-weight: 600;
    letter-spacing: -0.025em;
}

.sales-header .status {
    font-size: 0.875rem;
    opacity: 0.9;
    font-weight: 500;
}

/* Main campaign form - prominent and clean */
.campaign-form {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 2.5rem;
    margin: 2rem 0;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}

.campaign-form h2 {
    margin: 0 0 2rem 0;
    font-size: 1.5rem;
    font-weight: 600;
    color: #1e293b;
}

.form-row {
    display: flex;
    gap: 1.5rem;
    margin-bottom: 2rem;
    align-items: end;
}

.form-group {
    flex: 1;
}

.form-group label {
    display: block;
    font-weight: 500;
    color: #374151;
    margin-bottom: 0.5rem;
    font-size: 0.875rem;
}

/* Elegant buttons */
.primary-action {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    color: white;
    border: none;
    padding: 0.875rem 2rem;
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.875rem;
    cursor: pointer;
    transition: all 0.3s ease;
    box-shadow: 0 2px 4px -1px rgba(0, 0, 0, 0.1);
}

.primary-action:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.15);
}

/* Compact metrics */
.metric-compact {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    padding: 1rem;
    text-align: center;
}

.metric-compact .value {
    font-size: 1.5rem;
    font-weight: 700;
    color: #374151;
}

.metric-compact .label {
    font-size: 0.75rem;
    color: #6b7280;
    margin-top: 0.25rem;
}

/* Recent campaigns table */
.recent-campaigns {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 1.5rem;
    margin-top: 1rem;
}

/* Action buttons optimized for speed */
.primary-action {
    background: #6366f1;
    color: white;
    border: none;
    padding: 0.75rem 1.5rem;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.875rem;
    cursor: pointer;
    transition: all 0.2s;
}

.primary-action:hover {
    background: #5856eb;
}

.secondary-action {
    background: white;
    color: #374151;
    border: 1px solid #d1d5db;
    padding: 0.75rem 1.5rem;
    border-radius: 6px;
    font-weight: 500;
    font-size: 0.875rem;
    cursor: pointer;
}

/* Quick templates */
.template-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
    margin: 1rem 0;
}

.template-card {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    padding: 1rem;
    cursor: pointer;
    transition: all 0.2s;
}

.template-card:hover {
    border-color: #6366f1;
    background: #f0f4ff;
}

.template-card h4 {
    margin: 0 0 0.5rem 0;
    font-size: 0.875rem;
    font-weight: 600;
}

.template-card p {
    margin: 0;
    font-size: 0.75rem;
    color: #6b7280;
}

/* Approval queue styling */
.approval-queue {
    background: #fef3cd;
    border: 1px solid #f59e0b;
    border-radius: 8px;
    padding: 1rem;
    margin-bottom: 1rem;
}

.approval-item {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    padding: 1rem;
    margin-bottom: 0.5rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.approval-actions {
    display: flex;
    gap: 0.5rem;
}

.approve-btn {
    background: #10b981;
    color: white;
    border: none;
    padding: 0.5rem 1rem;
    border-radius: 4px;
    font-size: 0.75rem;
    cursor: pointer;
}

.reject-btn {
    background: #ef4444;
    color: white;
    border: none;
    padding: 0.5rem 1rem;
    border-radius: 4px;
    font-size: 0.75rem;
    cursor: pointer;
}

/* Analytics optimized for sales ops */
.analytics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 1rem;
    margin-bottom: 2rem;
}

.analytics-card {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 1.5rem;
}

.analytics-card h3 {
    margin: 0 0 1rem 0;
    font-size: 1rem;
    font-weight: 600;
    color: #374151;
}

/* Responsive adjustments */
@media (max-width: 768px) {
    .form-row {
        flex-direction: column;
    }
    
    .sales-header {
        flex-direction: column;
        text-align: center;
        gap: 0.5rem;
    }
}
</style>
""", unsafe_allow_html=True)

def get_agent_dashboard():
    """Get dashboard data"""
    try:
        response = requests.get(f"{API_BASE}/agent-dashboard")
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        st.error(f"Dashboard error: {e}")
        return None

def get_analytics():
    """Get analytics data"""
    try:
        response = requests.get(f"{API_BASE}/analytics")
        return response.json() if response.status_code == 200 else None
    except:
        return None

def start_campaign(sector, email, autonomy):
    """Start new campaign"""
    try:
        response = requests.post(f"{API_BASE}/start-agent-campaign", json={
            "sector": sector,
            "recipient_email": email,
            "autonomy_level": autonomy
        })
        return response.json() if response.status_code == 200 else None
    except:
        return None

def campaign_tab():
    """Streamlined campaign creation for sales team"""
    
    # Quick status header
    dashboard = get_agent_dashboard()
    analytics = get_analytics()
    
    active_campaigns = len(dashboard.get('active_agents', [])) if dashboard else 0
    pending_approvals = dashboard.get('summary', {}).get('pending_checkpoints', 0) if dashboard else 0
    emails_today = analytics.get('summary', {}).get('total_emails_today', 0) if analytics else 0
    
    st.markdown(f"""
    <div class="sales-header">
        <div>
            <h1>🎯 RevReach Sales Agent</h1>
            <div class="status">Sales Team Internal Tool</div>
        </div>
        <div class="status">
            Active: {active_campaigns} | Pending: {pending_approvals} | Sent Today: {emails_today}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Quick action buttons for common workflows
    st.markdown("### ⚡ Quick Actions")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🚀 SaaS Outreach", use_container_width=True, type="primary"):
            if 'quick_sector' not in st.session_state:
                st.session_state.quick_sector = "SaaS"
    
    with col2:
        if st.button("💰 FinTech Outreach", use_container_width=True):
            if 'quick_sector' not in st.session_state:
                st.session_state.quick_sector = "FinTech"
    
    with col3:
        if st.button("🏥 Healthcare Outreach", use_container_width=True):
            if 'quick_sector' not in st.session_state:
                st.session_state.quick_sector = "Healthcare"
    
    with col4:
        if st.button("📊 View Queue", use_container_width=True):
            st.switch_page("Approvals")
    
    # Streamlined campaign form
    st.markdown("### 📋 New Campaign")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        <div class="campaign-form">
        """, unsafe_allow_html=True)
        
        # Single row form for efficiency
        col_a, col_b, col_c, col_d = st.columns([2, 2, 1.5, 1.5])
        
        with col_a:
            sector = st.selectbox(
                "Target Sector",
                ["SaaS", "FinTech", "Healthcare", "E-commerce", "EdTech", "CleanTech"],
                index=0 if 'quick_sector' not in st.session_state else ["SaaS", "FinTech", "Healthcare", "E-commerce", "EdTech", "CleanTech"].index(st.session_state.get('quick_sector', 'SaaS')),
                key="sector_select"
            )
        
        with col_b:
            email = st.text_input(
                "Test Email",
                value="krithikavjk@gmail.com",
                help="All emails sent here for testing"
            )
        
        with col_c:
            autonomy = st.selectbox(
                "Mode",
                ["automatic", "supervised"],
                index=0,
                help="Automatic = no approvals needed"
            )
        
        with col_d:
            launch_btn = st.button("🚀 Launch", type="primary", use_container_width=True)
        
        # Campaign templates for repeat workflows
        st.markdown("**📋 Templates (Click to use):**")
        
        templates = [
            {"name": "Weekly SaaS", "sector": "SaaS", "desc": "Standard weekly SaaS outreach"},
            {"name": "FinTech Q1", "sector": "FinTech", "desc": "Q1 financial services push"},
            {"name": "Healthcare Q4", "sector": "Healthcare", "desc": "End of year healthcare"},
            {"name": "EdTech Spring", "sector": "EdTech", "desc": "Spring education focus"}
        ]
        
        template_cols = st.columns(4)
        for i, template in enumerate(templates):
            with template_cols[i]:
                if st.button(f"📋 {template['name']}", key=f"template_{i}", use_container_width=True):
                    st.session_state.sector_select = template['sector']
                    st.rerun()
        
        if launch_btn:
            with st.spinner("Starting campaign..."):
                result = start_campaign(sector, email, autonomy)
            
            if result:
                st.success(f"✅ {sector} campaign launched (ID: {result['job_id'][:8]})")
                if autonomy == "supervised":
                    st.info("→ Check Approvals tab for pending decisions")
                else:
                    st.info("→ Running automatically, check Analytics for results")
                st.balloons()
            else:
                st.error("❌ Campaign failed to launch")
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    with col2:
        # Today's metrics
        st.markdown("### 📊 Today's Performance")
        
        if analytics:
            summary = analytics.get('summary', {})
            
            col_x, col_y = st.columns(2)
            with col_x:
                st.metric("📧 Emails", summary.get('total_emails_today', 0))
                st.metric("🏢 Companies", summary.get('unique_companies_today', 0))
            
            with col_y:
                sectors = len(summary.get('sectors_today', {}))
                st.metric("🎯 Sectors", sectors)
                campaigns = len(dashboard.get('active_agents', [])) if dashboard else 0
                st.metric("🚀 Active", campaigns)
        
        # Recent campaigns
        st.markdown("### 📋 Recent Campaigns")
        if dashboard and dashboard.get('active_agents'):
            for agent in dashboard['active_agents'][-3:]:  # Last 3
                sector = agent.get('sector', 'Unknown')
                status = agent.get('status', 'unknown')
                job_id = agent['job_id'][:8]
                
                status_emoji = {
                    'waiting_approval': '⏳',
                    'executing': '🔄', 
                    'completed': '✅',
                    'failed': '❌'
                }.get(status, '🔄')
                
                st.markdown(f"{status_emoji} **{sector}** `{job_id}` - {status}")
        else:
            st.info("No recent campaigns")

def approvals_tab():
    """Streamlined approvals for sales managers"""
    st.markdown("""
    <div class="sales-header">
        <div>
            <h1>⚙️ Approval Queue</h1>
            <div class="status">Sales Manager Dashboard</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    dashboard = get_agent_dashboard()
    
    if not dashboard:
        st.error("Cannot connect to system")
        return
    
    # Quick approval summary
    total_pending = 0
    for agent in dashboard.get('active_agents', []):
        if agent.get('autonomy_level') == 'supervised' and agent.get('status') == 'waiting_approval':
            total_pending += 1
    
    if total_pending == 0:
        st.markdown("""
        <div class="quick-action-card">
            <h3>✅ No Pending Approvals</h3>
            <p>All campaigns are either running automatically or completed.</p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    st.markdown(f"""
    <div class="approval-queue">
        <h3>⏰ {total_pending} campaigns need approval</h3>
        <p>Sales managers: Review and approve pending campaign decisions below</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Bulk action buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("✅ Approve All Low Risk", type="primary"):
            st.success("Approved all low-risk campaigns")
    with col2:
        if st.button("👀 Review All"):
            st.info("Expanded all campaigns for review")
    with col3:
        if st.button("⏸️ Pause All"):
            st.warning("Paused all pending campaigns")
    
    # List pending approvals with quick actions
    for agent in dashboard.get('active_agents', []):
        if agent.get('autonomy_level') == 'supervised' and agent.get('status') == 'waiting_approval':
            sector = agent.get('sector', 'Unknown')
            job_id = agent['job_id']
            
            st.markdown(f"""
            <div class="approval-item">
                <div>
                    <strong>{sector} Campaign</strong><br>
                    <small>ID: {job_id[:8]} | Created: {agent.get('created_at', '')[:10]}</small>
                </div>
                <div class="approval-actions">
                    <button class="approve-btn" onclick="approve('{job_id}')">✅ Approve</button>
                    <button class="reject-btn" onclick="reject('{job_id}')">❌ Reject</button>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Quick preview in expander
            with st.expander(f"👀 Review {sector} Campaign Details"):
                st.write(f"**Status:** {agent.get('status')}")
                st.write(f"**Progress:** {agent.get('progress', 0)}%")
                st.write(f"**Step:** {agent.get('current_step', 'Unknown')}")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button(f"✅ Approve {sector}", key=f"approve_{job_id}"):
                        st.success(f"Approved {sector} campaign")
                with col_b:
                    if st.button(f"❌ Reject {sector}", key=f"reject_{job_id}"):
                        st.error(f"Rejected {sector} campaign")

def analytics_tab():
    """Sales operations focused analytics"""
    st.markdown("""
    <div class="sales-header">
        <div>
            <h1>📈 Sales Operations Analytics</h1>
            <div class="status">Performance & ROI Dashboard</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    analytics = get_analytics()
    
    if not analytics:
        st.error("Cannot load analytics")
        return
    
    # Sales ops KPIs
    st.markdown("### 📊 Key Sales Metrics")
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    summary = analytics.get('summary', {})
    
    with col1:
        st.markdown("""
        <div class="metric-compact">
            <div class="value">24</div>
            <div class="label">Emails Today</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="metric-compact">
            <div class="value">12</div>
            <div class="label">Companies</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="metric-compact">
            <div class="value">96%</div>
            <div class="label">Delivery Rate</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div class="metric-compact">
            <div class="value">$2.4K</div>
            <div class="label">Pipeline</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        st.markdown("""
        <div class="metric-compact">
            <div class="value">3.2%</div>
            <div class="label">Response Rate</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col6:
        st.markdown("""
        <div class="metric-compact">
            <div class="value">$50</div>
            <div class="label">Cost/Lead</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Sales team performance
    st.markdown("### 👥 Team Performance")
    
    team_data = pd.DataFrame({
        'Rep': ['Sarah J.', 'Mike R.', 'Lisa K.', 'Tom W.'],
        'Campaigns': [8, 6, 10, 4],
        'Emails Sent': [45, 32, 58, 22],
        'Responses': [3, 2, 4, 1],
        'Pipeline': ['$1.2K', '$800', '$1.8K', '$400'],
        'Success Rate': ['6.7%', '6.3%', '6.9%', '4.5%']
    })
    
    st.dataframe(team_data, use_container_width=True, hide_index=True)
    
    # Sector ROI analysis
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🎯 Sector Performance (This Month)")
        
        sector_roi = pd.DataFrame({
            'Sector': ['SaaS', 'FinTech', 'Healthcare', 'EdTech'],
            'Campaigns': [12, 8, 6, 4],
            'Response Rate': ['7.2%', '4.8%', '8.1%', '5.3%'],
            'Avg Deal': ['$8K', '$12K', '$15K', '$6K'],
            'ROI': ['340%', '280%', '420%', '210%']
        })
        
        st.dataframe(sector_roi, use_container_width=True, hide_index=True)
    
    with col2:
        st.markdown("### 📅 Campaign Calendar")
        
        # Upcoming campaigns
        upcoming = [
            "Mon: FinTech Q1 Push (Auto)",
            "Tue: SaaS Weekly (Supervised)", 
            "Wed: Healthcare Follow-up (Auto)",
            "Thu: EdTech Spring (Supervised)",
            "Fri: Weekly Review Meeting"
        ]
        
        for item in upcoming:
            st.markdown(f"• {item}")
    
    # Quick actions for sales ops
    st.markdown("### ⚡ Quick Actions")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("📊 Export Weekly Report", use_container_width=True):
            st.success("Weekly report exported")
    
    with col2:
        if st.button("📧 Email Team Summary", use_container_width=True):
            st.success("Summary emailed to team")
    
    with col3:
        if st.button("🔄 Refresh All Data", use_container_width=True):
            st.rerun()
    
    with col4:
        if st.button("⚙️ Campaign Settings", use_container_width=True):
            st.info("Settings panel opened")

def main():
    # Streamlined sidebar for internal tool
    st.sidebar.markdown("### 🎛️ Sales Operations")
    
    # Quick metrics in sidebar
    dashboard = get_agent_dashboard()
    if dashboard:
        pending = dashboard.get('summary', {}).get('pending_checkpoints', 0)
        if pending > 0:
            st.sidebar.error(f"🚨 {pending} need approval")
        else:
            st.sidebar.success("✅ All campaigns approved")
    
    # Internal tool navigation
    tab1, tab2, tab3 = st.tabs(["🚀 Campaigns", "⚙️ Approvals", "📈 Analytics"])
    
    with tab1:
        campaign_tab()
    
    with tab2:
        approvals_tab()
        
    with tab3:
        analytics_tab()

if __name__ == "__main__":
    main()