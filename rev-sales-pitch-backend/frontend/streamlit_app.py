import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import os
from datetime import datetime
import json

# Configure page
st.set_page_config(
    page_title="RevReach Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API Base URL - Production ready
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

# Custom CSS for better styling
st.markdown("""
<style>
.main-header {
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    padding: 2rem;
    border-radius: 10px;
    color: white;
    text-align: center;
    margin-bottom: 2rem;
}
</style>
""", unsafe_allow_html=True)

def get_agent_dashboard():
    """Get dashboard data with error handling"""
    try:
        response = requests.get(f"{API_BASE}/agent-dashboard")
        if response.status_code == 200:
            data = response.json()
            
            # Ensure we have the expected structure
            if 'summary' not in data:
                # Create summary from available data
                active_agents = data.get('active_agents', [])
                data['summary'] = {
                    'active_agents': len(active_agents),
                    'pending_checkpoints': data.get('pending_checkpoints', 0),
                    'emails_sent_today': 0,
                    'total_campaigns_today': 0
                }
            
            return data
        return None
    except Exception as e:
        st.error(f"Dashboard error: {e}")
        return None

def get_agent_status(job_id):
    """Get specific agent status"""
    try:
        response = requests.get(f"{API_BASE}/agent-status/{job_id}")
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

def approve_checkpoint(checkpoint_id, decision, feedback="", modified_content=""):
    """Approve/reject checkpoint with better error handling"""
    try:
        payload = {
            "checkpoint_id": checkpoint_id,
            "decision": decision,
            "feedback": feedback
        }
        
        if modified_content:
            payload["modified_content"] = modified_content
            
        response = requests.post(f"{API_BASE}/approve-checkpoint", json=payload)
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        st.error(f"Approval failed: {e}")
        return None

def agent_intervention(job_id, action):
    """Intervene in agent execution"""
    try:
        response = requests.post(f"{API_BASE}/agent-intervention", json={
            "job_id": job_id,
            "action": action
        })
        return response.json() if response.status_code == 200 else None
    except:
        return None

def campaign_tab():
    """Clean campaign creation tab"""
    st.header("🚀 Start New Campaign")
    
    col1, col2 = st.columns([1.2, 1])
    
    with col1:
        st.markdown("### 📋 Campaign Configuration")
        
        sector = st.selectbox(
            "🎯 Target Sector",
            ["SaaS", "FinTech", "Healthcare", "E-commerce", "EdTech", "CleanTech"]
        )
        
        st.markdown("### 📧 Testing Setup")
        st.info("🧪 **Testing Mode**: All generated emails will be sent to your email below for review.")
        
        email = st.text_input(
            "Your Email Address",
            value="krithiiyer2000@gmail.com"
        )
        
        st.markdown("### 🤖 Agent Control Level")
        autonomy = st.selectbox(
            "How much human oversight?",
            ["supervised", "guided", "autonomous"],
            index=0
        )
        
        if autonomy == "supervised":
            st.success("👁️ **Supervised**: Agent asks for approval at every step.")
        elif autonomy == "guided":
            st.info("🎯 **Guided**: Agent asks for approval on key decisions.")
        elif autonomy == "autonomous":
            st.warning("🚀 **Autonomous**: Agent works independently.")
        
        st.markdown("---")
        if st.button("🚀 Launch Campaign", type="primary", use_container_width=True):
            with st.spinner("🤖 Starting your agent..."):
                result = start_campaign(sector, email, autonomy)
                
            if result:
                st.success("✅ **Campaign Started Successfully!**")
                st.info(f"**Job ID:** `{result['job_id']}`")
                st.balloons()
            else:
                st.error("❌ Failed to start campaign.")
    
    with col2:
        st.markdown("### 🎯 Agent Workflow")
        
        st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 20px; border-radius: 12px; color: white; margin-bottom: 20px;">
            <h4 style="color: white; margin-top: 0;">🤖 What Your Agent Will Do</h4>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("**1. 🎯 Plan Campaign** - Selects companies → **You approve**")
        st.markdown("**2. 📝 Generate Emails** - Writes content → **You review**")
        st.markdown("**3. 📤 Send Emails** - Final approval → **Sends to inbox**")
        st.markdown("**4. ✅ Complete** - Campaign finished → **View results**")

def control_tab():
    """Simple control tab - NO EXPANDERS"""
    st.header("⚙️ Campaign Approvals")
    
    st.markdown("### ℹ️ What do I need to approve?")
    st.markdown("**🎯 Campaign Plan** - Review target companies")
    st.markdown("**📧 Email Content** - Review generated emails")
    st.markdown("**📤 Final Send** - Approve before sending")
    
    dashboard = get_agent_dashboard()
    
    if not dashboard or not dashboard['active_agents']:
        st.info("📭 No active campaigns requiring approval")
        return
    
    has_checkpoints = False
    
    for agent in dashboard['active_agents']:
        agent_details = get_agent_status(agent['job_id'])
        
        if agent_details and agent_details.get('pending_checkpoints'):
            has_checkpoints = True
            st.subheader(f"🔔 Approval Needed: Campaign {agent['job_id'][:8]}...")
            
            for checkpoint in agent_details['pending_checkpoints']:
                st.markdown(f"**Type:** {checkpoint['type'].replace('_', ' ').title()}")
                st.markdown(f"**Risk:** {checkpoint['risk_level'].upper()}")
                st.markdown(f"**Message:** {checkpoint['message']}")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button(f"✅ Approve", key=f"approve_{checkpoint['checkpoint_id']}", type="primary"):
                        result = approve_checkpoint(checkpoint['checkpoint_id'], 'approve', "Approved via UI")
                        if result:
                            st.success("✅ Approved!")
                            st.rerun()
                
                with col2:
                    if st.button(f"✏️ Modify", key=f"modify_{checkpoint['checkpoint_id']}"):
                        result = approve_checkpoint(checkpoint['checkpoint_id'], 'modify', "Modified via UI")
                        if result:
                            st.success("✏️ Modified!")
                            st.rerun()
                
                with col3:
                    if st.button(f"❌ Reject", key=f"reject_{checkpoint['checkpoint_id']}"):
                        result = approve_checkpoint(checkpoint['checkpoint_id'], 'reject', "Rejected via UI")
                        if result:
                            st.error("❌ Rejected!")
                            st.rerun()
                
                st.divider()
    
    if not has_checkpoints:
        st.info("📋 All approvals handled!")

def monitor_tab():
    """Minimal monitor tab - NO EXPANDERS AT ALL"""
    st.header("📊 Campaign Monitoring")
    
    dashboard = get_agent_dashboard()
    
    if not dashboard:
        st.error("❌ Cannot connect to Agent API")
        return
    
    # Check for urgent approvals
    urgent_approvals = 0
    for agent in dashboard.get('active_agents', []):
        agent_details = get_agent_status(agent['job_id'])
        if agent_details and agent_details.get('pending_checkpoints'):
            urgent_approvals += len(agent_details['pending_checkpoints'])
    
    if urgent_approvals > 0:
        st.error(f"🚨 URGENT: {urgent_approvals} approval(s) needed! → Go to Approvals tab")
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    summary = dashboard.get('summary', {})
    
    with col1:
        st.metric("🤖 Active Agents", summary.get('active_agents', 0))
    with col2:
        st.metric("⏳ Pending Approvals", urgent_approvals)
    with col3:
        st.metric("📧 Emails Today", summary.get('emails_sent_today', 0))
    with col4:
        st.metric("🎯 Campaigns Today", summary.get('total_campaigns_today', 0))
    
    # Active agents - SIMPLE DISPLAY
    if dashboard.get('active_agents'):
        st.markdown("### 🔄 Active Campaigns")
        
        for agent in dashboard['active_agents']:
            st.markdown(f"**Campaign {agent['job_id'][:8]}... ({agent['status']})**")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                progress = agent['progress'] / 100
                st.progress(progress, text=f"Progress: {agent['progress']}%")
                st.write(f"Status: {agent['status']}")
                st.write(f"Step: {agent.get('current_step', 'Unknown')}")
                
                if agent['status'] == 'waiting_approval':
                    st.error("⏳ Approval needed! → Check Approvals tab")
            
            with col2:
                if agent['status'] == 'executing':
                    if st.button(f"⏸️ Pause", key=f"pause_{agent['job_id']}"):
                        agent_intervention(agent['job_id'], 'pause')
                        st.rerun()
                elif agent['status'] == 'paused':
                    if st.button(f"▶️ Resume", key=f"resume_{agent['job_id']}"):
                        agent_intervention(agent['job_id'], 'resume')
                        st.rerun()
                
                if st.button(f"🛑 Stop", key=f"stop_{agent['job_id']}"):
                    agent_intervention(agent['job_id'], 'stop')
                    st.rerun()
            
            st.divider()
    
    else:
        st.info("📭 No active campaigns. Start one in the Campaign tab!")

def analytics_tab():
    """Simple analytics tab"""
    st.header("📈 Campaign Analytics")
    
    dashboard = get_agent_dashboard()
    
    if not dashboard:
        st.error("❌ Cannot load analytics data")
        return
    
    st.success("✅ System operating normally")
    
    if dashboard.get('active_agents'):
        st.subheader("🤖 Agent Performance")
        
        agent_data = []
        for agent in dashboard['active_agents']:
            agent_data.append({
                'Agent ID': agent['job_id'][:8],
                'Status': agent['status'],
                'Progress': agent['progress']
            })
        
        if agent_data:
            df = pd.DataFrame(agent_data)
            fig = px.bar(df, x='Agent ID', y='Progress', title="Agent Progress")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df, use_container_width=True)
    else:
        st.info("📭 No active agents to analyze")

