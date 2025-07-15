# safety_controls.py
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

class ComplianceStatus(Enum):
    COMPLIANT = "compliant"
    WARNING = "warning"
    VIOLATION = "violation"
    BLOCKED = "blocked"

@dataclass
class SafetyLimit:
    limit_type: str
    max_value: int
    current_value: int
    reset_period: str  # daily, weekly, monthly
    last_reset: datetime

@dataclass
class ComplianceCheck:
    check_type: str
    status: ComplianceStatus
    message: str
    details: Dict

class SafetyController:
    def __init__(self):
        # Email sending limits
        self.email_limits = {
            "daily_emails": SafetyLimit("daily_emails", 50, 0, "daily", datetime.now()),
            "weekly_emails": SafetyLimit("weekly_emails", 200, 0, "weekly", datetime.now()),
            "monthly_emails": SafetyLimit("monthly_emails", 500, 0, "monthly", datetime.now()),
            "emails_per_campaign": SafetyLimit("emails_per_campaign", 20, 0, "campaign", datetime.now())
        }
        
        # Campaign limits
        self.campaign_limits = {
            "daily_campaigns": SafetyLimit("daily_campaigns", 5, 0, "daily", datetime.now()),
            "concurrent_campaigns": SafetyLimit("concurrent_campaigns", 2, 0, "concurrent", datetime.now())
        }
        
        # Blacklisted domains and companies
        self.blacklisted_domains = [
            "competitor1.com", "competitor2.com"
        ]
        
        self.restricted_companies = [
            "direct_competitor", "legal_issues_company"
        ]
        
        # Required compliance patterns
        self.required_elements = {
            "unsubscribe_link": r"unsubscribe|opt.?out",
            "company_identification": r"DevRev",
            "physical_address": r"address|location"
        }
        
    def check_email_limits(self, email_count: int) -> ComplianceCheck:
        """Check if email sending is within limits"""
        self._reset_limits_if_needed()
        
        # Check various limits
        violations = []
        
        # Daily limit
        if self.email_limits["daily_emails"].current_value + email_count > self.email_limits["daily_emails"].max_value:
            violations.append(f"Would exceed daily email limit ({self.email_limits['daily_emails'].max_value})")
            
        # Weekly limit
        if self.email_limits["weekly_emails"].current_value + email_count > self.email_limits["weekly_emails"].max_value:
            violations.append(f"Would exceed weekly email limit ({self.email_limits['weekly_emails'].max_value})")
            
        # Per campaign limit
        if email_count > self.email_limits["emails_per_campaign"].max_value:
            violations.append(f"Campaign exceeds per-campaign limit ({self.email_limits['emails_per_campaign'].max_value})")
            
        if violations:
            return ComplianceCheck(
                check_type="email_limits",
                status=ComplianceStatus.VIOLATION,
                message="; ".join(violations),
                details={"violations": violations, "current_limits": self._get_current_limits()}
            )
            
        return ComplianceCheck(
            check_type="email_limits",
            status=ComplianceStatus.COMPLIANT,
            message="Email count within limits",
            details={"current_limits": self._get_current_limits()}
        )
        
    def check_campaign_limits(self) -> ComplianceCheck:
        """Check if new campaign can be started"""
        self._reset_limits_if_needed()
        
        violations = []
        
        # Daily campaigns
        if self.campaign_limits["daily_campaigns"].current_value >= self.campaign_limits["daily_campaigns"].max_value:
            violations.append(f"Daily campaign limit reached ({self.campaign_limits['daily_campaigns'].max_value})")
            
        # Concurrent campaigns
        if self.campaign_limits["concurrent_campaigns"].current_value >= self.campaign_limits["concurrent_campaigns"].max_value:
            violations.append(f"Concurrent campaign limit reached ({self.campaign_limits['concurrent_campaigns'].max_value})")
            
        if violations:
            return ComplianceCheck(
                check_type="campaign_limits",
                status=ComplianceStatus.VIOLATION,
                message="; ".join(violations),
                details={"violations": violations}
            )
            
        return ComplianceCheck(
            check_type="campaign_limits",
            status=ComplianceStatus.COMPLIANT,
            message="Campaign limits OK",
            details={}
        )
        
    def check_target_compliance(self, companies: List[str], recipient_email: str) -> ComplianceCheck:
        """Check if target companies and recipients are compliant"""
        violations = []
        warnings = []
        
        # Check blacklisted domains
        recipient_domain = recipient_email.split('@')[1].lower()
        if recipient_domain in self.blacklisted_domains:
            violations.append(f"Recipient domain {recipient_domain} is blacklisted")
            
        # Check restricted companies
        for company in companies:
            if company.lower() in [rc.lower() for rc in self.restricted_companies]:
                violations.append(f"Company {company} is restricted")
                
        # Check for competitor domains
        for company in companies:
            company_domain = f"{company.lower().replace(' ', '')}.com"
            if company_domain in self.blacklisted_domains:
                warnings.append(f"Company {company} may be a competitor")
                
        if violations:
            return ComplianceCheck(
                check_type="target_compliance",
                status=ComplianceStatus.VIOLATION,
                message="; ".join(violations),
                details={"violations": violations, "warnings": warnings}
            )
        elif warnings:
            return ComplianceCheck(
                check_type="target_compliance",
                status=ComplianceStatus.WARNING,
                message="; ".join(warnings),
                details={"warnings": warnings}
            )
            
        return ComplianceCheck(
            check_type="target_compliance",
            status=ComplianceStatus.COMPLIANT,
            message="Targets are compliant",
            details={}
        )
        
    def check_email_content_compliance(self, email_content: str) -> ComplianceCheck:
        """Check if email content meets compliance requirements"""
        import re
        
        violations = []
        warnings = []
        
        # Check for required elements
        for element, pattern in self.required_elements.items():
            if not re.search(pattern, email_content, re.IGNORECASE):
                if element == "unsubscribe_link":
                    violations.append("Missing unsubscribe mechanism")
                elif element == "company_identification":
                    warnings.append("Company identification unclear")
                elif element == "physical_address":
                    warnings.append("Physical address not specified")
                    
        # Check email length
        if len(email_content) > 2000:
            warnings.append("Email is very long, may be flagged as spam")
        elif len(email_content) < 100:
            warnings.append("Email is very short, may appear unprofessional")
            
        # Check for spam triggers
        spam_triggers = [
            r'act now', r'urgent', r'limited time', r'free money',
            r'guaranteed', r'no risk', r'100% free', r'click here',
            r'make money', r'earn \$', r'cash bonus'
        ]
        
        for trigger in spam_triggers:
            if re.search(trigger, email_content, re.IGNORECASE):
                warnings.append(f"Contains potential spam trigger: {trigger}")
                
        if violations:
            return ComplianceCheck(
                check_type="content_compliance",
                status=ComplianceStatus.VIOLATION,
                message="; ".join(violations),
                details={"violations": violations, "warnings": warnings}
            )
        elif warnings:
            return ComplianceCheck(
                check_type="content_compliance",
                status=ComplianceStatus.WARNING,
                message="; ".join(warnings),
                details={"warnings": warnings}
            )
            
        return ComplianceCheck(
            check_type="content_compliance",
            status=ComplianceStatus.COMPLIANT,
            message="Content is compliant",
            details={}
        )
        
    def run_full_compliance_check(self, companies: List[str], recipient_email: str, 
                                 email_contents: Dict[str, str]) -> List[ComplianceCheck]:
        """Run comprehensive compliance check"""
        checks = []
        
        # Check email limits
        checks.append(self.check_email_limits(len(email_contents)))
        
        # Check campaign limits
        checks.append(self.check_campaign_limits())
        
        # Check target compliance
        checks.append(self.check_target_compliance(companies, recipient_email))
        
        # Check each email content
        for company, content in email_contents.items():
            content_check = self.check_email_content_compliance(content)
            content_check.details["company"] = company
            checks.append(content_check)
            
        return checks
        
    def record_email_sent(self, count: int = 1):
        """Record that emails were sent (for limit tracking)"""
        self.email_limits["daily_emails"].current_value += count
        self.email_limits["weekly_emails"].current_value += count
        self.email_limits["monthly_emails"].current_value += count
        self.email_limits["emails_per_campaign"].current_value += count
        
    def record_campaign_started(self):
        """Record that a campaign was started"""
        self.campaign_limits["daily_campaigns"].current_value += 1
        self.campaign_limits["concurrent_campaigns"].current_value += 1
        
    def record_campaign_completed(self):
        """Record that a campaign was completed"""
        self.campaign_limits["concurrent_campaigns"].current_value -= 1
        
    def _reset_limits_if_needed(self):
        """Reset limits based on their reset periods"""
        now = datetime.now()
        
        for limit in self.email_limits.values():
            if self._should_reset_limit(limit, now):
                limit.current_value = 0
                limit.last_reset = now
                
        for limit in self.campaign_limits.values():
            if self._should_reset_limit(limit, now):
                limit.current_value = 0
                limit.last_reset = now
                
    def _should_reset_limit(self, limit: SafetyLimit, now: datetime) -> bool:
        """Check if a limit should be reset"""
        if limit.reset_period == "daily":
            return (now - limit.last_reset).days >= 1
        elif limit.reset_period == "weekly":
            return (now - limit.last_reset).days >= 7
        elif limit.reset_period == "monthly":
            return (now - limit.last_reset).days >= 30
        return False
        
    def _get_current_limits(self) -> Dict:
        """Get current limit status"""
        return {
            limit_type: {
                "current": limit.current_value,
                "max": limit.max_value,
                "remaining": limit.max_value - limit.current_value,
                "reset_period": limit.reset_period
            }
            for limit_type, limit in self.email_limits.items()
        }
        
    def add_unsubscribe_footer(self, email_content: str) -> str:
        """Add compliant unsubscribe footer to email"""
        footer = """

---
This email was sent by DevRev Inc.
If you no longer wish to receive emails from us, please reply with "UNSUBSCRIBE".

DevRev Inc.
123 Business Ave, Suite 100
San Francisco, CA 94105
"""
        return email_content + footer
        
    def emergency_stop_all_campaigns(self, reason: str):
        """Emergency stop for all campaigns"""
        # This would integrate with your agent system
        print(f"🚨 EMERGENCY STOP: {reason}")
        # Set all agents to failed state
        # Send notifications to admins
        # Log incident

# Global safety controller
safety_controller = SafetyController()