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

# Enhanced CSS for clean, simple styling
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

.stButton > button {
    border-radius: 6px;
    border: none;
    font-weight: 500;
}

.stSuccess, .stWarning, .stError, .stInfo {
    border-radius: 6px;
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

def approve_plan_checkpoint(checkpoint_id, selected_companies, feedback=""):
    """Approve plan checkpoint with selected companies"""
    try:
        payload = {
            "checkpoint_id": checkpoint_id,
            "selected_companies": selected_companies,
            "feedback": feedback
        }
        
        response = requests.post(f"{API_BASE}/approve-plan-checkpoint", json=payload)
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        st.error(f"Plan approval failed: {e}")
        return None

def approve_email_checkpoint(checkpoint_id, email_decisions):
    """Approve email checkpoint with individual email decisions"""
    try:
        payload = {
            "checkpoint_id": checkpoint_id,
            "email_decisions": email_decisions
        }
        
        response = requests.post(f"{API_BASE}/approve-email-checkpoint", json=payload)
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        st.error(f"Email approval failed: {e}")
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

def render_plan_approval_checkpoint(checkpoint):
    """Simple plan approval with company selection"""
    st.subheader("🎯 Step 1: Select Target Companies")
    
    plan_data = checkpoint.get('data', {}).get('plan', checkpoint.get('data', {}))
    companies = plan_data.get('companies', plan_data.get('original_companies', []))
    
    st.info(f"📋 **{len(companies)} companies discovered in {plan_data.get('sector', 'SaaS')} sector**")
    
    # Initialize selected companies in session state
    if f"selected_companies_{checkpoint['checkpoint_id']}" not in st.session_state:
        st.session_state[f"selected_companies_{checkpoint['checkpoint_id']}"] = companies.copy()
    
    # Company selection with checkboxes
    st.markdown("### 📝 Select Companies to Target:")
    selected_companies = []
    
    for company in companies:
        # Show risk level
        risk_level = "🔴 HIGH" if company in ["Slack Technologies", "Figma Inc"] else "🟡 MEDIUM"
        
        is_selected = st.checkbox(
            f"{company} ({risk_level})",
            value=company in st.session_state[f"selected_companies_{checkpoint['checkpoint_id']}"],
            key=f"company_select_{checkpoint['checkpoint_id']}_{company}"
        )
        
        if is_selected:
            selected_companies.append(company)
    
    # Update session state
    st.session_state[f"selected_companies_{checkpoint['checkpoint_id']}"] = selected_companies
    
    # Show selection summary
    if selected_companies != companies:
        excluded = [c for c in companies if c not in selected_companies]
        st.warning(f"⚠️ {len(excluded)} companies excluded: {', '.join(excluded)}")
    
    st.success(f"✅ {len(selected_companies)} companies selected")
    
    # Approval buttons
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🚀 Continue with Selected Companies", type="primary", key=f"approve_companies_{checkpoint['checkpoint_id']}", use_container_width=True):
            if selected_companies:
                # Update checkpoint data with selections
                checkpoint['data']['selected_companies'] = selected_companies
                
                result = approve_checkpoint(checkpoint['checkpoint_id'], 'approve', f"Selected {len(selected_companies)} companies")
                if result:
                    st.success("✅ Companies approved! Generating emails...")
                    time.sleep(1)  # Brief pause for user feedback
                    st.rerun()
            else:
                st.error("❌ Please select at least one company")
    
    with col2:
        if st.button("❌ Cancel Campaign", key=f"cancel_companies_{checkpoint['checkpoint_id']}", use_container_width=True):
            result = approve_checkpoint(checkpoint['checkpoint_id'], 'reject', "Campaign cancelled")
            if result:
                st.error("❌ Campaign cancelled")
                st.rerun()

def render_email_preview_checkpoint(checkpoint):
    """Simple email preview with email selection"""
    st.subheader("📧 Step 2: Review & Select Emails")
    
    data = checkpoint.get('data', {})
    emails = data.get('emails', {})
    
    if not emails:
        st.warning("No emails found")
        return
    
    st.info(f"📝 **{len(emails)} emails generated and ready for review**")
    
    # Initialize selected emails in session state
    if f"selected_emails_{checkpoint['checkpoint_id']}" not in st.session_state:
        st.session_state[f"selected_emails_{checkpoint['checkpoint_id']}"] = list(emails.keys())
    
    # Email selection with previews
    st.markdown("### 📧 Select Emails to Send:")
    selected_emails = []
    
    for company, email_content in emails.items():
        # Checkbox for email selection
        is_selected = st.checkbox(
            f"📧 Email to **{company}**",
            value=company in st.session_state[f"selected_emails_{checkpoint['checkpoint_id']}"],
            key=f"email_select_{checkpoint['checkpoint_id']}_{company}"
        )
        
        if is_selected:
            selected_emails.append(company)
        
        # Email preview in expander
        with st.expander(f"👀 Preview Email to {company}", expanded=False):
            # Show risk warning for high-risk companies
            if company in ["Slack Technologies", "Figma Inc"]:
                st.warning("🔴 **HIGH RISK COMPANY** - Extra caution recommended")
            
            # Show email subject
            st.markdown("**📨 Subject:** DevRev Partnership Opportunity for " + company)
            
            # Show email content
            st.markdown("**📄 Email Content:**")
            st.text_area(
                "Email",
                value=email_content,
                height=150,
                disabled=True,
                key=f"email_preview_{checkpoint['checkpoint_id']}_{company}"
            )
            
            # Quick stats
            word_count = len(email_content.split())
            st.caption(f"📊 {word_count} words • Professional tone • Personalized")
    
    # Update session state
    st.session_state[f"selected_emails_{checkpoint['checkpoint_id']}"] = selected_emails
    
    # Show selection summary
    if selected_emails != list(emails.keys()):
        excluded = [c for c in emails.keys() if c not in selected_emails]
        st.warning(f"⚠️ {len(excluded)} emails excluded: {', '.join(excluded)}")
    
    st.success(f"✅ {len(selected_emails)} emails selected for sending")
    
    # Approval buttons
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🚀 Continue with Selected Emails", type="primary", key=f"approve_emails_{checkpoint['checkpoint_id']}", use_container_width=True):
            if selected_emails:
                # Update checkpoint data with selected emails only
                selected_email_content = {company: emails[company] for company in selected_emails}
                checkpoint['data']['selected_emails'] = selected_email_content
                
                result = approve_checkpoint(checkpoint['checkpoint_id'], 'approve', f"Selected {len(selected_emails)} emails")
                if result:
                    st.success("✅ Emails approved! Moving to final send...")
                    time.sleep(1)
                    st.rerun()
            else:
                st.error("❌ Please select at least one email")
    
    with col2:
        if st.button("❌ Cancel Campaign", key=f"cancel_emails_{checkpoint['checkpoint_id']}", use_container_width=True):
            result = approve_checkpoint(checkpoint['checkpoint_id'], 'reject', "Campaign cancelled")
            if result:
                st.error("❌ Campaign cancelled")
                st.rerun()

def render_bulk_send_checkpoint(checkpoint):
    """Simple final send confirmation"""
    st.subheader("🚀 Step 3: Final Send Confirmation")
    
    data = checkpoint.get('data', {})
    emails = data.get('emails', data.get('selected_emails', {}))
    
    if not emails:
        st.warning("No emails to send")
        return
    
    # Final summary
    st.success(f"🎯 **Ready to send {len(emails)} emails**")
    
    # Show final list
    st.markdown("### 📤 Final Email List:")
    for i, company in enumerate(emails.keys(), 1):
        st.markdown(f"{i}. 📧 **{company}**")
    
    # Important notes
    st.markdown("### ⚠️ Important:")
    st.info("🧪 **Test Mode:** All emails will be sent to your test inbox for review")
    st.warning("🔒 **This action cannot be undone** - emails will be sent immediately")
    
    # Final confirmation
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🚀 Send All Emails Now", type="primary", key=f"send_emails_{checkpoint['checkpoint_id']}", use_container_width=True):
            result = approve_checkpoint(checkpoint['checkpoint_id'], 'approve', f"Sending {len(emails)} emails")
            if result:
                st.success("✅ Emails sent successfully! Campaign completed!")
                st.balloons()
                time.sleep(2)
                st.rerun()
    
    with col2:
        if st.button("❌ Cancel Send", key=f"cancel_send_{checkpoint['checkpoint_id']}", use_container_width=True):
            result = approve_checkpoint(checkpoint['checkpoint_id'], 'reject', "Send cancelled")
            if result:
                st.error("❌ Send cancelled")
                st.rerun()

def control_tab():
    """Simplified approval interface"""
    st.header("⚙️ Campaign Approvals")
    
    dashboard = get_agent_dashboard()
    
    if not dashboard or not dashboard['active_agents']:
        st.info("📭 No active campaigns requiring approval")
        st.markdown("Start a new campaign in the **Campaign** tab to see approvals here.")
        return
    
    # Check for pending approvals
    has_checkpoints = False
    
    for agent in dashboard['active_agents']:
        agent_details = get_agent_status(agent['job_id'])
        
        if agent_details and agent_details.get('pending_checkpoints'):
            has_checkpoints = True
            
            # Clean campaign header
            st.markdown(f"## 🔔 Campaign {agent['job_id'][:8]}... - {agent['status']}")
            
            for checkpoint in agent_details['pending_checkpoints']:
                checkpoint_type = checkpoint.get('type', 'unknown')
                
                # Route to appropriate simple renderer
                if checkpoint_type == 'plan_approval':
                    render_plan_approval_checkpoint(checkpoint)
                elif checkpoint_type == 'email_preview':
                    render_email_preview_checkpoint(checkpoint)
                elif checkpoint_type == 'bulk_send_approval':
                    render_bulk_send_checkpoint(checkpoint)
                else:
                    # Simple fallback
                    st.markdown("### ⚠️ Approval Required")
                    st.info(checkpoint.get('message', 'Please review and approve'))
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Approve", key=f"approve_{checkpoint['checkpoint_id']}", type="primary"):
                            result = approve_checkpoint(checkpoint['checkpoint_id'], 'approve', "Approved")
                            if result:
                                st.success("✅ Approved!")
                                st.rerun()
                    
                    with col2:
                        if st.button("❌ Reject", key=f"reject_{checkpoint['checkpoint_id']}"):
                            result = approve_checkpoint(checkpoint['checkpoint_id'], 'reject', "Rejected")
                            if result:
                                st.error("❌ Rejected!")
                                st.rerun()
                
                st.markdown("---")
    
    if not has_checkpoints:
        st.success("✅ All approvals complete! Check the Monitor tab for campaign progress.")

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
                st.markdown("📋 **Next Steps:** Go to the **Approvals** tab to review agent decisions.")
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
        
        st.markdown("**1. 🎯 Plan Campaign** - Discovers companies → **You select targets**")
        st.markdown("**2. 📝 Generate Emails** - Writes personalized content → **You review each email**")
        st.markdown("**3. 📤 Send Emails** - Final batch approval → **Sends to your inbox**")
        st.markdown("**4. ✅ Complete** - Campaign finished → **View results**")
        
        st.markdown("### 🛡️ Safety Features")
        st.markdown("• **Individual email approval**")
        st.markdown("• **Company-level risk assessment**")
        st.markdown("• **Content modification requests**")
        st.markdown("• **Test mode delivery**")

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
    
    auto_refresh = st.sidebar.checkbox("🔄 Auto-refresh (5s)", value=False)
    
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