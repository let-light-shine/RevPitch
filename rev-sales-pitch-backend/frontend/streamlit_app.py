import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import os
from datetime import datetime, date
import json

# Configure page
st.set_page_config(
    page_title="RevReach Sales Agent",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API Base URL
#API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
API_BASE = "https://revpitch.onrender.com"

# Simple, clean CSS - minimal styling only
# Replace the existing CSS section with this:
st.markdown("""
<style>
.main {
    padding-top: 2rem;
}

.stButton > button {
    width: 100%;
    height: 3rem;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    border: none;
    border-radius: 8px;
    color: white;
    font-weight: 600;
    transition: all 0.3s ease;
}

.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(139, 92, 246, 0.3);
}

.revreach-header {
    background: linear-gradient(135deg, #4c1d95, #6366f1, #8b5cf6);
    padding: 40px 30px;
    border-radius: 20px;
    margin-bottom: 30px;
    color: white;
    text-align: center;
    box-shadow: 0 20px 40px rgba(139, 92, 246, 0.2);
}

.revreach-header h1 {
    font-size: 3.5rem;
    font-weight: 800;
    margin-bottom: 10px;
    letter-spacing: -2px;
}

.revreach-header h3 {
    font-size: 1.4rem;
    font-weight: 400;
    opacity: 0.95;
    margin-bottom: 0;
    font-style: italic;
}

.field-label {
    font-size: 18px;
    font-weight: 600;
    color: #1f2937;
    margin-bottom: 8px;
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

def get_agent_status(job_id):
    """Get specific agent status"""
    try:
        response = requests.get(f"{API_BASE}/agent-status/{job_id}")
        return response.json() if response.status_code == 200 else None
    except:
        return None


def campaigns_tab():
    """Clean campaign creation"""
    
    # Enhanced header with navy blue background
    st.markdown("""
    <div class="revreach-header">
        <h1>📈 RevReach Agent</h1>
        <h3>Launch Hyper-Personalized Campaigns with AI & Confidence</h3>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Campaign Configuration section
    st.header("Campaign Configuration")

    # Update the sectors list
    DEVREV_SECTORS = [
    "SaaS", "FinTech", "Healthcare Tech", "E-commerce", "EdTech", 
    "Enterprise Software", "Developer Tools", "Customer Success", 
    "Product Management", "API-First Companies", "Data & Analytics", 
    "DevOps & Infrastructure", "Collaboration Tools", "Marketing Technology", 
    "Gaming & Entertainment", "Cybersecurity", "Real Estate Tech", 
    "Travel & Hospitality", "Food & Delivery", "IoT & Hardware"
]
    
    # Target Sector with info button
    st.markdown('<p class="field-label">Target Sector <span style="color: #666; cursor: help;" title="The sector helps our AI agent discover relevant companies and tailor email context to industry-specific challenges.">ℹ️</span></p>', unsafe_allow_html=True)
    sector = st.selectbox(
        "Target Sector",
        DEVREV_SECTORS,
        index=0,
        help="The sector helps our AI agent discover relevant companies and tailor email context to industry-specific challenges.",
        label_visibility="collapsed"
    )
    
    # Test Email with info button
    st.markdown('<p class="field-label">Test Email <span style="color: #666; cursor: help;" title="In testing mode, all campaign emails will be routed here. In a production environment, this would be the actual recipient\'s email.">ℹ️</span></p>', unsafe_allow_html=True)
    email = st.text_input(
        "Test Email",
        placeholder="your.email@company.com",
        help="In testing mode, all campaign emails will be routed here. In a production environment, this would be the actual recipient's email.",
        label_visibility="collapsed"
    )
    
    # Subtle testing mode notice right after email field
    st.markdown("""
    <div style="background-color: #fef3c7; padding: 8px 12px; border-radius: 4px; margin-top: 5px; margin-bottom: 15px;">
        <span style="color: #92400e; font-size: 14px;">📧 Testing Mode: All emails will be sent to this email address</span>
    </div>
    """, unsafe_allow_html=True)
    
    # Campaign Mode with info button
    st.markdown('<p class="field-label">Campaign Mode <span style="color: #666; cursor: help;" title="Supervised: Requires human approval at key stages. Automatic: AI agent proceeds autonomously with minimal interruptions.">ℹ️</span></p>', unsafe_allow_html=True)
    autonomy = st.selectbox(
        "Campaign Mode",
        [
            "Supervised - requires approval at key stages",
            "Automatic - agent takes care end to end"
        ],
        index=0,
        help="Supervised: Requires human approval at key stages (plan, email preview, bulk send). Ideal for high-risk campaigns or new users. | Automatic: AI agent proceeds autonomously with minimal interruptions. Best for low-risk, high-volume campaigns once confidence is established.",
        label_visibility="collapsed"
    )
    
    # Extract the actual mode value for backend
    autonomy_value = "supervised" if "Supervised" in autonomy else "automatic"
    
    # Campaign Summary (conceptual)
    st.markdown("### 📊 Campaign Summary")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Estimated Companies", "5")
    with col2:
        st.metric("Estimated Duration", "~3 mins")
    with col3:
        mode_color = "🟡" if autonomy_value == "supervised" else "🟢"
        st.metric("Mode", f"{mode_color} {autonomy_value.title()}")
    
    # Launch button
    if st.button("🚀 Launch Campaign", type="primary"):
        if not email:
            st.error("Please enter your email address")
        elif "@" not in email:
            st.error("Please enter a valid email address")
        else:
            with st.spinner(f"Starting {sector} campaign..."):
                result = start_campaign(sector, email, autonomy_value)
            
            if result:
                st.success(f"✅ {sector} campaign launched successfully!")
                st.info(f"Campaign ID: {result['job_id'][:8]}")
                
                if autonomy_value == "supervised":
                    st.warning("⏳ Approval required - Check Approvals tab")
                else:
                    st.info("🤖 Running automatically - Check Analytics tab")
                
                st.balloons()
            else:
                st.error("❌ Campaign launch failed")

def approve_checkpoint(checkpoint_id, decision, feedback=None, selected_companies=None, selected_emails=None):
    """Approve a checkpoint with selections"""
    try:
        payload = {
            "checkpoint_id": checkpoint_id,
            "decision": decision,
            "feedback": feedback
        }
        
        if selected_companies:
            payload["selected_companies"] = selected_companies
        if selected_emails:
            payload["selected_emails"] = selected_emails
            
        response = requests.post(f"{API_BASE}/approve-checkpoint", json=payload)
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        st.error(f"Approval error: {e}")
        return None

def approvals_tab():
    """Refined 3-step approval workflow"""
    st.title("⚙️ Approvals")
    st.write("Review and approve pending campaign decisions")
    
    # Add refresh button at the top
    col1, col2, col3 = st.columns([1, 1, 1])
    with col3:
        if st.button("🔄 Refresh", type="secondary", use_container_width=True):
            st.rerun()

    dashboard = get_agent_dashboard()
    
    if not dashboard:
        st.error("Cannot connect to system")
        st.info("💡 **Troubleshooting**: Make sure the backend API is running on the correct port")
        return
    
    # Debug section (collapsible)
    with st.expander("🔍 Debug Information", expanded=False):
        st.json(dashboard)
    
    # Get all active agents (not just waiting for approval)
    active_agents = dashboard.get('active_agents', [])
    
    if not active_agents:
        st.success("✅ No active campaigns")
        st.info("Start a new campaign from the Campaigns tab")
        return
    
    # Show progress for all active agents
    campaigns_shown = False
    
    for agent in active_agents:
        job_id = agent['job_id']
        sector = agent.get('sector', 'Unknown')
        status = agent.get('status', 'unknown')
        
        st.markdown(f"### 📋 {sector} Campaign - {job_id[:8]}")
        
        # Always show progress bar for active campaigns
        if status == 'waiting_approval':
            # Agent is waiting for approval - show current step
            agent_details = get_agent_status(job_id)
            if agent_details and agent_details.get('pending_checkpoints'):
                checkpoint = agent_details['pending_checkpoints'][0]
                checkpoint_type = checkpoint['type']
                
                if checkpoint_type == 'plan_approval':
                    render_step_1_company_selection(checkpoint)
                elif checkpoint_type == 'email_preview':
                    render_step_2_email_review(checkpoint)
                elif checkpoint_type == 'bulk_send_approval':
                    render_step_3_final_confirmation(checkpoint)
                campaigns_shown = True
        
        elif status in ['generating_emails', 'processing']:
            # Agent is processing between steps
            render_progress_bar(2, 3)  # Show step 2 progress
            st.info("🔄 **Generating personalized emails...** This may take a few moments.")
            st.markdown("The AI agent is creating tailored email content for each selected company. Please wait while this completes.")
            
            # Auto-refresh every 5 seconds
            st.markdown("*This page will automatically refresh when emails are ready for review.*")
            time.sleep(2)
            st.rerun()
            campaigns_shown = True
            
        elif status == 'executing':
            # Campaign is running
            progress = agent.get('progress', 0)
            st.info(f"🚀 **Campaign executing** - {progress}% complete")

            if progress < 100:
                st.markdown("*This page will automatically refresh to show completion status.*")
                time.sleep(3)
                st.rerun()
            campaigns_shown = True
            
        elif status == 'completed':
            # Campaign completed
            st.success("✅ **Campaign completed successfully!**")
            campaigns_shown = True
        
        elif status == 'planning':
            # Agent is stuck in planning - show manual recovery options
            st.warning("⚠️ **Campaign stuck in planning phase**")
            
            # Show manual recovery steps
            st.info("**Manual Recovery Steps:**")
            st.markdown("""
            1. **Wait 2-3 minutes** - Sometimes the agent is just slow to create checkpoints
            2. **Try starting a new campaign** - The old one will be replaced
            3. **Check backend logs** - Look for any error messages
            4. **Clear browser cache** - Sometimes helps with stuck states
            """)
            
            # Simple refresh and restart options
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button(f"🔄 Wait & Refresh", key=f"refresh_{job_id}", type="primary"):
                    with st.spinner("Waiting 10 seconds then refreshing..."):
                        time.sleep(10)
                        st.rerun()
            
            with col2:
                if st.button(f"🆕 Start New Campaign", key=f"new_{job_id}"):
                    st.info("Go to the **Campaigns** tab and start a new campaign")
                    st.markdown("The new campaign will replace this stuck one automatically.")
            
            # Show campaign age
            try:
                created_at = agent.get('created_at', '')
                if created_at:
                    from datetime import datetime
                    created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    age = datetime.now() - created_time
                    st.caption(f"Campaign age: {age.seconds // 60} minutes")
                    
                    if age.seconds > 300:  # 5 minutes
                        st.error("🚨 Campaign has been stuck for over 5 minutes - definitely needs intervention")
            except:
                pass
            
            campaigns_shown = True
                
        else:
            # Unknown status
            st.warning(f"⚠️ **Campaign status:** {status}")
            campaigns_shown = True
    
    if not campaigns_shown:
        st.success("✅ No pending approvals")
        st.info("All campaigns are running smoothly")

    st.markdown("---")
    if st.button("🔄 Refresh Page", type="primary", use_container_width=True):
        st.rerun()

def render_progress_bar(current_step, total_steps=3):
    """Render progress bar for approval steps"""
    progress_percentage = (current_step / total_steps) * 100
    
    st.markdown(f"""
    <div style="background-color: #f0f2f6; border-radius: 10px; padding: 10px; margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="font-weight: 600; color: #1f2937;">Approval Progress</span>
            <span style="font-size: 14px; color: #6b7280;">Step {current_step} of {total_steps}</span>
        </div>
        <div style="background-color: #e5e7eb; border-radius: 8px; height: 8px;">
            <div style="background-color: #10b981; height: 8px; border-radius: 8px; width: {progress_percentage}%; transition: width 0.3s ease;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def get_company_priority_info(company_name, companies_with_risk_data=None):
    """Get priority level and description from backend API data"""
    # Handle case where companies_with_risk_data is not available
    if not companies_with_risk_data:
        return {
            "level": "🟡 MEDIUM PRIORITY",
            "description": "Standard business prospect with potential for partnership.",
            "risk": "Standard business prospect"
        }
    
    # Find company data from backend
    for company_data in companies_with_risk_data:
        if company_data['name'] == company_name:
            risk_level = company_data.get('risk_level', 'MEDIUM')
            risk_reason = company_data.get('risk_reason', 'Standard business prospect')
            
            # Convert backend risk levels to display format
            if risk_level == 'HIGH':
                level_display = "🔴 HIGH PRIORITY"
            elif risk_level == 'LOW':
                level_display = "🟢 LOW PRIORITY"
            else:  # MEDIUM or default
                level_display = "🟡 MEDIUM PRIORITY"
            
            return {
                "level": level_display,
                "description": risk_reason,
                "risk": risk_reason
            }
    
    # Fallback if company not found in backend data
    return {
        "level": "🟡 MEDIUM PRIORITY",
        "description": "Standard business prospect with potential for partnership.",
        "risk": "Standard business prospect"
    }

def render_step_1_company_selection(checkpoint):
    """Step 1: Enhanced Target Company Selection"""
    # Progress bar
    render_progress_bar(1, 3)
    
    st.subheader("🎯 Step 1: Select Target Companies")
    
    data = checkpoint.get('data', {})
    companies_with_risk = data.get('companies_with_risk', [])
    companies = data.get('companies', [])
    
    # Use companies_with_risk if available, fallback to companies
    if companies_with_risk:
        company_list = [comp['name'] for comp in companies_with_risk]
    else:
        company_list = companies
    
    st.info(f"📋 **{len(company_list)} companies discovered in {data.get('sector', 'SaaS')} sector**")
    
    # Initialize selected companies in session state (all selected by default)
    session_key = f"selected_companies_{checkpoint['checkpoint_id']}"
    if session_key not in st.session_state:
        st.session_state[session_key] = company_list.copy()
    
    # Company selection with enhanced UI
    st.markdown("### 📝 Select Companies to Target:")
    st.markdown("*All companies are pre-selected. Uncheck to exclude from campaign.*")
    
    selected_companies = []
    
    # Create columns for better layout
    for i, company in enumerate(company_list):
        # Get enhanced priority info from backend data
        priority_info = get_company_priority_info(company, companies_with_risk)
        
        # Create checkbox with company info
        col1, col2 = st.columns([0.1, 0.9])
        
        with col1:
            is_selected = st.checkbox(
                f"Select {company}",
                value=company in st.session_state[session_key],
                key=f"company_select_{checkpoint['checkpoint_id']}_{company}",
                label_visibility="hidden"
            )
        
        with col2:
            if is_selected:
                selected_companies.append(company)
                # Show selected company with full info
                st.markdown(f"""
                <div style="border: 2px solid #10b981; border-radius: 8px; padding: 12px; margin-bottom: 10px; background-color: #f0fdf4;">
                    <div style="font-weight: 600; font-size: 16px; color: #1f2937; margin-bottom: 4px;">
                        {company} {priority_info['level']}
                    </div>
                    <div style="color: #6b7280; font-size: 14px; margin-bottom: 4px;">
                        {priority_info['description']}
                    </div>
                    <div style="color: #9ca3af; font-size: 12px;">
                        Risk Assessment: {priority_info['risk']}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                # Show deselected company with muted styling
                st.markdown(f"""
                <div style="border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; margin-bottom: 10px; background-color: #f9fafb; opacity: 0.6;">
                    <div style="font-weight: 600; font-size: 16px; color: #9ca3af; margin-bottom: 4px;">
                        {company} {priority_info['level']} ❌ EXCLUDED
                    </div>
                    <div style="color: #9ca3af; font-size: 14px;">
                        {priority_info['description']}
                    </div>
                </div>
                """, unsafe_allow_html=True)
    
    # Update session state
    st.session_state[session_key] = selected_companies
    
    # Show selection summary
    st.markdown("---")
    
    if len(selected_companies) != len(company_list):
        excluded_count = len(company_list) - len(selected_companies)
        st.warning(f"⚠️ **{excluded_count} companies excluded** from campaign")
    
    # Selection metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Selected", len(selected_companies))
    with col2:
        st.metric("Excluded", len(company_list) - len(selected_companies))
    with col3:
        # Get companies_with_risk data for priority calculation
        companies_with_risk = data.get('companies_with_risk', [])
        high_priority = sum(1 for c in selected_companies if get_company_priority_info(c, companies_with_risk)['level'].startswith("🔴"))
        st.metric("High Priority", high_priority)
    
    # Action buttons
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🚀 Continue to Email Generation", type="primary", key=f"approve_companies_{checkpoint['checkpoint_id']}", use_container_width=True):
            if selected_companies:
                with st.spinner("Approving companies and generating emails..."):
                    result = approve_checkpoint(
                        checkpoint['checkpoint_id'], 
                        'approve', 
                        f"Selected {len(selected_companies)} companies: {', '.join(selected_companies[:3])}{'...' if len(selected_companies) > 3 else ''}",
                        selected_companies=selected_companies
                    )
                    
                if result:
                    st.success(f"✅ {len(selected_companies)} companies approved! Generating personalized emails...")
                    st.info("🔄 Please wait while emails are being generated. This page will refresh automatically.")
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error("❌ Failed to approve companies. Please try again or check the backend connection.")
                    st.write("**Debug Info:** Check browser console and backend logs for details.")
            else:
                st.error("❌ Please select at least one company to continue")
    
    with col2:
        if st.button("❌ Cancel Campaign", key=f"cancel_companies_{checkpoint['checkpoint_id']}", use_container_width=True):
            with st.spinner("Cancelling campaign..."):
                result = approve_checkpoint(checkpoint['checkpoint_id'], 'reject', "Campaign cancelled by user")
            if result:
                st.error("❌ Campaign cancelled")
                st.rerun()
            else:
                st.error("❌ Failed to cancel campaign. Please try again.")

def render_step_2_email_review(checkpoint):
    """Step 2: Enhanced Email Review & Selection"""
    # Progress bar
    render_progress_bar(2, 3)
    
    st.subheader("📧 Step 2: Review & Select Emails")
    
    data = checkpoint.get('data', {})
    emails = data.get('emails', {})
    companies_with_risk = data.get('companies_with_risk', [])  # Get backend risk data
    # Note: companies_with_risk may not be available in email_preview step - backend should include this
    
    if not emails:
        st.error("❌ No emails found for review")
        return
    
    # Filter out None email content
    valid_emails = {company: content for company, content in emails.items() if content is not None}
    
    if not valid_emails:
        st.error("❌ No valid emails found for review")
        st.warning("All email generation attempts failed. Please try restarting the campaign.")
        return
    
    if len(valid_emails) < len(emails):
        failed_count = len(emails) - len(valid_emails)
        st.warning(f"⚠️ {failed_count} emails failed to generate and were excluded")
    
    st.success(f"📝 **{len(valid_emails)} personalized emails generated and ready for review**")
    
    # Initialize selected emails in session state (all selected by default)
    session_key = f"selected_emails_{checkpoint['checkpoint_id']}"
    if session_key not in st.session_state:
        st.session_state[session_key] = list(valid_emails.keys())
    
    # Email selection with previews
    st.markdown("### 📧 Review & Select Emails:")
    st.markdown("*All emails are pre-selected. Uncheck to exclude from sending.*")
    
    selected_emails = []
    
    for company, email_content in valid_emails.items():
        # Additional safety check
        if not email_content:
            st.warning(f"⚠️ Email content for {company} is empty, skipping...")
            continue
            
        # Get company priority info from backend data
        priority_info = get_company_priority_info(company, companies_with_risk)
        
        # Create main container for each email
        col1, col2 = st.columns([0.05, 0.95])
        
        with col1:
            is_selected = st.checkbox(
                f"Select email for {company}",
                value=company in st.session_state[session_key],
                key=f"email_select_{checkpoint['checkpoint_id']}_{company}",
                label_visibility="hidden"
            )
        
        with col2:
            if is_selected:
                selected_emails.append(company)
                
                # Selected email container
                with st.container():
                    st.markdown(f"""
                    <div style="border: 2px solid #10b981; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #f0fdf4;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                            <span style="font-weight: 600; font-size: 16px; color: #1f2937;">
                                📧 Email to {company}
                            </span>
                            <span style="font-size: 12px; padding: 4px 8px; background-color: #dcfce7; border-radius: 12px; color: #166534;">
                                ✅ SELECTED
                            </span>
                        </div>
                        <div style="font-size: 14px; color: #6b7280; margin-bottom: 8px;">
                            {priority_info['level']} • {priority_info['description']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Email preview in expander
                    with st.expander(f"👀 Preview Email Content for {company}", expanded=False):
                        # Extract subject and body with proper null checking
                        try:
                            lines = email_content.split('\n')
                            if lines and lines[0].startswith('Subject:'):
                                subject = lines[0].replace('Subject:', '').strip()
                                body = '\n'.join(lines[1:]).strip()
                            else:
                                subject = f"DevRev Partnership Opportunity for {company}"
                                body = email_content.strip()
                        except Exception as e:
                            # Fallback if email content is malformed
                            subject = f"DevRev Partnership Opportunity for {company}"
                            body = str(email_content) if email_content else "Email content unavailable"
                            st.warning(f"⚠️ Email content formatting issue: {e}")
                        
                        # Show email details
                        st.markdown(f"**📨 Subject:** `{subject}`")
                        
                        # Show email content with better formatting
                        st.markdown("**📄 Email Content:**")
                        st.text_area(
                            "Email Body",
                            value=body,
                            height=200,
                            disabled=True,
                            key=f"email_preview_{checkpoint['checkpoint_id']}_{company}"
                        )
                        
            else:
                # Deselected email container
                st.markdown(f"""
                <div style="border: 1px solid #e5e7eb; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #f9fafb; opacity: 0.6;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: 600; font-size: 16px; color: #9ca3af;">
                            📧 Email to {company}
                        </span>
                        <span style="font-size: 12px; padding: 4px 8px; background-color: #fee2e2; border-radius: 12px; color: #dc2626;">
                            ❌ EXCLUDED
                        </span>
                    </div>
                    <div style="font-size: 14px; color: #9ca3af; margin-top: 8px;">
                        This email will not be sent
                    </div>
                </div>
                """, unsafe_allow_html=True)
    
    # Update session state
    st.session_state[session_key] = selected_emails
    
    # Show selection summary
    st.markdown("---")
    
    if len(selected_emails) != len(valid_emails):
        excluded_count = len(valid_emails) - len(selected_emails)
        st.warning(f"⚠️ **{excluded_count} emails excluded** from sending")
    
    # Email metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Emails to Send", len(selected_emails))
    with col2:
        st.metric("Excluded", len(valid_emails) - len(selected_emails))
    with col3:
        # Calculate average words safely
        total_words = 0
        for company in selected_emails:
            email_content = valid_emails.get(company, "")
            if email_content:
                total_words += len(email_content.split())
        avg_words = total_words // max(len(selected_emails), 1)
        st.metric("Avg Word Count", avg_words)
    
    # Action buttons
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🚀 Continue to Final Review", type="primary", key=f"approve_emails_{checkpoint['checkpoint_id']}", use_container_width=True):
            if selected_emails:
                with st.spinner("Approving emails and preparing for send..."):
                    result = approve_checkpoint(
                        checkpoint['checkpoint_id'], 
                        'approve', 
                        f"Selected {len(selected_emails)} emails for sending",
                        selected_emails=selected_emails
                    )
                    
                if result:
                    st.success(f"✅ {len(selected_emails)} emails approved! Moving to final confirmation...")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Failed to approve emails. Please try again or check the backend connection.")
            else:
                st.error("❌ Please select at least one email to continue")
    
    with col2:
        if st.button("❌ Cancel Campaign", key=f"cancel_emails_{checkpoint['checkpoint_id']}", use_container_width=True):
            result = approve_checkpoint(checkpoint['checkpoint_id'], 'reject', "Campaign cancelled by user")
            if result:
                st.error("❌ Campaign cancelled")
                st.rerun()

def render_step_3_final_confirmation(checkpoint):
    """Step 3: Enhanced Final Send Confirmation"""
    # Progress bar
    render_progress_bar(3, 3)
    
    st.subheader("🚀 Step 3: Final Send Confirmation")
    
    data = checkpoint.get('data', {})
    emails = data.get('emails', {})
    recipient_email = data.get('recipient_email', 'Unknown')
    sector = data.get('sector', 'Unknown')
    companies_with_risk = data.get('companies_with_risk', [])  # Get backend risk data
    # Note: companies_with_risk may not be available in bulk_send_approval step - backend should include this
    
    if not emails:
        st.error("❌ No emails to send")
        return
    
    # Filter out None email content
    valid_emails = {company: content for company, content in emails.items() if content is not None}
    
    if not valid_emails:
        st.error("❌ No valid emails found to send")
        st.warning("All email generation attempts failed. Please try restarting the campaign.")
        return
    
    if len(valid_emails) < len(emails):
        failed_count = len(emails) - len(valid_emails)
        st.warning(f"⚠️ {failed_count} emails failed to generate and were excluded")
    
    # Final summary header
    st.success(f"🎯 **Ready to send {len(valid_emails)} emails for {sector} campaign**")
    
    # Test mode notice
    st.markdown("""
    <div style="background: linear-gradient(90deg, #3b82f6, #1d4ed8); border-radius: 10px; padding: 20px; margin: 20px 0; color: white;">
        <div style="display: flex; align-items: center; margin-bottom: 10px;">
            <span style="font-size: 24px; margin-right: 10px;">🧪</span>
            <span style="font-weight: 600; font-size: 18px;">TEST MODE ACTIVE</span>
        </div>
        <div style="font-size: 14px; opacity: 0.9;">
            All emails will be sent to your test inbox for review and validation
        </div>
        <div style="font-size: 14px; margin-top: 5px; opacity: 0.8;">
            Recipient: <code>{}</code>
        </div>
    </div>
    """.format(recipient_email), unsafe_allow_html=True)
    
    # Final email list with enhanced display
    st.markdown("### 📤 Final Email Summary:")
    
    for i, (company, email_content) in enumerate(valid_emails.items(), 1):
        # Additional safety check
        if not email_content:
            st.warning(f"⚠️ Email content for {company} is empty, skipping...")
            continue
            
        priority_info = get_company_priority_info(company, companies_with_risk)
        
        # Calculate word count safely
        try:
            word_count = len(email_content.split()) if email_content else 0
        except:
            word_count = 0
        
        # Extract subject for display with proper null checking
        try:
            lines = email_content.split('\n')
            if lines and lines[0].startswith('Subject:'):
                subject = lines[0].replace('Subject:', '').strip()
            else:
                subject = f"DevRev Partnership Opportunity for {company}"
        except:
            subject = f"DevRev Partnership Opportunity for {company}"
        
        st.markdown(f"""
        <div style="border: 1px solid #e5e7eb; border-radius: 8px; padding: 15px; margin-bottom: 10px; background-color: white;">
            <div style="display: flex; justify-content: between; align-items: center; margin-bottom: 8px;">
                <span style="font-weight: 600; color: #1f2937; font-size: 16px;">
                    {i}. 📧 {company}
                </span>
                <span style="font-size: 12px; color: #6b7280;">
                    {priority_info['level']}
                </span>
            </div>
            <div style="font-size: 14px; color: #6b7280; margin-bottom: 5px;">
                📨 Subject: {subject}
            </div>
            <div style="font-size: 12px; color: #9ca3af;">
                📊 {word_count} words • Personalized content • Professional tone
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Send summary metrics
    st.markdown("### 📊 Send Summary:")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Emails", len(valid_emails))
    with col2:
        high_priority = sum(1 for company in valid_emails.keys() if get_company_priority_info(company, companies_with_risk)['level'].startswith("🔴"))
        st.metric("High Priority", high_priority)
    with col3:
        # Calculate total words safely
        total_words = 0
        for content in valid_emails.values():
            if content:
                try:
                    total_words += len(content.split())
                except:
                    pass
        st.metric("Total Words", total_words)
    with col4:
        st.metric("Test Recipient", "1")
    
    # Important warnings
    st.markdown("### ⚠️ Important Notes:")
    
    st.warning("🔒 **This action cannot be undone** - emails will be sent immediately upon confirmation")
    st.info("📝 **Review Complete** - All emails have been generated with personalized content")
    st.info("🎯 **Quality Assured** - Each email is tailored to the specific company and includes relevant DevRev value propositions")
    
    # Final confirmation buttons
    st.markdown("---")
    col1, col2 = st.columns([0.7, 0.3])
    
    with col1:
        # Large prominent send button
        if st.button("🚀 SEND ALL EMAILS NOW", type="primary", key=f"send_emails_{checkpoint['checkpoint_id']}", use_container_width=True):
            with st.spinner("Sending emails... This may take a moment."):
                result = approve_checkpoint(checkpoint['checkpoint_id'], 'approve', f"Confirmed: Sending {len(valid_emails)} emails to test inbox")
                
            if result:
                st.success("✅ Emails sent successfully! Campaign completed!")
                st.balloons()
                
                # Show completion message
                st.markdown("""
                <div style="background-color: #10b981; border-radius: 10px; padding: 20px; margin: 20px 0; color: white; text-align: center;">
                    <div style="font-size: 24px; margin-bottom: 10px;">🎉</div>
                    <div style="font-weight: 600; font-size: 18px; margin-bottom: 10px;">Campaign Completed Successfully!</div>
                    <div style="font-size: 14px;">Check your test inbox for all sent emails</div>
                </div>
                """, unsafe_allow_html=True)
                
                time.sleep(3)
                st.rerun()
            else:
                st.error("❌ Failed to send emails. Please try again or check the backend connection.")
    
    with col2:
        if st.button("❌ Cancel Send", key=f"cancel_send_{checkpoint['checkpoint_id']}", use_container_width=True):
            with st.spinner("Cancelling send..."):
                result = approve_checkpoint(checkpoint['checkpoint_id'], 'reject', "Send cancelled by user")
            if result:
                st.error("❌ Send cancelled")
                st.rerun()
            else:
                st.error("❌ Failed to cancel send. Please try again.")


def render_email_preview_checkpoint(checkpoint):
    """Step 2: Review & Select Emails (Alternative Implementation)"""
    st.subheader("📧 Step 2: Review & Select Emails")
    
    data = checkpoint.get('data', {})
    emails = data.get('emails', {})
    
    if not emails:
        st.warning("No emails found")
        return
    
    # Filter out None email content
    valid_emails = {company: content for company, content in emails.items() if content is not None}
    
    if not valid_emails:
        st.error("❌ No valid emails found for review")
        st.warning("All email generation attempts failed. Please try restarting the campaign.")
        return
    
    if len(valid_emails) < len(emails):
        failed_count = len(emails) - len(valid_emails)
        st.warning(f"⚠️ {failed_count} emails failed to generate and were excluded")
    
    st.info(f"📝 **{len(valid_emails)} emails generated and ready for review**")
    
    # Initialize selected emails in session state
    if f"selected_emails_{checkpoint['checkpoint_id']}" not in st.session_state:
        st.session_state[f"selected_emails_{checkpoint['checkpoint_id']}"] = list(valid_emails.keys())
    
    # Email selection with previews
    st.markdown("### 📧 Select Emails to Send:")
    selected_emails = []
    
    for company, email_content in valid_emails.items():
        # Additional safety check
        if not email_content:
            st.warning(f"⚠️ Email content for {company} is empty, skipping...")
            continue
            
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
            
            # Extract subject and body with proper null checking
            try:
                lines = email_content.split('\n')
                if lines and lines[0].startswith('Subject:'):
                    subject = lines[0].replace('Subject:', '').strip()
                    body = '\n'.join(lines[1:]).strip()
                else:
                    subject = f"DevRev Partnership Opportunity for {company}"
                    body = email_content
            except Exception as e:
                # Fallback if email content is malformed
                subject = f"DevRev Partnership Opportunity for {company}"
                body = str(email_content) if email_content else "Email content unavailable"
                st.warning(f"⚠️ Email content formatting issue: {e}")
            
            # Show email subject
            st.markdown(f"**📨 Subject:** {subject}")
            
            # Show email content
            st.markdown("**📄 Email Content:**")
            st.text_area(
                "Email",
                value=body,
                height=150,
                disabled=True,
                key=f"email_preview_{checkpoint['checkpoint_id']}_{company}"
            )
            
            # Quick stats
            word_count = len(body.split()) if body else 0
            st.caption(f"📊 {word_count} words • Professional tone • Personalized")
    
    # Update session state
    st.session_state[f"selected_emails_{checkpoint['checkpoint_id']}"] = selected_emails
    
    # Show selection summary
    if selected_emails != list(valid_emails.keys()):
        excluded = [c for c in valid_emails.keys() if c not in selected_emails]
        st.warning(f"⚠️ {len(excluded)} emails excluded: {', '.join(excluded)}")
    
    st.success(f"✅ {len(selected_emails)} emails selected for sending")
    
    # Approval buttons
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🚀 Continue with Selected Emails", type="primary", key=f"approve_emails_{checkpoint['checkpoint_id']}", use_container_width=True):
            if selected_emails:
                result = approve_checkpoint(
                    checkpoint['checkpoint_id'], 
                    'approve', 
                    f"Selected {len(selected_emails)} emails",
                    selected_emails=selected_emails
                )
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


def render_step_2_email_review(checkpoint):
    """Step 2: Enhanced Email Review & Selection"""
    # Progress bar
    render_progress_bar(2, 3)
    
    st.subheader("📧 Step 2: Review & Select Emails")
    
    data = checkpoint.get('data', {})
    emails = data.get('emails', {})
    companies_with_risk = data.get('companies_with_risk', [])  # Get backend risk data
    # Note: companies_with_risk may not be available in email_preview step - backend should include this
    
    if not emails:
        st.error("❌ No emails found for review")
        return
    
    # Filter out None email content
    valid_emails = {company: content for company, content in emails.items() if content is not None}
    
    if not valid_emails:
        st.error("❌ No valid emails found for review")
        st.warning("All email generation attempts failed. Please try restarting the campaign.")
        return
    
    if len(valid_emails) < len(emails):
        failed_count = len(emails) - len(valid_emails)
        st.warning(f"⚠️ {failed_count} emails failed to generate and were excluded")
    
    st.success(f"📝 **{len(valid_emails)} personalized emails generated and ready for review**")
    
    # Initialize selected emails in session state (all selected by default)
    session_key = f"selected_emails_{checkpoint['checkpoint_id']}"
    if session_key not in st.session_state:
        st.session_state[session_key] = list(valid_emails.keys())
    
    # Email selection with previews
    st.markdown("### 📧 Review & Select Emails:")
    st.markdown("*All emails are pre-selected. Uncheck to exclude from sending.*")
    
    selected_emails = []
    
    for company, email_content in valid_emails.items():
        # Additional safety check
        if not email_content:
            st.warning(f"⚠️ Email content for {company} is empty, skipping...")
            continue
            
        # Get company priority info from backend data
        priority_info = get_company_priority_info(company, companies_with_risk)
        
        # Create main container for each email
        col1, col2 = st.columns([0.05, 0.95])
        
        with col1:
            is_selected = st.checkbox(
                f"Select email for {company}",
                value=company in st.session_state[session_key],
                key=f"email_select_{checkpoint['checkpoint_id']}_{company}",
                label_visibility="hidden"
            )
        
        with col2:
            if is_selected:
                selected_emails.append(company)
                
                # Selected email container
                with st.container():
                    st.markdown(f"""
                    <div style="border: 2px solid #10b981; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #f0fdf4;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                            <span style="font-weight: 600; font-size: 16px; color: #1f2937;">
                                📧 Email to {company}
                            </span>
                            <span style="font-size: 12px; padding: 4px 8px; background-color: #dcfce7; border-radius: 12px; color: #166534;">
                                ✅ SELECTED
                            </span>
                        </div>
                        <div style="font-size: 14px; color: #6b7280; margin-bottom: 8px;">
                            {priority_info['level']} • {priority_info['description']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Email preview in expander
                    with st.expander(f"👀 Preview Email Content for {company}", expanded=False):
                        # Extract subject and body with proper null checking
                        try:
                            lines = email_content.split('\n')
                            if lines and lines[0].startswith('Subject:'):
                                subject = lines[0].replace('Subject:', '').strip()
                                body = '\n'.join(lines[1:]).strip()
                            else:
                                subject = f"DevRev Partnership Opportunity for {company}"
                                body = email_content.strip()
                        except Exception as e:
                            # Fallback if email content is malformed
                            subject = f"DevRev Partnership Opportunity for {company}"
                            body = str(email_content) if email_content else "Email content unavailable"
                            st.warning(f"⚠️ Email content formatting issue: {e}")
                        
                        # Show email details
                        st.markdown(f"**📨 Subject:** `{subject}`")
                        
                        # Show email content with better formatting
                        st.markdown("**📄 Email Content:**")
                        st.text_area(
                            "Email Body",
                            value=body,
                            height=200,
                            disabled=True,
                            key=f"email_preview_{checkpoint['checkpoint_id']}_{company}"
                        )
                        
            else:
                # Deselected email container
                st.markdown(f"""
                <div style="border: 1px solid #e5e7eb; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #f9fafb; opacity: 0.6;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: 600; font-size: 16px; color: #9ca3af;">
                            📧 Email to {company}
                        </span>
                        <span style="font-size: 12px; padding: 4px 8px; background-color: #fee2e2; border-radius: 12px; color: #dc2626;">
                            ❌ EXCLUDED
                        </span>
                    </div>
                    <div style="font-size: 14px; color: #9ca3af; margin-top: 8px;">
                        This email will not be sent
                    </div>
                </div>
                """, unsafe_allow_html=True)
    
    # Update session state
    st.session_state[session_key] = selected_emails
    
    # Show selection summary
    st.markdown("---")
    
    if len(selected_emails) != len(valid_emails):
        excluded_count = len(valid_emails) - len(selected_emails)
        st.warning(f"⚠️ **{excluded_count} emails excluded** from sending")
    
    # Email metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Emails to Send", len(selected_emails))
    with col2:
        st.metric("Excluded", len(valid_emails) - len(selected_emails))
    with col3:
        # Calculate average words safely
        total_words = 0
        for company in selected_emails:
            email_content = valid_emails.get(company, "")
            if email_content:
                total_words += len(email_content.split())
        avg_words = total_words // max(len(selected_emails), 1)
        st.metric("Avg Word Count", avg_words)
    
    # Action buttons
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🚀 Continue to Final Review", type="primary", key=f"approve_emails_{checkpoint['checkpoint_id']}", use_container_width=True):
            if selected_emails:
                with st.spinner("Approving emails and preparing for send..."):
                    result = approve_checkpoint(
                        checkpoint['checkpoint_id'], 
                        'approve', 
                        f"Selected {len(selected_emails)} emails for sending",
                        selected_emails=selected_emails
                    )
                    
                if result:
                    st.success(f"✅ {len(selected_emails)} emails approved! Moving to final confirmation...")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Failed to approve emails. Please try again or check the backend connection.")
            else:
                st.error("❌ Please select at least one email to continue")
    
    with col2:
        if st.button("❌ Cancel Campaign", key=f"cancel_emails_{checkpoint['checkpoint_id']}", use_container_width=True):
            result = approve_checkpoint(checkpoint['checkpoint_id'], 'reject', "Campaign cancelled by user")
            if result:
                st.error("❌ Campaign cancelled")
                st.rerun()

def render_email_preview_checkpoint(checkpoint):
    """Step 2: Review & Select Emails"""
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
            
            # Extract subject and body
            lines = email_content.split('\n')
            if lines[0].startswith('Subject:'):
                subject = lines[0].replace('Subject:', '').strip()
                body = '\n'.join(lines[1:]).strip()
            else:
                subject = f"DevRev Partnership Opportunity for {company}"
                body = email_content
            
            # Show email subject
            st.markdown(f"**📨 Subject:** {subject}")
            
            # Show email content
            st.markdown("**📄 Email Content:**")
            st.text_area(
                "Email",
                value=body,
                height=150,
                disabled=True,
                key=f"email_preview_{checkpoint['checkpoint_id']}_{company}"
            )
            
            # Quick stats
            word_count = len(body.split())
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
                result = approve_checkpoint(
                    checkpoint['checkpoint_id'], 
                    'approve', 
                    f"Selected {len(selected_emails)} emails",
                    selected_emails=selected_emails
                )
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
    """Step 3: Final Send Confirmation"""
    st.subheader("🚀 Step 3: Final Send Confirmation")
    
    data = checkpoint.get('data', {})
    emails = data.get('emails', {})
    
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

def approve_checkpoint(checkpoint_id, decision, feedback=None, selected_companies=None, selected_emails=None):
    """Frontend approval function with selections"""
    try:
        payload = {
            "checkpoint_id": checkpoint_id,
            "decision": decision,
            "feedback": feedback
        }
        
        if selected_companies:
            payload["selected_companies"] = selected_companies
        if selected_emails:
            payload["selected_emails"] = selected_emails
            
        response = requests.post(f"{API_BASE}/approve-checkpoint", json=payload)
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        st.error(f"Approval error: {e}")
        return None

def analytics_tab():
    """Enhanced analytics interface with sector-company tracking"""
    
    st.title("📊 Analytics")
    st.write("Campaign performance and metrics")
    
    # Get data
    analytics = get_analytics()
    dashboard = get_agent_dashboard()
    
    if not analytics:
        st.error("Unable to load analytics")
        return
    
    # Metrics
    summary = analytics.get('summary', {})
    
    st.subheader("📊 Today's Performance")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Emails Sent", summary.get('total_emails_today', 0))
    
    with col2:
        st.metric("Companies", summary.get('unique_companies_today', 0))
    
    with col3:
        st.metric("Sectors", len(summary.get('sectors_today', {})))
    
    with col4:
        campaigns = len(dashboard.get('active_agents', [])) if dashboard else 0
        st.metric("Active Campaigns", campaigns)
    
    # Enhanced Sector Analysis
    if summary.get('sectors_today'):
        st.subheader("🎯 Sector Performance Analysis")
        
        sectors_data = summary['sectors_today']
        if sectors_data:
            # Create two columns for charts
            col1, col2 = st.columns(2)
            
            with col1:
                # Pie chart
                fig_pie = px.pie(
                    values=list(sectors_data.values()),
                    names=list(sectors_data.keys()),
                    title="Emails by Sector"
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col2:
                # Bar chart
                fig_bar = px.bar(
                    x=list(sectors_data.keys()),
                    y=list(sectors_data.values()),
                    title="Email Count by Sector",
                    labels={'x': 'Sector', 'y': 'Email Count'}
                )
                st.plotly_chart(fig_bar, use_container_width=True)
    
    # NEW: Detailed Sector-Company Breakdown
    st.subheader("📋 Detailed Sector-Company Breakdown")
    
    today_emails = analytics.get('recent_emails', [])
    if today_emails:
        # Process data for sector-company breakdown
        sector_company_data = {}
        
        for email in today_emails:
            sector = email.get('sector', 'Unknown')
            company = email.get('company', 'Unknown')
            status = email.get('status', 'unknown')
            
            if sector not in sector_company_data:
                sector_company_data[sector] = {
                    'companies': {},
                    'total_emails': 0,
                    'successful_emails': 0
                }
            
            if company not in sector_company_data[sector]['companies']:
                sector_company_data[sector]['companies'][company] = {
                    'emails_sent': 0,
                    'status': 'unknown'
                }
            
            sector_company_data[sector]['companies'][company]['emails_sent'] += 1
            sector_company_data[sector]['companies'][company]['status'] = status
            sector_company_data[sector]['total_emails'] += 1
            
            if status == 'sent':
                sector_company_data[sector]['successful_emails'] += 1
        
        # Display sector breakdown
        for sector, data in sector_company_data.items():
            with st.expander(f"📊 {sector} Sector - {data['total_emails']} emails sent to {len(data['companies'])} companies", expanded=False):
                
                # Sector summary
                success_rate = (data['successful_emails'] / max(data['total_emails'], 1)) * 100
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Emails", data['total_emails'])
                with col2:
                    st.metric("Companies Reached", len(data['companies']))
                with col3:
                    st.metric("Success Rate", f"{success_rate:.1f}%")
                
                # Company details
                st.markdown("**Companies in this sector:**")
                
                company_df_data = []
                for company, company_data in data['companies'].items():
                    status_emoji = "✅" if company_data['status'] == 'sent' else "❌"
                    company_df_data.append({
                        'Company': f"{status_emoji} {company}",
                        'Emails Sent': company_data['emails_sent'],
                        'Status': company_data['status'].title()
                    })
                
                if company_df_data:
                    df_companies = pd.DataFrame(company_df_data)
                    st.dataframe(df_companies, use_container_width=True, hide_index=True)
    
    # Recent activity (simplified)
    if analytics.get('recent_emails'):
        st.subheader("📧 Recent Activity (Last 10)")
        
        recent_emails = analytics['recent_emails']
        if recent_emails:
            df = pd.DataFrame(recent_emails[-10:])  # Last 10 only
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%H:%M:%S')
            
            # Show simplified view
            display_cols = ['timestamp', 'sector', 'company', 'status']
            if all(col in df.columns for col in display_cols):
                df_display = df[display_cols]
                df_display.columns = ['Time', 'Sector', 'Company', 'Status']
                
                # Add status emoji
                df_display['Status'] = df_display['Status'].apply(
                    lambda x: f"✅ {x}" if x == 'sent' else f"❌ {x}"
                )
                
                st.dataframe(df_display, use_container_width=True, hide_index=True)
    
    # Current campaigns
    if dashboard and dashboard.get('active_agents'):
        st.subheader("🚀 Active Campaigns")
        
        campaign_data = []
        for agent in dashboard['active_agents']:
            status_emoji = "🚀" if agent.get('status') == 'executing' else "⏳"
            campaign_data.append({
                'Status': f"{status_emoji} {agent.get('status', 'unknown').title()}",
                'Sector': agent.get('sector', 'Unknown'),
                'Progress': f"{agent.get('progress', 0)}%",
                'Created': agent.get('created_at', '')[:10] if agent.get('created_at') else 'Unknown'
            })
        
        if campaign_data:
            df_campaigns = pd.DataFrame(campaign_data)
            st.dataframe(df_campaigns, use_container_width=True, hide_index=True)
    
    if st.button("🔄 Refresh", type="primary"):
        st.rerun()

def main():
    """Simple main function"""
    # Sidebar
    st.sidebar.title("🎛️ Control Panel")
    
    # Show metrics in sidebar
    dashboard = get_agent_dashboard()
    # Show metrics in sidebar  
    dashboard = get_agent_dashboard()
    if dashboard:
        summary = dashboard.get('summary', {})
        
        st.sidebar.metric("Active Campaigns", summary.get('active_agents', 0))
        st.sidebar.metric("Pending Approvals", summary.get('pending_checkpoints', 0))
        
        # Check actual agent status
        active_agents = dashboard.get('active_agents', [])
        if active_agents:
            agent = active_agents[0]  # Check first active agent
            status = agent.get('status', 'unknown')
            
            if status == 'waiting_approval':
                agent_details = get_agent_status(agent['job_id'])
                if agent_details and agent_details.get('pending_checkpoints'):
                    checkpoint_type = agent_details['pending_checkpoints'][0].get('type', '')
                    if checkpoint_type == 'plan_approval':
                        st.sidebar.warning("⏳ Waiting for company selection")
                    elif checkpoint_type == 'email_preview':
                        st.sidebar.warning("⏳ Waiting for email review")
                    elif checkpoint_type == 'bulk_send_approval':
                        st.sidebar.warning("⏳ Waiting for send confirmation")
                    else:
                        st.sidebar.error("🚨 Approvals needed")
            elif status in ['generating_emails', 'processing']:
                st.sidebar.info("🔄 Generating emails...")
            elif status == 'executing':
                progress = agent.get('progress', 0)
                st.sidebar.info(f"🚀 Campaign running ({progress}%)")
            elif status == 'completed':
                st.sidebar.success("✅ Campaign completed")
            else:
                st.sidebar.success("✅ All approved")
        else:
            st.sidebar.success("✅ All approved")
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["🚀 Campaigns", "⚙️ Approvals", "📊 Analytics"])
    
    with tab1:
        campaigns_tab()
    
    with tab2:
        approvals_tab()
    
    with tab3:
        analytics_tab()

if __name__ == "__main__":
    main()