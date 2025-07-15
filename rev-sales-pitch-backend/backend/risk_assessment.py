# risk_assessment.py
import re
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
from agent_state import RiskLevel

@dataclass
class RiskFactor:
    factor_type: str
    severity: RiskLevel
    description: str
    recommendation: str

class RiskAssessment:
    def __init__(self):
        # High-profile companies that require special handling
        self.high_profile_companies = {
            'microsoft', 'google', 'apple', 'amazon', 'meta', 'netflix', 
            'salesforce', 'oracle', 'ibm', 'adobe', 'nvidia', 'tesla'
        }
        
        # Sensitive topics that need approval
        self.sensitive_topics = {
            'layoffs', 'layoff', 'downsizing', 'bankruptcy', 'lawsuit', 
            'controversy', 'scandal', 'hack', 'breach', 'investigation',
            'regulatory', 'compliance', 'penalty', 'fine'
        }
        
        # Industry-specific compliance requirements
        self.regulated_industries = {
            'financial', 'healthcare', 'pharmaceutical', 'banking', 
            'insurance', 'government', 'defense'
        }
        
        # Email content patterns that indicate risk
        self.risky_patterns = [
            r'urgent|immediate|emergency',
            r'guaranteed|promise|100%',
            r'free|no cost|no charge',
            r'limited time|expires|deadline',
            r'confidential|secret|insider'
        ]
        
    def assess_company_risk(self, company: str, sector: str) -> RiskLevel:
        """Assess risk level for targeting a specific company"""
        company_lower = company.lower()
        
        # Check if high-profile company
        if any(hp in company_lower for hp in self.high_profile_companies):
            return RiskLevel.HIGH
            
        # Check if regulated industry
        if any(ri in sector.lower() for ri in self.regulated_industries):
            return RiskLevel.MEDIUM
            
        return RiskLevel.LOW
        
    def assess_email_content_risk(self, email_content: str, company: str) -> Tuple[RiskLevel, List[RiskFactor]]:
        """Assess risk level of email content"""
        risk_factors = []
        content_lower = email_content.lower()
        
        # Check for sensitive topics
        for topic in self.sensitive_topics:
            if topic in content_lower:
                risk_factors.append(RiskFactor(
                    factor_type="sensitive_topic",
                    severity=RiskLevel.HIGH,
                    description=f"Email mentions sensitive topic: {topic}",
                    recommendation="Consider softer language or remove reference"
                ))
                
        # Check for risky patterns
        for pattern in self.risky_patterns:
            if re.search(pattern, content_lower):
                risk_factors.append(RiskFactor(
                    factor_type="risky_language",
                    severity=RiskLevel.MEDIUM,
                    description=f"Email contains potentially risky language: {pattern}",
                    recommendation="Consider more professional tone"
                ))
                
        # Check email length (too long or too short)
        word_count = len(email_content.split())
        if word_count < 50:
            risk_factors.append(RiskFactor(
                factor_type="email_length",
                severity=RiskLevel.LOW,
                description="Email is very short, may appear impersonal",
                recommendation="Consider adding more context"
            ))
        elif word_count > 200:
            risk_factors.append(RiskFactor(
                factor_type="email_length",
                severity=RiskLevel.MEDIUM,
                description="Email is very long, may reduce engagement",
                recommendation="Consider shortening the message"
            ))
            
        # Determine overall risk level
        if any(rf.severity == RiskLevel.HIGH for rf in risk_factors):
            overall_risk = RiskLevel.HIGH
        elif any(rf.severity == RiskLevel.MEDIUM for rf in risk_factors):
            overall_risk = RiskLevel.MEDIUM
        else:
            overall_risk = RiskLevel.LOW
            
        return overall_risk, risk_factors
        
    def assess_campaign_risk(self, companies: List[str], sector: str) -> Tuple[RiskLevel, Dict[str, Any]]:
        """Assess overall campaign risk"""
        high_risk_companies = []
        medium_risk_companies = []
        
        for company in companies:
            risk = self.assess_company_risk(company, sector)
            if risk == RiskLevel.HIGH:
                high_risk_companies.append(company)
            elif risk == RiskLevel.MEDIUM:
                medium_risk_companies.append(company)
                
        # Determine overall campaign risk
        if high_risk_companies:
            overall_risk = RiskLevel.HIGH
        elif len(medium_risk_companies) > len(companies) / 2:
            overall_risk = RiskLevel.MEDIUM
        else:
            overall_risk = RiskLevel.LOW
            
        assessment = {
            'overall_risk': overall_risk,
            'high_risk_companies': high_risk_companies,
            'medium_risk_companies': medium_risk_companies,
            'recommendations': self._generate_campaign_recommendations(
                high_risk_companies, medium_risk_companies, sector
            )
        }
        
        return overall_risk, assessment
        
    def _generate_campaign_recommendations(self, high_risk: List[str], medium_risk: List[str], sector: str) -> List[str]:
        """Generate recommendations based on risk assessment"""
        recommendations = []
        
        if high_risk:
            recommendations.append(f"Manual approval required for {len(high_risk)} high-profile companies")
            recommendations.append("Consider executive review for high-risk targets")
            
        if medium_risk:
            recommendations.append(f"Extra caution needed for {len(medium_risk)} regulated industry targets")
            
        if sector.lower() in self.regulated_industries:
            recommendations.append("Ensure compliance with industry regulations")
            
        if not recommendations:
            recommendations.append("Campaign appears low-risk, can proceed with standard monitoring")
            
        return recommendations

# Global risk assessor
risk_assessor = RiskAssessment()