def main():
    st.markdown("""
    <div class="main-header">
        <h1 style="margin: 0; font-size: 3rem;">🤖 RevReach Agent</h1>
        <p style="margin: 0.5rem 0 0 0; font-size: 1.2rem;">
            AI Sales Campaign Manager with Human Oversight
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    st.sidebar.title("🎛️ Control Panel")
    
    # Check for urgent approvals
    dashboard = get_agent_dashboard()
    urgent_approvals = 0
    if dashboard and dashboard.get('active_agents'):
        for agent in dashboard['active_agents']:
            agent_details = get_agent_status(agent['job_id'])
            if agent_details and agent_details.get('pending_checkpoints'):
                urgent_approvals += len(agent_details['pending_checkpoints'])
    
    if urgent_approvals > 0:
        st.sidebar.error(f"🚨 {urgent_approvals} APPROVAL(S) NEEDED!")
    else:
        st.sidebar.success("✅ No approvals needed")
    
    if st.sidebar.button("🔄 Refresh Now"):
        st.rerun()
    
    auto_refresh = st.sidebar.checkbox("🔄 Auto-refresh (5s)", value=True)
    
    if auto_refresh:
        time.sleep(5)
        st.rerun()
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs(["🚀 Campaign", "⚙️ Approvals", "📊 Monitor", "📈 Analytics"])
    
    with tab1:
        campaign_tab()
    
    with tab2:
        control_tab()
        
    with tab3:
        monitor_tab()
        
    with tab4:
        analytics_tab()

if __name__ == "__main__":
    main()